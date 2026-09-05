"""
Prioritisation Agent -- "twenty clients, one RM. Who does she call first, and
can you defend the ranking?" (the challenge statement's own framing).

Two layers, deliberately kept separate:

1. A deterministic signal/score layer (build_client_signals, build_book_priorities)
   -- pure Python, zero LLM tokens, real threshold checks against tools.py
   (check_mandate_breach, get_facility_status, get_liquidity_map,
   get_lookthrough_exposure). This is what actually decides the ranking and
   is defensible on its own: every signal cites the real number and the real
   threshold it crossed. It runs on every page load, same as the plain-data
   Overview cards -- no Groq call, no rate-limit concern.

2. A single-shot LLM call (brief()) on top, following the same pattern as
   explanation.py/scenario.py/recommendation.py (agents/common.py's
   run_agent, @traceable spans). Its job is narrative, not scoring: given
   the already-ranked, already-scored top clients and their real signals,
   write a short "why call her today" briefing in that order. The LLM
   cannot change who's #1 -- it can only explain the ranking the
   deterministic layer already produced, which is what keeps the ranking
   itself defensible rather than a black box.

This intentionally does not reuse Hahvinaash's branch's prioritisation.py:
that version detected liquidity shortfalls by searching for the word
"shortfall" in a stringified Python dict rather than comparing real numbers.
Every check here is a real numeric comparison against a real threshold.
"""
from langsmith import traceable

from .. import tools
from ..db import TODAY
from . import common
from .common import traced_call
from .explanation import MODEL

# (urgency, impact, confidence, relevance), each 0-10 -- a fixed, explicit
# table rather than something the LLM assigns per-signal, since the ranking
# itself needs to be defensible by rule, not by the model's mood.
SIGNAL_WEIGHTS = {
    "ltv_breach": (10, 9, 10, 9),
    "mandate_breach": (9, 9, 10, 10),
    "single_position_breach": (9, 8, 10, 9),
    "liquidity_shortfall": (8, 8, 8, 8),
    "liquidity_fx_gap": (6, 6, 6, 7),
    "concentration": (6, 7, 8, 7),
}

CONCENTRATION_THRESHOLD_PCT = 20.0
TOP_N_FOR_BRIEFING = 8


def _score(signal_type: str) -> float:
    u, i, c, r = SIGNAL_WEIGHTS[signal_type]
    return round((u * 0.30 + i * 0.30 + c * 0.20 + r * 0.20) * 10, 2)


def _priority_label(score: float) -> str:
    if score <= 0:
        return "CLEAR"
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def build_client_signals(client_id: str, as_of: str | None = None) -> list[dict]:
    """
    One client's real, threshold-based signals -- zero LLM tokens. Every
    signal's "detail" string cites the actual figures involved, the same
    traceability discipline as every other tool result in this codebase.
    """
    as_of = as_of or TODAY
    signals: list[dict] = []

    snapshot = tools.get_client_snapshot(client_id, as_of)
    for p in snapshot["portfolios"]:
        breach = tools.check_mandate_breach(p["portfolio_id"], as_of)
        for row in breach.get("asset_class_breaches", []):
            signals.append({
                "type": "mandate_breach",
                "portfolio_id": p["portfolio_id"],
                "portfolio_name": p["portfolio_name"],
                "title": f"{p['portfolio_name']}: {row['asset_class']} outside mandate band",
                "detail": (
                    f"Actual {row['actual_pct']}% vs target {row['target_pct']}% "
                    f"(band {row['min_pct']}-{row['max_pct']}%)"
                ),
                "score": _score("mandate_breach"),
            })
        for row in breach.get("single_position_breaches", []):
            signals.append({
                "type": "single_position_breach",
                "portfolio_id": p["portfolio_id"],
                "portfolio_name": p["portfolio_name"],
                "title": f"{p['portfolio_name']}: {row['instrument_name']} over single-position limit",
                "detail": f"{row['weight_pct']}% of portfolio vs {row['max_single_position_pct']}% limit",
                "score": _score("single_position_breach"),
            })

    for facility in tools.get_facility_status(client_id, as_of):
        if facility["breach"]:
            signals.append({
                "type": "ltv_breach",
                "portfolio_id": facility["collateral_portfolio_id"],
                "portfolio_name": None,
                "title": f"Facility {facility['facility_id']} at/above margin-call LTV",
                "detail": f"LTV {facility['ltv_pct']}% vs {facility['margin_call_ltv_pct']}% margin-call trigger",
                "score": _score("ltv_breach"),
            })

    liquidity = tools.get_liquidity_map(client_id, as_of)
    coverage = (liquidity["daily_liquid_usd"] or 0) + (liquidity["credit_facility_headroom_usd"] or 0)
    shortfall = (liquidity["near_term_cash_needs_usd_only"] or 0) - coverage
    if shortfall > 0:
        signals.append({
            "type": "liquidity_shortfall",
            "portfolio_id": None,
            "portfolio_name": None,
            "title": "Near-term USD cash need exceeds same-day-liquid assets + facility headroom",
            "detail": (
                f"${liquidity['near_term_cash_needs_usd_only']:,.0f} due vs "
                f"${coverage:,.0f} available (${shortfall:,.0f} short) within "
                f"{liquidity['horizon_days']} days"
            ),
            "score": _score("liquidity_shortfall"),
        })
    non_usd = liquidity.get("near_term_cash_needs_other_ccy") or []
    if non_usd:
        signals.append({
            "type": "liquidity_fx_gap",
            "portfolio_id": None,
            "portfolio_name": None,
            "title": "Non-USD cash need(s) due, not covered by the USD-only liquidity check",
            "detail": f"{len(non_usd)} need(s) in other currencies: "
                      + ", ".join(f"{n['currency']} {n['amount']:,.0f}" for n in non_usd),
            "score": _score("liquidity_fx_gap"),
        })

    lookthrough = tools.get_lookthrough_exposure(client_id, as_of)
    for theme in lookthrough.get("candidate_concentration_themes", []):
        if theme["combined_pct_of_client_aum"] >= CONCENTRATION_THRESHOLD_PCT:
            signals.append({
                "type": "concentration",
                "portfolio_id": None,
                "portfolio_name": None,
                "title": f"Cross-instrument concentration: {theme['label_guess']}",
                "detail": f"{theme['combined_pct_of_client_aum']}% of client AUM across "
                          f"{len(theme['instruments'])} instruments referencing the same theme",
                "score": _score("concentration"),
            })

    return signals


