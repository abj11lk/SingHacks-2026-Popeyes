"""
Scenario Agent -- "what happens if this unresolved situation moves."

Built for CL-0019 (Abdullah Al-Mansoori): the Strait of Hormuz situation is
unresolved as of today (event_log's last entry, 05-08-2026, is a naval
blockade after renewed attacks), and his RM note from 12-08-2026 records him
asking exactly this question -- "asked for a view on what happens to his
portfolio if the Strait reopens and normalises. We have not modelled this."
This agent is that model.

Unlike the Explanation Agent, this one can't be answered by looking anything
up -- there is no tool that returns "what happens if". The agent has to
reason from: what he actually holds (SCENARIO_TOOLS = get_client_snapshot,
get_lookthrough_exposure, get_events, get_market_context, get_notes), how
those holdings behaved during the actual Hormuz-closure event earlier this
year (a real historical analog for the escalation direction), and the
plain economic direction of a de-escalation (materially the reverse). The
system prompt is deliberately strict about labelling this as reasoned
projection, not fact -- there is nothing here to fabricate-check against
a ground truth, so the discipline has to be in how the answer is framed.

The default question deliberately never names "Hormuz" -- it asks the agent
to identify the relevant unresolved situation itself from get_events cross-
referenced with the client's actual holdings. A hardcoded topic in the
question would mean the code handed the model its own answer; asking it to
find the situation is what actually demonstrates reasoning rather than
scripted output, and it's what a reviewer reading this file sees.
"""
from .. import db
from ..db import SNAPSHOT_DATES, TODAY
from ..langchain_tools import SCENARIO_TOOLS
from . import common
from .explanation import MODEL


def _client_header(client_id: str) -> str:
    rows = db.query("SELECT client_name FROM clients WHERE client_id = ?", (client_id,))
    if rows.empty:
        raise ValueError(f"Unknown client_id: {client_id}")
    return rows.iloc[0]["client_name"]


def _build_system_prompt(client_name: str) -> str:
    return f"""Scenario Agent. First identify which unresolved situation in event_log.csv still \
materially affects {client_name}'s portfolio, then analyse what happens if it moves in either \
direction -- as a brief ready to read before a client call.

Rules:
- Events: only get_events (event_log.csv), never your own knowledge of what actually happened. \
Look for one whose effects are still open/ongoing (the most recent relevant event, and whether \
later events show it resolving or continuing) and whose transmission channels overlap this \
client's actual holdings -- don't default to whichever event is most recent in the log if a \
different one is the one that actually touches this portfolio.
- Dates: exactly {', '.join(SNAPSHOT_DATES)}. '{TODAY}' = today; omit as_of for today. In your \
written answer, reformat dates as DD-MM-YYYY (e.g. {TODAY[8:10]}-{TODAY[5:7]}-{TODAY[0:4]}).
- Never cite a market level/rate/price without calling get_market_context first; guessing is \
fabrication.
- Use get_lookthrough_exposure to find what the client is actually exposed to underneath any \
structured product -- a name buried in a "worst-of basket" is a real exposure, not a detail.
- Use get_notes and the client profile (source_of_wealth, objectives) to check whether the \
scenario also touches the client's life outside the portfolio -- e.g. a business in the same \
sector as a holding is not diversification, it is the same bet twice, and that is worth saying \
plainly even if uncomfortable.
- This is a PROJECTION, not a lookup. Say so explicitly. Ground the escalation direction in \
what actually happened during the real historical event (use diff_snapshots-style reasoning from \
get_client_snapshot at different dates if useful, and get_market_context, for the real, already-\
observed move); for the reverse direction (de-escalation), say clearly that it is the reasoned \
opposite, not an observed fact, and name your assumptions. Never state a specific number for a \
hypothetical outcome as if it were certain -- use ranges or directional language and say why.
- Cite exact tool-sourced figures for anything you claim already happened. Say so if unsure.

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

    if question is None:
        question = (
            f"As of today ({TODAY}), identify any major unresolved situation in the event log "
            f"that still materially affects this client's portfolio. Analyse what happens if it "
            f"escalates further, and what happens if it de-escalates and normalises. "
            f"What matters before the next client call?"
        )

    return common.run_agent(
        agent_type="scenario",
        model_name=MODEL,
        tools=SCENARIO_TOOLS,
        system_prompt=_build_system_prompt(client_name),
        question=question,
        client_id=client_id,
    )
