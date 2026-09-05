"""
Explanation Agent -- "what did this portfolio do, and why."

First working checkpoint of the multi-agent build (per the build order: tool
layer, then this agent proven against CL-0012, then Risk+Scenario on
CL-0019, then Recommendation on CL-0014).

Single-shot design (see agents/common.py for why): _gather_context() below
calls tools.py directly -- get_client_snapshot, diff_snapshots, get_notes,
get_events, get_market_context -- once, deterministically, with sensible
defaults (today, the full baseline-to-today window). No ReAct loop; the
model gets everything in one message and writes the answer in one call.

get_market_context is fetched because the first working version of this
agent fabricated a plausible-sounding but wrong number: it said the
10-year Treasury yield started the year "around 3.8%" when it had no way
to know that (the real figure, from market_context.csv, is 4.05%). Handing
it the actual series removed the incentive to guess.
"""
from langsmith import traceable

from .. import db, tools
from ..db import SNAPSHOT_DATES, TODAY
from ..langchain_tools import _condense_diff, _condense_snapshot
from . import common
from .common import traced_call

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


def _gather_context(client_id: str, from_date: str, to_date: str) -> dict:
    """
    One deterministic pass over tools.py -- zero LLM tokens spent gathering.
    Each call is wrapped via traced_call so it still shows up as its own
    named span in LangSmith, nested under explain()'s @traceable chain run,
    even though nothing here is an LLM-driven tool call anymore.
    """
    return {
        "get_client_snapshot": _condense_snapshot(
            traced_call("get_client_snapshot", tools.get_client_snapshot, client_id, to_date)
        ),
        "diff_snapshots": _condense_diff(
            traced_call("diff_snapshots", tools.diff_snapshots, client_id, from_date, to_date),
            include_events=False,
        ),
        "get_notes": traced_call("get_notes", tools.get_notes, client_id),
        "get_events": traced_call("get_events", tools.get_events, from_date, to_date),
        "get_market_context": traced_call(
            "get_market_context", tools.get_market_context,
            from_date, to_date, common.DEFAULT_MARKET_SERIES,
        ),
    }


def _build_system_prompt(client_name: str) -> str:
    # Kept deliberately short -- this account has an 8,000 tokens/minute cap, and prompt
    # length matters even for a single call. Every rule here earned its place from an
    # actual failure: rule 1 because event descriptions must not be invented, the
    # market-data rule because this agent once guessed a Treasury yield instead of being
    # given the real one (see module docstring). No RM name anywhere -- the report is
    # read by whoever's using the tool, not addressed to a named person.
    return f"""Explanation Agent. Explain what {client_name}'s portfolio did and why, as a brief \
ready to read before a client call, using ONLY the data provided below.

Rules:
- get_events is the only source for 2026 events. Never use your own knowledge.
- '{TODAY}' = today. In your written answer, reformat dates as DD-MM-YYYY \
(e.g. {TODAY[8:10]}-{TODAY[5:7]}-{TODAY[0:4]}).
- diff_snapshots splits each move into price effect (price moved) vs flow effect (a trade \
happened) -- state which one actually occurred, don't blur the two.
- Never state a market level, rate or price move that isn't in the get_market_context data \
provided. A plausible-sounding number you were not given is a fabrication, even one you're \
confident about.
- Ground it in the client: use get_notes/profile (age, objectives, what they've said); flag \
tension with the data.
- Cite exact figures and dates from the data provided. If something isn't in the data, say so \
instead of guessing.

Answer in short, plain English. Write the brief itself -- do not address, name, or refer to the \
relationship manager in the third person (no "Priscilla should...", no "the RM can use this...")."""


@traceable(run_type="chain", name="explanation-agent")
def explain(client_id: str, question: str | None = None,
            from_date: str | None = None, to_date: str | None = None) -> dict:
    """
    Runs the Explanation Agent for one client and returns the answer plus a
    full traceability record (what was pre-fetched, LangSmith trace URL if
    available). Also writes an audit row to Supabase's agent_runs table.
    """
    from_date = from_date or SNAPSHOT_DATES[0]
    to_date = to_date or TODAY

    client_name = _client_header(client_id)
    context = _gather_context(client_id, from_date, to_date)

    if question is None:
        question = (
            f"Explain what happened in {client_id}'s portfolio between {from_date} and {to_date}, "
            f"and why. What matters before the next client call?"
        )

    return common.run_agent(
        agent_type="explanation",
        model_name=MODEL,
        system_prompt=_build_system_prompt(client_name),
        question=question,
        context=context,
        client_id=client_id,
    )