def build_book_priorities(as_of: str | None = None) -> list[dict]:
    """
    Every client, ranked. A client's score is the worst single signal's
    score plus a small bonus per additional distinct signal type (capped at
    100) -- multiple compounding issues rank above one issue of similar
    severity, which is the actual judgment call "who calls first" requires.
    """
    as_of = as_of or TODAY
    rows = []
    for c in tools.list_clients(as_of):
        signals = build_client_signals(c["client_id"], as_of)
        if signals:
            distinct_types = len(set(s["type"] for s in signals))
            score = min(100, max(s["score"] for s in signals) + 5 * (distinct_types - 1))
        else:
            score = 0
        rows.append({
            "client_id": c["client_id"],
            "client_name": c["client_name"],
            "aum_usd_from_holdings": c["aum_usd_from_holdings"],
            "score": round(score, 2),
            "priority": _priority_label(score),
            "signals": sorted(signals, key=lambda s: s["score"], reverse=True),
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def _build_system_prompt() -> str:
    return """Prioritisation Agent. Using ONLY the ranked client signals provided below, write a \
short book-wide triage briefing for a Relationship Manager covering twenty clients: who should she \
call first today, and why.

Rules:
- The ranking and every score you see is already fixed by a deterministic rule -- you are \
explaining it, not re-ranking it. Present the clients in the exact order given.
- Cite the exact signal detail provided for each client (the real percentages, dollar amounts, or \
LTV figures) -- never invent a number or a reason not present in the data.
- For each client, one or two sentences: what's wrong and why it's urgent, referencing the actual \
signal(s) listed for them.
- If a client has multiple signals, mention the combination, not just the single worst one.
- Do not address, name, or refer to the relationship manager in the third person.

Write the briefing itself, ranked client by client, in plain English."""


@traceable(run_type="chain", name="prioritisation-agent")
def brief(as_of: str | None = None, question: str | None = None) -> dict:
    """
    Runs the Prioritisation Agent once for the whole book and returns the
    answer plus a full traceability record, same shape as the other three
    agents (client_id is the "BOOK" sentinel here rather than a real
    client -- agent_runs.client_id is a plain nullable text column, no
    foreign key, so this is safe).
    """
    as_of = as_of or TODAY
    book = traced_call("build_book_priorities", build_book_priorities, as_of)
    flagged = [r for r in book if r["score"] > 0][:TOP_N_FOR_BRIEFING]

    context = {
        "book_priorities_top_flagged": [
            {
                "client_id": r["client_id"],
                "client_name": r["client_name"],
                "score": r["score"],
                "priority": r["priority"],
                "signals": [
                    {"title": s["title"], "detail": s["detail"]} for s in r["signals"]
                ],
            }
            for r in flagged
        ],
        "total_clients": len(book),
        "flagged_clients": len(flagged),
    }

    if question is None:
        question = (
            f"As of {as_of}, {len(flagged)} of {len(book)} clients have at least one active "
            f"signal. Write the triage briefing in ranked order."
        )

    result = common.run_agent(
        agent_type="prioritisation",
        model_name=MODEL,
        system_prompt=_build_system_prompt(),
        question=question,
        context=context,
        client_id="BOOK",
    )
    result["book"] = book
    return result
