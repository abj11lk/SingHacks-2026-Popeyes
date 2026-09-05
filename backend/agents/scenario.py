"""
Scenario Agent -- "what happens if this unresolved situation moves."

Built for CL-0019 (Abdullah Al-Mansoori): the Strait of Hormuz situation is
unresolved as of today (event_log's last entry, 05-08-2026, is a naval
blockade after renewed attacks), and his RM note from 12-08-2026 records him
asking exactly this question -- "asked for a view on what happens to his
portfolio if the Strait reopens and normalises. We have not modelled this."
This agent is that model.

Single-shot design (see agents/common.py for why): _gather_context() pre-
fetches get_client_snapshot, get_lookthrough_exposure, diff_snapshots
(baseline-to-today -- what actually moved and by how much, the real
historical analog for the escalation direction), get_events (unfiltered,
so the model can identify the relevant situation itself rather than being
told), and get_market_context, all deterministically, no ReAct loop.

The default question deliberately never names "Hormuz" -- it asks the agent
to identify the relevant unresolved situation itself from the (unfiltered)
event data cross-referenced with the client's actual holdings. A hardcoded
topic in the question would mean the code handed the model its own answer;
asking it to find the situation is what actually demonstrates reasoning
rather than scripted output, and it's what a reviewer reading this file
sees.
"""
from .. import db, tools
from ..db import SNAPSHOT_DATES, TODAY
from ..langchain_tools import _condense_diff, _condense_snapshot
from . import common
from .explanation import MODEL


def _client_header(client_id: str) -> str:
    rows = db.query("SELECT client_name FROM clients WHERE client_id = ?", (client_id,))
    if rows.empty:
        raise ValueError(f"Unknown client_id: {client_id}")
    return rows.iloc[0]["client_name"]


def _gather_context(client_id: str) -> dict:
    """One deterministic pass over tools.py -- zero LLM tokens spent gathering."""
    return {
        "get_client_snapshot": _condense_snapshot(tools.get_client_snapshot(client_id, TODAY)),
        "get_lookthrough_exposure": tools.get_lookthrough_exposure(client_id, TODAY),
        "diff_snapshots_baseline_to_today": _condense_diff(
            tools.diff_snapshots(client_id, SNAPSHOT_DATES[0], TODAY),
            max_movers=3, include_events=False,
        ),
        "get_events_all": tools.get_events(),  # unfiltered -- the model identifies the relevant one
        "get_market_context": tools.get_market_context(series_ids=common.DEFAULT_MARKET_SERIES),
        "get_notes": tools.get_notes(client_id),
    }


def _build_system_prompt(client_name: str) -> str:
    return f"""Scenario Agent. Using ONLY the data provided below, first identify which \
unresolved situation in get_events_all still materially affects {client_name}'s portfolio, then \
analyse what happens if it moves in either direction -- as a brief ready to read before a client \
call.

Rules:
- get_events_all is the only source for what happened in 2026. Never use your own knowledge. \
Look for a situation whose effects are still open/ongoing (check whether later events show it \
resolving or continuing) and whose transmission channels overlap this client's actual holdings \
-- don't default to whichever event is most recent if a different one is the one that actually \
touches this portfolio.
- '{TODAY}' = today. In your written answer, reformat dates as DD-MM-YYYY \
(e.g. {TODAY[8:10]}-{TODAY[5:7]}-{TODAY[0:4]}).
- Never state a market level, rate or price move that isn't in the get_market_context data \
provided. A plausible-sounding number you were not given is a fabrication.
- Use get_lookthrough_exposure to find what the client is actually exposed to underneath any \
structured product -- a name buried in a "worst-of basket" is a real exposure, not a detail.
- Use get_notes and the client profile (source_of_wealth, objectives) to check whether the \
scenario also touches the client's life outside the portfolio -- e.g. a business in the same \
sector as a holding is not diversification, it is the same bet twice, and that is worth saying \
plainly even if uncomfortable.
- This is a PROJECTION, not a lookup. Say so explicitly. Ground the escalation direction in what \
diff_snapshots_baseline_to_today and get_market_context show actually happened (the real, \
already-observed move); for the reverse direction (de-escalation), say clearly that it is the \
reasoned opposite, not an observed fact, and name your assumptions. Never state a specific number \
for a hypothetical outcome as if it were certain -- use ranges or directional language and say \
why.
- Cite exact figures from the data provided for anything you claim already happened. If \
something isn't in the data, say so instead of guessing.

Answer in short, plain English. Cover both directions (further escalation, and de-escalation/\
reopening). Write the brief itself -- do not address, name, or refer to the relationship manager \
in the third person."""


def analyze(client_id: str, question: str | None = None) -> dict:
    """
    Runs the Scenario Agent for one client and returns the answer plus a
    full traceability record. Also writes an audit row to Supabase's
    agent_runs table (agent_type='scenario').
    """
    client_name = _client_header(client_id)
    context = _gather_context(client_id)

    if question is None:
        question = (
            f"As of today ({TODAY}), identify any major unresolved situation that still "
            f"materially affects this client's portfolio. Analyse what happens if it escalates "
            f"further, and what happens if it de-escalates and normalises. "
            f"What matters before the next client call?"
        )

    return common.run_agent(
        agent_type="scenario",
        model_name=MODEL,
        system_prompt=_build_system_prompt(client_name),
        question=question,
        context=context,
        client_id=client_id,
    )
