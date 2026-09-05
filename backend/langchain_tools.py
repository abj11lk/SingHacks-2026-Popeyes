"""
LangChain @tool wrappers over backend/tools.py, for LangGraph agents.

Every wrapper here does nothing but call the matching plain function in
tools.py and return its result -- no business logic lives in this file.
That split exists so the dashboard backend, a test, and an LLM agent all
run the exact same code path to answer "what does this client's portfolio
look like" -- there's one place to fix a bug, not three (see tools.py's
module docstring).

Docstrings here are written for the model, not for a human reading the
source -- they're the tool descriptions the LLM sees, so they spell out
things a human wouldn't need told (e.g. the five valid snapshot dates,
since a model has no reason to know this dataset only has five).

Note: concatenating a variable onto a triple-quoted string inside a function
body is a string *concatenation expression*, not a docstring -- Python only
recognises a bare string literal as the first statement as __doc__, so that
pattern silently leaves __doc__ as None and @tool refuses to wrap the
function. The snapshot-dates reminder is appended to each already-defined
function's __doc__ below instead, after the fact.
"""
from typing import Optional

from langchain_core.tools import tool

from . import tools as t
from .db import SNAPSHOT_DATES, TODAY


def _safe(fn, *args, **kwargs):
    """
    Runs a tools.py function and turns any exception into an LLM-readable
    error dict instead of letting it propagate. This matters because
    LangGraph's ToolNode only catches its own internal ToolInvocationError
    by default (malformed arguments) -- an application-level ValueError
    (e.g. an invalid snapshot date, which the model *will* pass sometimes,
    since event dates and snapshot dates aren't the same five values) would
    otherwise crash the whole agent run instead of giving the model
    something to retry with.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


_SNAPSHOT_HELP = (
    f"\n\nValid snapshot dates are exactly: {', '.join(SNAPSHOT_DATES)}. "
    f"'{TODAY}' is 'today' in this dataset. Omit this argument to use today. "
    "Do not pass any other date -- there is no data for it."
)

# The Groq account backing this deployment has an 8,000 tokens-per-minute
# cap on the model in use. tools.py's raw output is built for traceability
# (every field, a full sources block) and routinely runs 3,000-5,000 tokens
# per call once JSON-serialized -- fine for the dashboard/API, but two or
# three such calls in one ReAct loop blow straight through the budget. These
# LLM-facing wrappers trim to what's needed to reason and cite figures
# correctly (real numbers, real dates, real instrument names all stay);
# tools.py itself is untouched, so every other caller keeps full fidelity.


def _condense_snapshot(snap: dict, max_holdings: int = 10) -> dict:
    holdings = sorted(snap["holdings"], key=lambda h: h["market_value_usd"], reverse=True)
    shown = holdings[:max_holdings]
    portfolios = [
        {
            "portfolio_id": p["portfolio_id"],
            "portfolio_name": p["portfolio_name"],
            "service_model": p["service_model"],
            "mandate_name": p["mandate_name"],
            "aum_usd": p["aum_usd_from_holdings"],
            "mandate_status": p["mandate_status"],
            "mandate_breaches": p["mandate_breaches"],
        }
        for p in snap["portfolios"]
    ]
    return {
        "client_id": snap["client_id"],
        "as_of": snap["as_of"],
        "profile": snap["profile"],
        "portfolios": portfolios,
        "aum_usd_total": snap["aum_usd_from_holdings_all_portfolios"],
        "holdings": [
            {
                "instrument_name": h["instrument_name"],
                "asset_class": h["asset_class"],
                "sub_asset_class": h["sub_asset_class"],
                "weight_pct": h["weight_pct"],
                "market_value_usd": h["market_value_usd"],
                "liquidity_tier": h["liquidity_tier"],
                "unrealised_pnl_pct": h["unrealised_pnl_pct"],
            }
            for h in shown
        ],
        "holdings_truncated": (
            f"showing top {max_holdings} of {len(holdings)} holdings by market value"
            if len(holdings) > max_holdings else None
        ),
        "credit_facilities_count": len(snap["credit_facilities"]),
        "commitments_count": len(snap["commitments"]),
        "planned_cash_needs": [
            {"description": c["description"], "amount": c["amount"], "currency": c["currency"],
             "due_from": c["due_from"]}
            for c in snap["planned_cash_needs"]
        ],
        "notes": snap["notes"],
    }


def _condense_diff(diff: dict, max_movers: int = 8, include_events: bool = True) -> dict:
    """
    include_events=False when the caller is already fetching event_log data
    separately (both Explanation and Scenario do, in the single-shot
    design) -- events_in_window duplicated the exact same ~15 events
    verbatim, roughly half of this function's entire output size for no
    added information.
    """
    movers = diff["instrument_movers"]
    shown = movers[:max_movers]
    result = {
        "client_id": diff["client_id"],
        "from_date": diff["from_date"],
        "to_date": diff["to_date"],
        "aum_usd_from": diff["aum_usd_from"],
        "aum_usd_to": diff["aum_usd_to"],
        "change_usd": diff["change_usd"],
        "change_pct": diff["change_pct"],
        "portfolio_change": diff["portfolio_change"],
        "asset_class_change": diff["asset_class_change"],
        "instrument_movers": [
            {
                "instrument_name": m["instrument_name"],
                "asset_class": m["asset_class"],
                "change_usd": m["change_usd"],
                "quantity_unchanged": m["quantity_unchanged"],
                "approx_price_effect_usd": m["approx_price_effect_usd"],
                "approx_flow_effect_usd": m["approx_flow_effect_usd"],
                "transactions_in_window": [
                    {"transaction_type": tx["transaction_type"], "trade_date": tx["trade_date"],
                     "amount": tx["amount"], "narrative": tx["narrative"]}
                    for tx in m["transactions_in_window"]
                ],
            }
            for m in shown
        ],
        "instrument_movers_truncated": (
            f"showing top {max_movers} of {len(movers)} movers by absolute dollar change"
            if len(movers) > max_movers else None
        ),
    }

    if include_events:
        result["events_in_window"] = [
            {"event_date": e["event_date"], "event_type": e["event_type"], "severity": e["severity"],
             "region": e["region"], "description": e["description"],
             "primary_transmission": e["primary_transmission"]}
            for e in diff["events_in_window"]
        ]
        result["note"] = (
            "events_in_window is the full authoritative event list for this period. Whether an "
            "event actually affected a specific holding is for you to reason about from the "
            "holding's asset_class/sector and the event's primary_transmission -- this tool no "
            "longer pre-computes that match, so do not claim it did."
        )
    else:
        result["note"] = (
            "Event data is provided separately in this context under its own key -- cross-"
            "reference it yourself by date and by matching primary_transmission to asset "
            "class/sector, rather than expecting it duplicated here."
        )

    return result


@tool
def get_client_snapshot(client_id: str, as_of: Optional[str] = None) -> dict:
    """
    Full picture of one client at one point in time: profile (age, life
    stage, objectives, risk profile), all portfolios with AUM and mandate
    breach status, top holdings by value, and RM notes up to that date.

    Use this to understand who the client is and what they currently hold.
    Use diff_snapshots instead if the question is about what changed.
    """
    result = _safe(t.get_client_snapshot, client_id, as_of)
    return result if "error" in result else _condense_snapshot(result)


@tool
def diff_snapshots(client_id: str, from_date: str, to_date: str) -> dict:
    """
    What changed for a client between two snapshots: AUM change per
    portfolio, exposure change per asset class, and the largest
    instrument-level movers -- each split into an approximate price effect
    (the position was already held and its price moved) vs a flow effect
    (a buy/sell/capital call changed the quantity), backed by the client's
    actual transactions in that window. Also returns every event on record
    in that window (event_date, description, primary_transmission) -- you
    decide which ones plausibly reached this client's holdings by
    reasoning from asset class and the event's transmission channels, not
    from a pre-computed match.

    This is the tool for "what happened and why" -- always prefer it over
    guessing at causality yourself. from_date and to_date must both be
    exact snapshot dates and from_date must be earlier than to_date.
    """
    result = _safe(t.diff_snapshots, client_id, from_date, to_date)
    return result if "error" in result else _condense_diff(result)


@tool
def get_notes(client_id: str, as_of: Optional[str] = None) -> list:
    """
    Relationship manager notes for a client, verbatim, oldest to newest.
    These are informal and subjective, and sometimes disagree with what the
    portfolio data shows -- that disagreement is often the most important
    thing about the client, not a data error to resolve. Never paraphrase
    away what a note actually says.

    Pass as_of to only see notes written on or before that date (useful for
    reconstructing what was known at a past point in time); omit it to see
    everything up to today.
    """
    return _safe(t.get_notes, client_id, as_of)


@tool
def get_events(start_date: Optional[str] = None, end_date: Optional[str] = None,
               keyword: Optional[str] = None) -> list:
    """
    Events from event_log.csv -- the authoritative record of what happened
    in the world in 2026 that could plausibly reach a portfolio. This is
    the ONLY source of truth for 2026 market/geopolitical events: never use
    your own knowledge of what happened in 2026, and if this tool
    disagrees with what you think you know, this tool wins.

    start_date/end_date filter by event_date (inclusive); keyword does a
    substring match against the event description, region and transmission
    channels (e.g. keyword='energy').
    """
    return _safe(t.get_events, start_date, end_date, keyword)


@tool
def get_market_context(from_date: Optional[str] = None, to_date: Optional[str] = None,
                        series_ids: Optional[list[str]] = None) -> dict:
    """
    The actual market levels (US Treasury 2y/10y yields, fed funds, CPI,
    gold, Brent, TTF gas, equity indices, FX pairs, VIX) at two snapshot
    dates, with the change over that window. Use this every time you claim
    a market move caused a portfolio effect -- e.g. before saying "yields
    rose", check this tool for the actual from/to yield rather than
    stating a remembered or estimated figure. Series IDs include
    UST_10Y_PCT, UST_2Y_PCT, FED_FUNDS_UPPER_PCT, US_CPI_YOY_PCT,
    GOLD_USD_OZ, BRENT_USD_BBL, VIX, SPX, HSI, and the USDxxx/EURUSD/GBPUSD
    FX pairs. Omit series_ids to get all of them; from_date/to_date default
    to the full available range if omitted.

    Each series in the result has BOTH `change` (the raw unit move, e.g.
    "+31.6" for a Brent move in USD/barrel -- NOT a percentage) and
    `change_pct` (the percentage move, already computed -- use this one
    whenever you write "X%", never divide `change` by anything yourself or
    treat `change` as a percentage).
    """
    return _safe(t.get_market_context, from_date, to_date, series_ids)


@tool
def check_mandate_breach(portfolio_id: str, as_of: Optional[str] = None) -> dict:
    """
    Whether a portfolio's actual allocation breaches its mandate's
    min/max bands per asset class, and whether any single position exceeds
    the mandate's concentration limit. Custody portfolios return
    status='not_applicable' -- they are not managed by the bank and have no
    mandate to breach; do not describe a custody account as "in breach".
    """
    return _safe(t.check_mandate_breach, portfolio_id, as_of)


@tool
def get_liquidity_map(client_id: str, as_of: Optional[str] = None, horizon_days: int = 365) -> dict:
    """
    What a client holds by liquidity tier (Daily/Weekly/Monthly/Quarterly
    Gate/Illiquid) and how much of the portfolio is actually sellable,
    set against known planned cash needs, uncalled private-fund
    commitments, and available Lombard credit-facility headroom as an
    alternative to selling. horizon_days sets the "near-term" window for
    cash needs, default 365.
    """
    return _safe(t.get_liquidity_map, client_id, as_of, horizon_days)


@tool
def get_lookthrough_exposure(client_id: str, as_of: Optional[str] = None) -> dict:
    """
    Candidate concentration groupings across a client's holdings, found by
    matching instrument names and structured-product underlying_reference
    text (e.g. a stock, a bond, and an accumulator all referencing the same
    company). This is a heuristic text match, not a confirmed issuer
    cross-reference -- present it as "worth checking", not as fact.
    """
    return _safe(t.get_lookthrough_exposure, client_id, as_of)


@tool
def list_clients(as_of: Optional[str] = None) -> list:
    """
    One row per client across the whole book: AUM, risk profile, and quick
    flags for mandate breach, LTV breach, and an upcoming cash need within
    90 days. Use this for book-wide/prioritisation questions, not for
    single-client detail.
    """
    return _safe(t.list_clients, as_of)


ALL_TOOLS = [
    get_client_snapshot,
    diff_snapshots,
    get_notes,
    get_events,
    get_market_context,
    check_mandate_breach,
    get_liquidity_map,
    get_lookthrough_exposure,
    list_clients,
]

EXPLANATION_TOOLS = [get_client_snapshot, diff_snapshots, get_notes, get_events, get_market_context]

# get_lookthrough_exposure resolves the FCN's worst-of basket to named
# instruments/companies; get_notes carries the client's own stated view and
# the RM's open question ("we have not modelled this"); get_market_context
# grounds any Brent/shipping-rate claim in real numbers rather than a guess.
SCENARIO_TOOLS = [get_client_snapshot, get_lookthrough_exposure, get_events, get_market_context, get_notes]

# check_mandate_breach and get_liquidity_map are the two deterministic risk
# panels already on the dashboard for every client -- the Recommendation
# Agent grounds its proposals in the same numbers a human reading the
# dashboard would see, not a separate calculation. get_market_context is
# here because a real run cited "1 USD = 7.8 HKD" for an HKD cash-need
# conversion with no tool call behind it (the real rate that day was 7.81)
# -- the same unsourced-market-figure bug already fixed once for the
# Explanation Agent, now closed here too.
RECOMMENDATION_TOOLS = [get_client_snapshot, get_lookthrough_exposure, get_liquidity_map,
                        check_mandate_breach, get_notes, get_market_context]

# Append the snapshot-dates reminder to every tool that takes an as_of/date
# argument, now that each is a real StructuredTool with a working .description.
for _t in (get_client_snapshot, diff_snapshots, get_market_context, check_mandate_breach,
           get_liquidity_map, get_lookthrough_exposure, list_clients):
    _t.description = (_t.description or "") + _SNAPSHOT_HELP
