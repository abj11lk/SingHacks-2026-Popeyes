"""
Recommendation Agent -- "here's what I'd consider doing, you decide."

Built for CL-0014 (Lau Chi Ming): a Hong Kong property bet spread across
three separate-looking wrappers of the same issuer -- a perpetual bond, a
common stock, and an accumulator referencing it (~29% of AUM combined per
get_lookthrough_exposure; an earlier version of this docstring said ~53%
across four wrappers including "direct real estate" -- that number was
inflated by a since-fixed clustering bug that had also merged in an
unrelated bank's bond purely because both bonds share the word
"perpetual"), on top of a genuine liquidity mismatch (an
HKD 60m redevelopment contribution due mid-2027 against a portfolio where
only ~43% is Daily-liquid). Both risks are already visible as plain data on
the dashboard (the Concentration card, the Liquidity bar); this agent's job
is to turn that into concrete, individually actionable proposals -- not to
discover the risk itself.

Single-shot design (see agents/common.py for why): _gather_context() pre-
fetches everything -- including check_mandate_breach for every one of the
client's portfolios (derived from get_client_snapshot, not hardcoded to
one), and get_market_context (added after a real run cited "1 USD = 7.8
HKD" for an HKD cash-need conversion with no data behind it -- the real
rate that day was 7.81; same unsourced-market-figure bug already fixed
once for Explanation, closed here too).

Unlike Explanation/Scenario, output here isn't one report -- it's a set of
DISCRETE recommendations, because the whole point of this capability is
"RM stays in control": each one needs to be independently accept/edit/
reject-able, not bundled into a single wall of text. Rather than pay for a
second LLM call to force structured output, the prompt requires a strict
"### Recommendation: <title>" heading per item and parse_recommendations()
below splits the single answer on that heading -- same cost as Explanation/
Scenario, no extra Groq call.
"""
import re

from langsmith import traceable

from .. import db, tools
from ..db import TODAY
from ..langchain_tools import _condense_snapshot
from . import common
from .common import traced_call
from .explanation import MODEL

_HEADING_RE = re.compile(r"^###\s*Recommendation:\s*(.+)$", re.MULTILINE)


def _client_header(client_id: str) -> str:
    rows = db.query("SELECT client_name FROM clients WHERE client_id = ?", (client_id,))
    if rows.empty:
        raise ValueError(f"Unknown client_id: {client_id}")
    return rows.iloc[0]["client_name"]


def _gather_context(client_id: str) -> dict:
    """
    One deterministic pass over tools.py -- zero LLM tokens spent gathering.
    Each call is wrapped via traced_call so it still shows up as its own
    named span in LangSmith, nested under recommend()'s @traceable chain run.
    """
    snapshot = traced_call("get_client_snapshot", tools.get_client_snapshot, client_id, TODAY)

    def _all_mandate_breaches():
        return {
            p["portfolio_id"]: tools.check_mandate_breach(p["portfolio_id"], TODAY)
            for p in snapshot["portfolios"]
        }

    mandate_breaches = traced_call("check_mandate_breach_by_portfolio", _all_mandate_breaches)

    return {
        "get_client_snapshot": _condense_snapshot(snapshot),
        "get_lookthrough_exposure": traced_call(
            "get_lookthrough_exposure", tools.get_lookthrough_exposure, client_id, TODAY
        ),
        "get_liquidity_map": traced_call("get_liquidity_map", tools.get_liquidity_map, client_id, TODAY),
        "check_mandate_breach_by_portfolio": mandate_breaches,
        "get_notes": traced_call("get_notes", tools.get_notes, client_id),
        "get_market_context": traced_call(
            "get_market_context", tools.get_market_context, series_ids=common.DEFAULT_MARKET_SERIES
        ),
    }


