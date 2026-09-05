"""
Shared execution harness for every agent: LangGraph invoke + LangSmith trace
capture + Supabase audit logging + tool-call extraction. Each agent module
(explanation.py, scenario.py, ...) supplies only what's specific to it -- the
tool list, the system prompt, the question -- so a fix to the harness (e.g.
how tracing degrades when LangSmith is unavailable) lives in one place, not
copy-pasted per agent and fixed in only one of them by accident.
"""
import json
import time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tracers.context import tracing_v2_enabled
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from .. import config, supabase_client


def tool_calls_from_messages(messages):
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


def run_agent(*, agent_type: str, model_name: str, tools: list, system_prompt: str,
              question: str, client_id: str) -> dict:
    """
    Runs a ReAct agent end to end and returns everything both the API layer
    and a standalone driver script need: the answer, a tool-call trace, the
    LangSmith trace URL (None if tracing is broken/unconfigured -- degrades
    gracefully rather than failing the run), and the Supabase agent_runs row
    id (also None if that write fails, for the same reason).
    """
    # max_tokens defaults to None (no explicit completion-token reservation),
    # and Groq's own default left zero room once a few tool calls had grown
    # the input context -- the Scenario Agent (5 tool calls) came back with a
    # completely empty answer, not just truncated. 2000 stopped a full empty
    # answer but still truncated a long two-scenario report mid-table.
    # Careful raising this further: the 8,000 TPM cap is INPUT + max_tokens
    # combined (that's what "Request too large" measures), so too high a
    # value here reintroduces the original 413 error instead of fixing
    # truncation -- 3000 is a middle ground, verified empirically below.
    model = ChatGroq(model=model_name, temperature=0, api_key=config.GROQ_API_KEY, max_tokens=3000)
    agent = create_react_agent(model, tools=tools, prompt=system_prompt)

    started = time.time()
    trace_url = None
    try:
        with tracing_v2_enabled(project_name=config.LANGSMITH_PROJECT) as cb:
            result = agent.invoke(
                {"messages": [HumanMessage(content=question)]},
                config={"run_name": f"{agent_type}-agent", "tags": [agent_type, client_id]},
            )
            try:
                trace_url = cb.get_run_url()
            except Exception as e:
                print(f"[{agent_type}-agent] LangSmith trace URL unavailable: {e}")
    except Exception as e:
        print(f"[{agent_type}-agent] Tracing disabled/unavailable ({e}); running untraced.")
        result = agent.invoke({"messages": [HumanMessage(content=question)]})

    latency_ms = int((time.time() - started) * 1000)

    messages = result["messages"]
    final = next((m for m in reversed(messages) if isinstance(m, AIMessage) and m.content), None)
    answer = final.content if final else ""
    tool_calls = tool_calls_from_messages(messages)

    run_row = None
    try:
        run_row = supabase_client.log_agent_run(
            agent_type=agent_type,
            client_id=client_id,
            model=model_name,
            input_summary={"question": question},
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
        "tool_calls": tool_calls,
        "latency_ms": latency_ms,
        "langsmith_trace_url": trace_url,
        "agent_run_id": run_row["id"] if run_row else None,
    }
