"""
Explanation Agent -- "what did this portfolio do, and why."

First working checkpoint of the multi-agent build (per the build order: tool
layer, then this agent proven against CL-0012, then Risk+Scenario on
CL-0019, then Recommendation on CL-0014).

A LangGraph ReAct agent (langgraph.prebuilt.create_react_agent) over Groq,
restricted to the tools that matter for explanation
(langchain_tools.EXPLANATION_TOOLS): get_client_snapshot, diff_snapshots,
get_notes, get_events, get_market_context. Execution (invoke, LangSmith
tracing, Supabase audit logging, tool-call trace extraction) lives in
agents/common.py, shared with every other agent.

get_market_context exists because the first working version of this agent
fabricated a plausible-sounding but wrong number: it said the 10-year
Treasury yield started the year "around 3.8%" when it had no tool that
could tell it that (the real figure, from market_context.csv, is 4.05%).
Giving it the actual series to query removed the incentive to guess.
"""
from .. import db
from ..db import SNAPSHOT_DATES, TODAY
from ..langchain_tools import EXPLANATION_TOOLS
from . import common

# Switched from openai/gpt-oss-120b after that model's 200,000-token/day
# free-tier quota was exhausted by testing. Same model family (similar
# tool-calling behavior), smaller, with its own separate daily quota --
# Groq tracks rate limits per model, not per account.
MODEL = "openai/gpt-oss-20b"


def _client_header(client_id: str) -> str:
    """client_name straight from clients.csv."""
    rows = db.query("SELECT client_name FROM clients WHERE client_id = ?", (client_id,))
    if rows.empty:
        raise ValueError(f"Unknown client_id: {client_id}")
    return rows.iloc[0]["client_name"]


def _build_system_prompt(client_name: str) -> str:
    # Kept deliberately short -- this account has an 8,000 tokens/minute cap and LangGraph's
    # ReAct loop resends the full prompt on every turn, so prompt length compounds across tool
    # calls. Every rule here earned its place from an actual failure: rule 1 because event
    # descriptions must not be invented, rule on market data because the first version of this
    # agent guessed a Treasury yield instead of looking it up (see module docstring). No RM name
    # anywhere -- the report is read by whoever's using the tool, not addressed to a named person.
    return f"""Explanation Agent. Explain what {client_name}'s portfolio did and why, as a brief \
ready to read before a client call.

Rules:
- Events: only get_events (event_log.csv), never your own knowledge.
- Dates: exactly {', '.join(SNAPSHOT_DATES)}. '{TODAY}' = today; omit as_of for today.
- diff_snapshots: say whether each move is price effect (held, price moved) or flow effect (a \
trade) -- don't blur the two.
- Never cite a market level/rate/price without calling get_market_context first; guessing is \
fabrication.
- Ground it in the client: use get_notes/profile (age, objectives, what they've said); flag \
tension with the data.
- Cite exact tool-sourced figures/dates. Say so if unsure.
- Dates are given to you as YYYY-MM-DD (e.g. {TODAY}) -- when tool arguments need a date, pass \
it in that exact form. In your written answer only, reformat dates as DD-MM-YYYY \
(e.g. {TODAY[8:10]}-{TODAY[5:7]}-{TODAY[0:4]}).

Answer in short, plain English. Write the brief itself -- do not address, name, or refer to the \
relationship manager in the third person (no "Priscilla should...", no "the RM can use this...")."""


def explain(client_id: str, question: str | None = None,
            from_date: str | None = None, to_date: str | None = None) -> dict:
    """
    Runs the Explanation Agent for one client and returns the answer plus a
    full traceability record (tool calls made, LangSmith trace URL if
    available). Also writes an audit row to Supabase's agent_runs table.
    """
    from_date = from_date or SNAPSHOT_DATES[0]
    to_date = to_date or TODAY

    client_name = _client_header(client_id)

    if question is None:
        question = (
            f"Explain what happened in {client_id}'s portfolio between {from_date} and {to_date}, "
            f"and why. What matters before the next client call?"
        )

    return common.run_agent(
        agent_type="explanation",
        model_name=MODEL,
        tools=EXPLANATION_TOOLS,
        system_prompt=_build_system_prompt(client_name),
        question=question,
        client_id=client_id,
    )
