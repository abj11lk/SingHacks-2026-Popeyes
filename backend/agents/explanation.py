"""
Explanation Agent -- "what did this portfolio do, and why."

First working checkpoint of the multi-agent build (per the build order: tool
layer, then this agent proven against CL-0012, then Risk+Scenario on
CL-0019, then Recommendation on CL-0014).

A LangGraph ReAct agent (langgraph.prebuilt.create_react_agent) over Groq,
restricted to the tools that matter for explanation
(langchain_tools.EXPLANATION_TOOLS): get_client_snapshot, diff_snapshots,
get_notes, get_events, get_market_context. Every run is logged to Supabase
(agent_runs) with the tool-call trace, and traced in LangSmith when tracing
is configured and working -- if it isn't, the run still completes; a broken
LangSmith key degrades tracing, not the agent.

get_market_context exists because the first working version of this agent
fabricated a plausible-sounding but wrong number: it said the 10-year
Treasury yield started the year "around 3.8%" when it had no tool that
could tell it that (the real figure, from market_context.csv, is 4.05%).
Giving it the actual series to query removed the incentive to guess.
"""
import json
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tracers.context import tracing_v2_enabled
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from .. import config, supabase_client
from ..db import SNAPSHOT_DATES, TODAY
from ..langchain_tools import EXPLANATION_TOOLS

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = f"""You are the Explanation Agent inside a wealth intelligence workbench used \
by Priscilla Ong, a relationship manager at a private bank. Your job is to explain what a \
client's portfolio did and why, in a way she could use directly in a client conversation.

Ground rules, non-negotiable:

1. event_log.csv (via get_events) is the ONLY authoritative source for what happened in the \
world in 2026. Never use your own knowledge of 2026 events. If get_events disagrees with what \
you think you know, get_events wins.

2. The five snapshot dates in this dataset are exactly: {', '.join(SNAPSHOT_DATES)}. \
'{TODAY}' is "today". Never invent or guess a different date.

3. Use diff_snapshots to explain change, not just report it. It splits each instrument's move \
into an approximate price effect (the position was already held and its price moved) and a flow \
effect (a buy, sell, or capital call changed the quantity). Say which one actually happened -- \
"the portfolio fell because yields rose on bonds the client still holds" is a different, more \
useful sentence than "the portfolio fell 7%", and a different sentence again from "the client \
sold into the decline" if the transactions say otherwise.

4. diff_snapshots lists every event in the window but does not tell you which holdings each one \
touched -- that link is yours to reason out from the holding's asset class/sector and the event's \
primary_transmission field, and you must flag it as your own inference ("likely", "consistent \
with") rather than stating it as a confirmed fact.

4b. NEVER state a market level, rate, or price move (a yield, an index level, a commodity price, \
an FX rate) without first calling get_market_context to check the actual figure. A plausible-\
sounding number you were not given by a tool is a fabrication, full stop -- this applies even to \
numbers you are fairly confident about from general knowledge. If get_market_context does not \
cover something, say you don't have that figure rather than estimating it.

5. Read get_notes and the client profile before you explain anything. A number without the \
client behind it is not an explanation. Age, life stage, stated objectives, and what they have \
actually told their RM (which sometimes contradicts what the portfolio shows) are part of the \
explanation, not background colour. If the client's own words are in tension with what the data \
shows, say so plainly -- that tension is usually the most important thing to flag, not something \
to smooth over.

6. If you are not sure of something, say so and say what you would check, rather than producing \
a confident-sounding answer the data does not actually support.

7. Cite real figures: exact dollar amounts, dates, and instrument names from the tool outputs, \
not vague gestures ("some bonds", "recently"). Every number you state should be traceable to a \
specific tool call.

Write your final answer as something Priscilla could read to herself before a client call: a \
short, plain-English explanation, client-appropriate in tone (no jargon like "price effect" \
verbatim -- translate it), that connects the portfolio's numbers to who this client actually is \
and what they told her."""


def _tool_calls_from_messages(messages):
    """Extracts a compact {tool_name, args, result_summary} trace from the LangGraph message history."""
    calls = []
    pending = {}
    for m in messages:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                pending[tc["id"]] = {"tool_name": tc["name"], "args": tc["args"]}
        elif isinstance(m, ToolMessage):
            entry = pending.get(m.tool_call_id, {"tool_name": m.name, "args": {}})
            content = m.content if isinstance(m.content, str) else json.dumps(m.content, default=str)
            entry["result_summary"] = content[:2000]
            calls.append(entry)
    return calls


def explain(client_id: str, question: str | None = None,
            from_date: str | None = None, to_date: str | None = None) -> dict:
    """
    Runs the Explanation Agent for one client and returns the answer plus a
    full traceability record (tool calls made, LangSmith trace URL if
    available). Also writes an audit row to Supabase's agent_runs table.
    """
    from_date = from_date or SNAPSHOT_DATES[0]
    to_date = to_date or TODAY

    if question is None:
        question = (
            f"Explain what happened in {client_id}'s portfolio between {from_date} and {to_date}, "
            f"and why. What should Priscilla know before her next call with this client?"
        )

    model = ChatGroq(model=MODEL, temperature=0, api_key=config.GROQ_API_KEY)
    agent = create_react_agent(model, tools=EXPLANATION_TOOLS, prompt=SYSTEM_PROMPT)

    started = time.time()
    trace_url = None
    try:
        with tracing_v2_enabled(project_name=config.LANGCHAIN_PROJECT) as cb:
            result = agent.invoke(
                {"messages": [HumanMessage(content=question)]},
                config={"run_name": "explanation-agent", "tags": ["explanation", client_id]},
            )
            try:
                trace_url = cb.get_run_url()
            except Exception as e:
                print(f"[explanation-agent] LangSmith trace URL unavailable: {e}")
    except Exception as e:
        print(f"[explanation-agent] Tracing disabled/unavailable ({e}); running untraced.")
        result = agent.invoke({"messages": [HumanMessage(content=question)]})

    latency_ms = int((time.time() - started) * 1000)

    messages = result["messages"]
    final = next((m for m in reversed(messages) if isinstance(m, AIMessage) and m.content), None)
    answer = final.content if final else ""
    tool_calls = _tool_calls_from_messages(messages)

    run_row = None
    try:
        run_row = supabase_client.log_agent_run(
            agent_type="explanation",
            client_id=client_id,
            model=MODEL,
            input_summary={"question": question, "from_date": from_date, "to_date": to_date},
            output={"answer": answer},
            tool_calls=tool_calls,
            langsmith_trace_url=trace_url,
            latency_ms=latency_ms,
        )
    except Exception as e:
        print(f"[explanation-agent] Supabase audit log failed ({e}); continuing without it.")

    return {
        "client_id": client_id,
        "question": question,
        "answer": answer,
        "tool_calls": tool_calls,
        "latency_ms": latency_ms,
        "langsmith_trace_url": trace_url,
        "agent_run_id": run_row["id"] if run_row else None,
    }
