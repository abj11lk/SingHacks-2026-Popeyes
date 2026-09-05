"""
Shared execution harness for every agent -- single-shot design.

Each agent pre-fetches everything it needs in one deterministic Python pass
(calling backend/tools.py directly -- zero LLM tokens), then makes exactly
ONE Groq call with that data already embedded in the prompt. No ReAct loop,
no multi-turn tool-calling.

This replaced an earlier LangGraph create_react_agent design after repeated
real failures: a 5-tool-call ReAct run costs roughly 6 compounding turns
(each resending the system prompt, tool schemas, and every prior tool
result), burned ~17k cumulative tokens in one run, and would sometimes
exhaust its own completion budget mid-loop and return a completely empty
answer with no error. A single call with pre-assembled context costs
about one turn's worth of tokens, once, with nothing to compound and
nothing to run out of room partway through.

What's still shared here, deliberately, regardless of how each agent
gathers its context: the actual Groq call, LangSmith trace capture, and
Supabase audit logging (backend/agents/common.py's module docstring
history has more on why -- a LangSmith bug fixed here once already fixed
it for every agent at once, whereas copy-pasted per-agent it would not
have). What's NOT forced to be shared: the system prompt, which tools get
pre-fetched, and how the output gets shaped (recommendation.py's
parse_recommendations() layers on top of this untouched).
"""
import json
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tracers.context import tracing_v2_enabled
from langchain_groq import ChatGroq
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from .. import config, supabase_client


def traced_call(name, fn, *args, **kwargs):
    """
    Wraps a single tools.py call as a named "tool" span in LangSmith,
    without coupling tools.py itself to any tracing framework. Used inside
    each agent's _gather_context() so the pre-fetch step still shows up as
    individual, inspectable spans in the trace, nested under whichever
    @traceable-decorated function called it (LangSmith propagates that
    context automatically) -- even though these are plain Python calls, not
    LLM-driven tool calls the way they were under the old ReAct design.
    """
    return traceable(name=name, run_type="tool")(fn)(*args, **kwargs)

# get_market_context returns all 23 series if series_ids is omitted --
# ~4,300 chars, the single largest item in every agent's context once
# events stopped being duplicated. None of the three focal clients'
# stories touch TTF gas, EUR/GBP/CNH/IDR/INR/THB FX, or the Nasdaq/STI/
# MSCI Asia indices specifically -- this curated list covers every series
# actually referenced this session (rates, the two commodities that map to
# real events, the two FX pairs our HK/SG-domiciled clients touch, the two
# broad equity gauges, volatility) at roughly half the token cost.
DEFAULT_MARKET_SERIES = [
    "UST_10Y_PCT", "UST_2Y_PCT", "FED_FUNDS_UPPER_PCT", "US_CPI_YOY_PCT",
    "GOLD_USD_OZ", "BRENT_USD_BBL",
    "SPX", "HSI",
    "USDHKD", "USDSGD",
    "VIX",
]


def format_context(context: dict) -> str:
    """
    Renders pre-fetched tool outputs as labelled JSON blocks, so the model
    can cite exactly which tool a figure came from ("per get_liquidity_map,
    daily-liquid is $11.4m") the same way it would after a live tool call --
    the traceability doesn't depend on the call having just happened.
    """
    return "\n\n".join(
        f"--- {name} ---\n{json.dumps(data, default=str)}"
        for name, data in context.items()
    )


def run_agent(*, agent_type: str, model_name: str, system_prompt: str,
              question: str, context: dict, client_id: str) -> dict:
    """
    context: {tool_name: pre-fetched result} -- gathered by the calling
    agent module via its own _gather_context(), not by the model.

    Returns the same shape the old ReAct-based harness did (answer,
    tool_calls, latency_ms, langsmith_trace_url, agent_run_id), so callers
    (recommendation.py's parsing, the API layer) don't need to change.
    tool_calls here just lists what was pre-fetched, since nothing was
    "called" mid-conversation anymore.
    """
    # reasoning_effort="low" matters more than max_tokens does here: gpt-oss models spend
    # part of their completion budget on hidden chain-of-thought (a "reasoning_tokens"
    # count separate from the visible answer), and a single large single-shot prompt made
    # the model reason so much longer than it did per-turn in the old ReAct design that it
    # burned the ENTIRE 3000-token budget on thinking and returned a one-line answer (once,
    # completely empty). Confirmed directly: same prompt, same context, default reasoning
    # effort used 2998 of 3000 tokens on reasoning; "low" used 4, leaving the rest for the
    # actual report -- which itself only needed ~1,100-1,300 tokens once reasoning stopped
    # eating the budget. max_tokens is now sized close to that real usage rather than a
    # defensive 3000: Groq's 413 check is prompt_tokens + max_tokens (the theoretical
    # ceiling), not actual usage, so an oversized reserve counts against the 8,000 TPM cap
    # even when the model never gets close to using it.
    model = ChatGroq(model=model_name, temperature=0, api_key=config.GROQ_API_KEY,
                      max_tokens=1800, reasoning_effort="low")

    full_question = f"{question}\n\nData available to you:\n{format_context(context)}"
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=full_question)]

    started = time.time()
    trace_url = None
    try:
        with tracing_v2_enabled(project_name=config.LANGSMITH_PROJECT):
            response = model.invoke(
                messages,
                config={"run_name": f"{agent_type}-agent-llm-call", "tags": [agent_type, client_id]},
            )
            # Since explain()/analyze()/recommend() are themselves @traceable, this Groq
            # call is now a child span of that run rather than its own tracing root --
            # tracing_v2_enabled's own callback handler has no root run of its own to hand
            # back a URL for (cb.get_run_url() raises "No traced run found" here). The
            # current run tree (this span or an ancestor -- either resolves to the same
            # trace) is the reliable way to get a shareable URL under nesting.
            try:
                run_tree = get_current_run_tree()
                trace_url = run_tree.get_url() if run_tree else None
            except Exception as e:
                print(f"[{agent_type}-agent] LangSmith trace URL unavailable: {e}")
    except Exception as e:
        print(f"[{agent_type}-agent] Tracing disabled/unavailable ({e}); running untraced.")
        response = model.invoke(messages)

    latency_ms = int((time.time() - started) * 1000)
    answer = response.content

    tool_calls = [
        {"tool_name": name, "args": {}, "result_summary": json.dumps(data, default=str)[:2000]}
        for name, data in context.items()
    ]

    run_row = None
    try:
        run_row = supabase_client.log_agent_run(
            agent_type=agent_type,
            client_id=client_id,
            model=model_name,
            input_summary={"question": question, "tools_used": list(context.keys())},
            output={"answer": answer},
            tool_calls=tool_calls,
            langsmith_trace_url=trace_url,
            latency_ms=latency_ms,
        )
    except Exception as e:
        print(f"[{agent_type}-agent] Supabase audit log failed ({e}); continuing without it.")

    return {
        "client_id": client_id,
        "question": question,
        "answer": answer,
        "tool_calls": [{"tool_name": name, "args": {}} for name in context.keys()],
        "latency_ms": latency_ms,
        "langsmith_trace_url": trace_url,
        "agent_run_id": run_row["id"] if run_row else None,
    }