def _build_system_prompt(client_name: str) -> str:
    return f"""Recommendation Agent. Using ONLY the data provided below, propose concrete \
actions worth considering for {client_name}'s portfolio, grounded in real concentration/\
liquidity/mandate data -- for a human to accept, edit, or reject. You are proposing, not \
deciding.

Rules:
- '{TODAY}' = today. In your written answer, reformat dates as DD-MM-YYYY \
(e.g. {TODAY[8:10]}-{TODAY[5:7]}-{TODAY[0:4]}).
- Use get_lookthrough_exposure and check_mandate_breach_by_portfolio to find concentration/\
mandate issues; use get_liquidity_map to find whether known cash needs can actually be met from \
what's sellable.
- Use get_notes to understand what the client actually believes and wants -- a recommendation \
that contradicts a client's stated conviction must say so explicitly and address it, not ignore \
it. Do not propose selling into a client's stated loss-aversion without acknowledging that \
directly.
- Ground every recommendation in exact figures from the data provided (weights, dollar amounts, \
mandate limits, liquidity tiers). Never invent a number.
- Never state an FX rate or convert between currencies with a rate that isn't in the \
get_market_context data provided (series like USDHKD, USDSGD) -- a plausible-sounding rate you \
were not given is a fabrication, even one you're confident about.
- Every recommendation must be a specific, concrete action (trim a position by an amount, use a \
facility instead of a sale, etc.) -- not vague advice like "consider diversifying".
- If an asset class is UNDER its mandate minimum, the fix is to ADD to it (or add cash that will \
be invested into it), never to trim it further -- trimming an already-underweight class moves it \
further from the target, not closer. Before finalizing each recommendation, check that the \
direction of the action you propose (buy/add vs sell/trim) actually moves the specific number \
you cited toward the target you cited, not away from it, and check your own arithmetic on any \
subtraction you state as a fact (e.g. "X% below the Y% minimum" must equal Y minus X).
- Frame recommendations as options worth discussing, not instructions -- "worth considering" \
language, since a human decides whether to act on it.
- Propose 1 to 3 recommendations, no more. Each one gets its own section starting EXACTLY with \
"### Recommendation: <short title>" (a few words, no client name needed) on its own line, \
followed by the rationale as plain prose. This exact heading format is required -- it is how \
each recommendation becomes its own reviewable item, not a formatting preference.

Do not address, name, or refer to the relationship manager in the third person. Do not write any \
text before the first "### Recommendation:" heading or after the last recommendation's prose."""


def parse_recommendations(answer: str) -> list[dict]:
    """
    Splits the agent's answer into discrete {title, rationale} items on the
    required "### Recommendation: <title>" heading. Returns an empty list
    (not an error) if the model didn't follow the format -- callers decide
    what to do with zero parsed recommendations rather than this function
    guessing or fabricating a fallback title.
    """
    matches = list(_HEADING_RE.finditer(answer))
    items = []
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(answer)
        rationale = answer[start:end].strip()
        if title and rationale:
            items.append({"title": title, "rationale": rationale})
    return items


@traceable(run_type="chain", name="recommendation-agent")
def recommend(client_id: str, question: str | None = None) -> dict:
    """
    Runs the Recommendation Agent for one client, parses discrete
    recommendations out of the answer, and returns both the full raw answer
    (for the agent_runs audit trail, same as every other agent) and the
    parsed list (for the caller to persist into Supabase's recommendations
    table, one row per item, so each can be accepted/edited/rejected
    independently).
    """
    client_name = _client_header(client_id)
    context = _gather_context(client_id)

    if question is None:
        question = (
            f"Review {client_id}'s portfolio for concentration, mandate, and liquidity issues, "
            f"and propose concrete actions worth considering. What matters before the next "
            f"client call?"
        )

    result = common.run_agent(
        agent_type="recommendation",
        model_name=MODEL,
        system_prompt=_build_system_prompt(client_name),
        question=question,
        context=context,
        client_id=client_id,
    )
    result["recommendations"] = parse_recommendations(result["answer"])
    return result
