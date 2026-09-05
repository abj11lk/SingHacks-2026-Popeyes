"""
Shared client-context tool layer -- the engine.

Every agent (Explanation, Concentration/Look-through, Liquidity & Collateral,
Scenario/Stress-Test, Recommendation, Prioritisation) reads client data
through these functions rather than touching the CSVs or the DB directly.
That keeps retrieval consistent, keeps the "as of which snapshot" logic in
one place, and means every number an agent uses can be traced back to a
table + row.

These are plain Python functions on purpose -- no framework dependency here.
The dashboard backend, a notebook, a test, and the LangGraph agent layer
(see langchain_tools.py, which wraps these with @tool for the LLM) all call
the exact same code path, so there's one place to fix a bug, not three.

Design rules followed throughout:
  - Never silently fabricate. If a value cannot be computed from the data,
    say so (`None` + a note) rather than guessing.
  - Every returned dict carries a `sources` block: which tables/files and
    which keys were read to produce it. An agent (or a reviewer) can always
    ask "where did that number come from".
  - Heuristic groupings (e.g. look-through name-matching) are always labelled
    as heuristic, never asserted as fact.
"""
import math
import re

import pandas as pd

from . import db
from .db import SNAPSHOT_DATES, TODAY, resolve_snapshot_date

pd.set_option("future.no_silent_downcasting", True)


# ---------------------------------------------------------------------------
# small internal helpers
# ---------------------------------------------------------------------------

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """NaN -> None so the result is JSON-safe, without touching numeric semantics."""
    return df.astype(object).where(pd.notnull(df), None)


def _records(df: pd.DataFrame) -> list:
    return _clean(df).to_dict(orient="records")


def _require_client(client_id: str) -> dict:
    row = db.query("SELECT * FROM clients WHERE client_id = ?", (client_id,))
    if row.empty:
        raise ValueError(f"Unknown client_id: {client_id}")
    return _records(row)[0]


def _require_portfolio(portfolio_id: str) -> dict:
    row = db.query("SELECT * FROM portfolios WHERE portfolio_id = ?", (portfolio_id,))
    if row.empty:
        raise ValueError(f"Unknown portfolio_id: {portfolio_id}")
    return _records(row)[0]


def _pct(part, whole):
    if whole in (0, None) or part is None or (isinstance(whole, float) and math.isclose(whole, 0)):
        return None
    return 100.0 * part / whole


# ---------------------------------------------------------------------------
# 1. get_client_snapshot
# ---------------------------------------------------------------------------

def get_client_snapshot(client_id: str, as_of: str | None = None) -> dict:
    """
    Full picture of a client at one point in time: profile, portfolios,
    holdings, mandate status per portfolio, credit facilities, commitments
    and planned cash needs, plus RM notes up to that date.

    This is the "what does the portfolio look like" tool. Pair it with
    diff_snapshots() for "what happened".
    """
    as_of = resolve_snapshot_date(as_of)
    client = _require_client(client_id)

    portfolios = _records(db.query(
        "SELECT * FROM portfolios WHERE client_id = ?", (client_id,)
    ))

    holdings = _records(db.query(
        "SELECT * FROM holdings WHERE client_id = ? AND snapshot_date = ? "
        "ORDER BY market_value_usd DESC",
        (client_id, as_of),
    ))

    aum_usd_from_holdings = sum(h["market_value_usd"] for h in holdings)

    date_cols = [f"aum_{d}" for d in SNAPSHOT_DATES]
    for p in portfolios:
        p["aum_local_official"] = p.get(f"aum_{as_of}")
        p["aum_usd_from_holdings"] = round(
            sum(h["market_value_usd"] for h in holdings if h["portfolio_id"] == p["portfolio_id"]), 2
        )
        for col in date_cols:
            p.pop(col, None)

        breach = check_mandate_breach(p["portfolio_id"], as_of=as_of)
        p["mandate_status"] = breach["status"]
        p["mandate_breaches"] = breach.get("asset_class_breaches", []) + breach.get(
            "single_position_breaches", []
        )

    facilities = get_facility_status(client_id, as_of=as_of)
    commitments = _records(db.query(
        "SELECT * FROM commitments WHERE client_id = ?", (client_id,)
    ))
    cash_needs = _records(db.query(
        "SELECT * FROM planned_cash_needs WHERE client_id = ?", (client_id,)
    ))
    notes = get_notes(client_id, as_of=as_of)

    return {
        "client_id": client_id,
        "as_of": as_of,
        "profile": client,
        "portfolios": portfolios,
        "aum_usd_from_holdings_all_portfolios": round(aum_usd_from_holdings, 2),
        "aum_usd_client_record": client.get("total_aum_usd"),
        "holdings": holdings,
        "credit_facilities": facilities,
        "commitments": commitments,
        "planned_cash_needs": cash_needs,
        "notes": notes,
        "sources": {
            "clients.csv": [client_id],
            "portfolios.csv": [p["portfolio_id"] for p in portfolios],
            "holdings.csv": f"{len(holdings)} rows at snapshot_date={as_of}",
            "credit_facilities.csv": [f["facility_id"] for f in facilities],
            "commitments.csv": [c["commitment_id"] for c in commitments],
            "planned_cash_needs.csv": [c["need_id"] for c in cash_needs],
            "rm_notes.json": [n["note_id"] for n in notes],
        },
    }


def get_facility_status(client_id: str, as_of: str | None = None) -> list:
    """Credit facilities for a client, with the wide per-date columns resolved to `as_of`."""
    as_of = resolve_snapshot_date(as_of)
    raw = _records(db.query("SELECT * FROM credit_facilities WHERE client_id = ?", (client_id,)))
    out = []
    for f in raw:
        drawn = f.get(f"drawn_{as_of}")
        collateral_mv = f.get(f"collateral_market_value_{as_of}")
        lending_value = f.get(f"lending_value_{as_of}")
        ltv = f.get(f"ltv_pct_{as_of}")
        headroom = f.get(f"headroom_{as_of}")
        trigger = f.get("margin_call_ltv_pct")
        out.append({
            "facility_id": f["facility_id"],
            "client_id": f["client_id"],
            "collateral_portfolio_id": f["collateral_portfolio_id"],
            "facility_type": f["facility_type"],
            "facility_ccy": f["facility_ccy"],
            "credit_limit": f["credit_limit"],
            "interest_rate_pct": f["interest_rate_pct"],
            "margin_call_ltv_pct": trigger,
            "as_of": as_of,
            "drawn": drawn,
            "collateral_market_value": collateral_mv,
            "lending_value": lending_value,
            "ltv_pct": ltv,
            "headroom": headroom,
            "breach": (ltv is not None and trigger is not None and ltv >= trigger),
        })
    return out


# ---------------------------------------------------------------------------
# 2. diff_snapshots
# ---------------------------------------------------------------------------

def diff_snapshots(client_id: str, from_date: str, to_date: str) -> dict:
    """
    What changed for a client between two snapshots, decomposed into:
      - portfolio-level AUM change
      - asset-class level exposure change
      - instrument-level movers, each split into a price effect (the position
        was already held and its price moved) vs a flow effect (a buy/sell/
        capital call changed the quantity held) using the client's actual
        transactions in that window
      - the events on record in that window, with a *candidate* (heuristic,
        not asserted) list of which of the client's holdings each event's
        transmission channels might touch

    This is the core "explain what happened" tool.
    """
    from_date = resolve_snapshot_date(from_date)
    to_date = resolve_snapshot_date(to_date)
    if db.snapshot_index(from_date) >= db.snapshot_index(to_date):
        raise ValueError("from_date must be an earlier snapshot than to_date")

    _require_client(client_id)

    h_from = db.query(
        "SELECT * FROM holdings WHERE client_id = ? AND snapshot_date = ?", (client_id, from_date)
    )
    h_to = db.query(
        "SELECT * FROM holdings WHERE client_id = ? AND snapshot_date = ?", (client_id, to_date)
    )

    aum_from = round(h_from["market_value_usd"].sum(), 2)
    aum_to = round(h_to["market_value_usd"].sum(), 2)

    # --- portfolio level ---
    by_pf_from = h_from.groupby("portfolio_id")["market_value_usd"].sum()
    by_pf_to = h_to.groupby("portfolio_id")["market_value_usd"].sum()
    portfolio_ids = sorted(set(by_pf_from.index) | set(by_pf_to.index))
    portfolio_change = []
    for pid in portfolio_ids:
        v_from = float(by_pf_from.get(pid, 0.0))
        v_to = float(by_pf_to.get(pid, 0.0))
        portfolio_change.append({
            "portfolio_id": pid,
            "aum_usd_from": round(v_from, 2),
            "aum_usd_to": round(v_to, 2),
            "change_usd": round(v_to - v_from, 2),
            "change_pct": _pct(v_to - v_from, v_from),
        })

    # --- asset class level ---
    ac_from = h_from.groupby("asset_class")["market_value_usd"].sum()
    ac_to = h_to.groupby("asset_class")["market_value_usd"].sum()
    asset_classes = sorted(set(ac_from.index) | set(ac_to.index))
    asset_class_change = []
    for ac in asset_classes:
        v_from = float(ac_from.get(ac, 0.0))
        v_to = float(ac_to.get(ac, 0.0))
        asset_class_change.append({
            "asset_class": ac,
            "market_value_usd_from": round(v_from, 2),
            "market_value_usd_to": round(v_to, 2),
            "change_usd": round(v_to - v_from, 2),
            "change_pct": round(_pct(v_to - v_from, v_from), 2) if v_from else None,
            "weight_pct_from": round(_pct(v_from, aum_from), 2) if aum_from else None,
            "weight_pct_to": round(_pct(v_to, aum_to), 2) if aum_to else None,
        })
    asset_class_change.sort(key=lambda r: abs(r["change_usd"]), reverse=True)

    # --- instrument-level movers with price/flow decomposition ---
    key_cols = ["portfolio_id", "instrument_id"]
    merged = pd.merge(
        h_from[key_cols + ["instrument_name", "asset_class", "quantity", "price_local",
                            "instrument_ccy", "market_value_usd"]],
        h_to[key_cols + ["instrument_name", "asset_class", "quantity", "price_local",
                          "instrument_ccy", "market_value_usd"]],
        on=key_cols, how="outer", suffixes=("_from", "_to"),
    )

    txns = db.query(
        "SELECT * FROM transactions WHERE client_id = ? AND trade_date > ? AND trade_date <= ? "
        "ORDER BY trade_date",
        (client_id, from_date, to_date),
    )

    movers = []
    for _, r in merged.iterrows():
        mv_from = r["market_value_usd_from"] if pd.notnull(r["market_value_usd_from"]) else 0.0
        mv_to = r["market_value_usd_to"] if pd.notnull(r["market_value_usd_to"]) else 0.0
        change = mv_to - mv_from
        if abs(change) < 1:
            continue

        qty_from = r["quantity_from"] if pd.notnull(r["quantity_from"]) else 0.0
        qty_to = r["quantity_to"] if pd.notnull(r["quantity_to"]) else 0.0
        price_from = r["price_local_from"] if pd.notnull(r["price_local_from"]) else None
        price_to = r["price_local_to"] if pd.notnull(r["price_local_to"]) else None
        name = r["instrument_name_to"] if pd.notnull(r["instrument_name_to"]) else r["instrument_name_from"]
        asset_class = r["asset_class_to"] if pd.notnull(r["asset_class_to"]) else r["asset_class_from"]

        # Rough decomposition: hold quantity fixed at the earlier of the two to
        # isolate the pure price effect, attribute the rest to flows (trades).
        price_effect_usd = None
        if price_from is not None and price_to is not None and qty_from:
            local_return_pct = _pct(price_to - price_from, price_from)
            # scale the price return onto the *from* USD value as an approximation
            # (assumes FX and price move together in market_value_usd terms).
            price_effect_usd = round(mv_from * (local_return_pct / 100.0), 2) if local_return_pct is not None else None

        flow_effect_usd = round(change - price_effect_usd, 2) if price_effect_usd is not None else None

        instrument_txns = txns[
            (txns.portfolio_id == r["portfolio_id"]) & (txns.instrument_id == r["instrument_id"])
        ]

        movers.append({
            "portfolio_id": r["portfolio_id"],
            "instrument_id": r["instrument_id"],
            "instrument_name": name,
            "asset_class": asset_class,
            "market_value_usd_from": round(mv_from, 2),
            "market_value_usd_to": round(mv_to, 2),
            "change_usd": round(change, 2),
            "quantity_from": qty_from,
            "quantity_to": qty_to,
            "quantity_unchanged": math.isclose(qty_from, qty_to, rel_tol=1e-9),
            "price_local_from": price_from,
            "price_local_to": price_to,
            "approx_price_effect_usd": price_effect_usd,
            "approx_flow_effect_usd": flow_effect_usd,
            "transactions_in_window": _records(instrument_txns),
        })
    movers.sort(key=lambda r: abs(r["change_usd"]), reverse=True)

    # --- events in window, with candidate (heuristic) relevance ---
    events = db.query(
        "SELECT * FROM event_log WHERE event_date > ? AND event_date <= ? ORDER BY event_date",
        (from_date, to_date),
    )
    held_terms = set()
    for col in ("asset_class", "sub_asset_class", "sector", "instrument_name"):
        held_terms |= set(h_to[col].dropna().str.lower().unique())
    events_out = []
    for _, e in events.iterrows():
        transmission_terms = [t.strip().lower() for t in str(e["primary_transmission"]).split(",")]
        candidate_holdings = sorted({
            term_held for term_held in held_terms
            if any(t and t in term_held for t in transmission_terms)
        })
        events_out.append({
            "event_date": e["event_date"],
            "event_type": e["event_type"],
            "region": e["region"],
            "description": e["description"],
            "primary_transmission": e["primary_transmission"],
            "severity": e["severity"],
            "candidate_related_holdings_heuristic": candidate_holdings,
        })

    return {
        "client_id": client_id,
        "from_date": from_date,
        "to_date": to_date,
        "aum_usd_from": aum_from,
        "aum_usd_to": aum_to,
        "change_usd": round(aum_to - aum_from, 2),
        "change_pct": _pct(aum_to - aum_from, aum_from),
        "portfolio_change": portfolio_change,
        "asset_class_change": asset_class_change,
        "instrument_movers": movers,
        "events_in_window": events_out,
        "sources": {
            "holdings.csv": f"snapshot_date in ({from_date}, {to_date})",
            "transactions.csv": f"{len(txns)} rows, trade_date in ({from_date}, {to_date}]",
            "event_log.csv": f"{len(events_out)} rows, event_date in ({from_date}, {to_date}]",
        },
        "caveats": [
            "approx_price_effect_usd / approx_flow_effect_usd are an approximate decomposition "
            "(quantity held at the earlier date, local price return applied to the earlier USD "
            "value) -- treat as directional, not exact, and prefer transactions_in_window for the "
            "authoritative record of what was bought or sold.",
            "candidate_related_holdings_heuristic is keyword matching against "
            "event_log.primary_transmission, not a confirmed causal link. An agent citing this "
            "must present it as a hypothesis to check, not a fact.",
        ],
    }


# ---------------------------------------------------------------------------
# 3. get_notes
# ---------------------------------------------------------------------------

def get_notes(client_id: str, as_of: str | None = None) -> list:
    """RM notes for a client, verbatim, sorted oldest to newest. Never paraphrased here."""
    _require_client(client_id)
    if as_of is None:
        rows = db.query(
            "SELECT * FROM rm_notes WHERE client_id = ? ORDER BY note_date", (client_id,)
        )
    else:
        as_of = resolve_snapshot_date(as_of)
        rows = db.query(
            "SELECT * FROM rm_notes WHERE client_id = ? AND note_date <= ? ORDER BY note_date",
            (client_id, as_of),
        )
    return _records(rows)


# ---------------------------------------------------------------------------
# 4. get_events
# ---------------------------------------------------------------------------

def get_events(start_date: str | None = None, end_date: str | None = None,
               keyword: str | None = None) -> list:
    """
    Events from event_log.csv, verbatim -- the authoritative record of what
    happened in 2026. Never substitute model knowledge for this table.
    """
    sql = "SELECT * FROM event_log WHERE 1=1"
    params = []
    if start_date:
        sql += " AND event_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND event_date <= ?"
        params.append(end_date)
    sql += " ORDER BY event_date"
    rows = db.query(sql, tuple(params))
    if keyword:
        kw = keyword.lower()
        mask = (
            rows["description"].str.lower().str.contains(kw)
            | rows["primary_transmission"].str.lower().str.contains(kw)
            | rows["region"].str.lower().str.contains(kw)
        )
        rows = rows[mask]
    return _records(rows)


# ---------------------------------------------------------------------------
# bonus: market context -- the actual numbers behind an event
# ---------------------------------------------------------------------------

def get_market_context(from_date: str | None = None, to_date: str | None = None,
                        series_ids: list[str] | None = None) -> dict:
    """
    Market levels (Treasury yields, gold, Brent, FX, equity indices, VIX,
    CPI, fed funds) at two snapshot dates, with the change over that
    window. Exists so a causal claim like "yields rose, so the bond fell"
    can be backed by the actual yield move instead of an assumed or
    remembered figure -- event_log.csv says an event happened; this tool
    says by how much the market actually moved.

    Omit series_ids for every series; pass a list (e.g. ['UST_10Y_PCT',
    'GOLD_USD_OZ']) to narrow it down. from_date/to_date default to the
    first and last snapshot if omitted.
    """
    from_date = resolve_snapshot_date(from_date) if from_date else SNAPSHOT_DATES[0]
    to_date = resolve_snapshot_date(to_date) if to_date else TODAY

    sql = "SELECT * FROM market_context WHERE snapshot_date IN (?, ?)"
    params = [from_date, to_date]
    if series_ids:
        placeholders = ",".join("?" * len(series_ids))
        sql += f" AND series_id IN ({placeholders})"
        params += series_ids
    rows = db.query(sql, tuple(params))

    by_series = {}
    for _, r in rows.iterrows():
        entry = by_series.setdefault(r["series_id"], {
            "series_id": r["series_id"], "series_name": r["series_name"],
            "category": r["category"], "unit": r["unit"],
            "value_from": None, "value_to": None,
        })
        if r["snapshot_date"] == from_date:
            entry["value_from"] = float(r["value"])
        if r["snapshot_date"] == to_date:
            entry["value_to"] = float(r["value"])

    series = []
    for entry in by_series.values():
        vf, vt = entry["value_from"], entry["value_to"]
        entry["change"] = round(vt - vf, 4) if vf is not None and vt is not None else None
        entry["change_pct"] = round(_pct(vt - vf, vf), 2) if vf and vt is not None else None
        series.append(entry)
    series.sort(key=lambda s: (s["category"], s["series_id"]))

    return {
        "from_date": from_date,
        "to_date": to_date,
        "series": series,
        "sources": {"market_context.csv": f"snapshot_date in ({from_date}, {to_date})"},
    }


# ---------------------------------------------------------------------------
# 5. check_mandate_breach
# ---------------------------------------------------------------------------

def check_mandate_breach(portfolio_id: str, as_of: str | None = None) -> dict:
    """
    Compares a portfolio's actual allocation against its mandate's
    min/target/max bands per asset class, and flags single-position
    concentration breaches (only for instruments where
    concentration_limit_applies == 'Y', per the data dictionary -- the limit
    is not meant to apply to diversified funds, sovereigns or deposits).

    Custody portfolios are not measured against a mandate (data dictionary);
    this returns status="not_applicable" for them rather than fabricating a
    breach check that does not exist in the bank's own governance model.
    """
    as_of = resolve_snapshot_date(as_of)
    portfolio = _require_portfolio(portfolio_id)

    if portfolio["service_model"] == "Custody":
        return {
            "portfolio_id": portfolio_id,
            "as_of": as_of,
            "status": "not_applicable",
            "reason": "Custody accounts are not managed by the bank and are not measured against a mandate.",
        }

    mandate_code = portfolio["mandate_code"]
    bands = db.query("SELECT * FROM mandates WHERE mandate_code = ?", (mandate_code,))
    if bands.empty:
        return {
            "portfolio_id": portfolio_id,
            "as_of": as_of,
            "status": "unknown",
            "reason": f"No mandate bands found for mandate_code={mandate_code}",
        }
    max_single_position_pct = float(bands.iloc[0]["max_single_position_pct"])

    holdings = db.query(
        "SELECT h.*, i.concentration_limit_applies FROM holdings h "
        "JOIN instruments i ON h.instrument_id = i.instrument_id "
        "WHERE h.portfolio_id = ? AND h.snapshot_date = ?",
        (portfolio_id, as_of),
    )
    total = holdings["market_value_usd"].sum()

    by_ac = holdings.groupby("asset_class")["market_value_usd"].sum()
    asset_class_detail = []
    asset_class_breaches = []
    for _, band in bands.iterrows():
        ac = band["asset_class"]
        min_pct = float(band["min_pct"])
        target_pct = float(band["target_pct"])
        max_pct = float(band["max_pct"])
        value = float(by_ac.get(ac, 0.0))
        actual_pct = _pct(value, total) or 0.0
        row = {
            "asset_class": ac,
            "actual_pct": round(actual_pct, 2),
            "min_pct": min_pct,
            "target_pct": target_pct,
            "max_pct": max_pct,
            "breach": bool(actual_pct < min_pct or actual_pct > max_pct),
            "drift_vs_target_pct": round(actual_pct - target_pct, 2),
        }
        asset_class_detail.append(row)
        if row["breach"]:
            asset_class_breaches.append(row)

    single_position_breaches = []
    for _, h in holdings.iterrows():
        if h["concentration_limit_applies"] != "Y":
            continue
        weight = float(h["weight_pct"])
        if weight > max_single_position_pct:
            single_position_breaches.append({
                "instrument_id": h["instrument_id"],
                "instrument_name": h["instrument_name"],
                "asset_class": h["asset_class"],
                "weight_pct": round(weight, 2),
                "max_single_position_pct": max_single_position_pct,
            })

    status = "breach" if (asset_class_breaches or single_position_breaches) else "within_mandate"

    return {
        "portfolio_id": portfolio_id,
        "mandate_code": mandate_code,
        "mandate_name": portfolio["mandate_name"],
        "as_of": as_of,
        "status": status,
        "asset_class_detail": asset_class_detail,
        "asset_class_breaches": asset_class_breaches,
        "single_position_breaches": single_position_breaches,
        "mandate_notes": bands.iloc[0]["mandate_notes"],
        "sources": {
            "mandates.csv": mandate_code,
            "holdings.csv": f"{len(holdings)} rows, portfolio_id={portfolio_id}, snapshot_date={as_of}",
        },
    }


# ---------------------------------------------------------------------------
# 6. get_liquidity_map
# ---------------------------------------------------------------------------

_TIER_ORDER = ["Daily", "Weekly", "Monthly", "Quarterly Gate", "Illiquid"]


def get_liquidity_map(client_id: str, as_of: str | None = None, horizon_days: int = 365) -> dict:
    """
    What a client actually holds by liquidity tier, set against known and
    expected cash outflows (planned_cash_needs + uncalled commitments) and
    available Lombard headroom as an alternative to selling.

    horizon_days controls the "near-term" window used for the coverage
    check (default one year from as_of).
    """
    as_of = resolve_snapshot_date(as_of)
    _require_client(client_id)

    holdings = db.query(
        "SELECT * FROM holdings WHERE client_id = ? AND snapshot_date = ?", (client_id, as_of)
    )
    total = holdings["market_value_usd"].sum()

    by_tier = holdings.groupby("liquidity_tier")["market_value_usd"].sum()
    tier_breakdown = []
    cumulative = 0.0
    for tier in _TIER_ORDER:
        value = float(by_tier.get(tier, 0.0))
        cumulative += value
        tier_breakdown.append({
            "liquidity_tier": tier,
            "market_value_usd": round(value, 2),
            "pct_of_portfolio": round(_pct(value, total) or 0.0, 2),
            "cumulative_sellable_usd": round(cumulative, 2),
            "cumulative_sellable_pct": round(_pct(cumulative, total) or 0.0, 2),
        })
    extra_tiers = set(by_tier.index) - set(_TIER_ORDER)
    for tier in extra_tiers:
        tier_breakdown.append({
            "liquidity_tier": tier,
            "market_value_usd": round(float(by_tier[tier]), 2),
            "note": "tier not in the expected Daily..Illiquid ordering -- check source data",
        })

    daily_usd = float(by_tier.get("Daily", 0.0))

    horizon_end = (pd.Timestamp(as_of) + pd.Timedelta(days=horizon_days)).strftime("%Y-%m-%d")
    cash_needs = _records(db.query(
        "SELECT * FROM planned_cash_needs WHERE client_id = ? AND due_from <= ? "
        "ORDER BY due_from",
        (client_id, horizon_end),
    ))
    commitments = _records(db.query("SELECT * FROM commitments WHERE client_id = ?", (client_id,)))
    facilities = get_facility_status(client_id, as_of=as_of)
    total_headroom = sum(f["headroom"] for f in facilities if f["headroom"] is not None)

    near_term_needs_usd = sum(
        n["amount"] for n in cash_needs if n.get("currency") == "USD"
    )
    non_usd_needs = [n for n in cash_needs if n.get("currency") != "USD"]

    return {
        "client_id": client_id,
        "as_of": as_of,
        "total_market_value_usd": round(total, 2),
        "tier_breakdown": tier_breakdown,
        "daily_liquid_usd": round(daily_usd, 2),
        "credit_facility_headroom_usd": round(total_headroom, 2),
        "near_term_cash_needs_usd_only": round(near_term_needs_usd, 2),
        "near_term_cash_needs_other_ccy": non_usd_needs,
        "planned_cash_needs_in_horizon": cash_needs,
        "commitments": commitments,
        "horizon_days": horizon_days,
        "caveats": [
            "near_term_cash_needs_usd_only sums only USD-denominated needs; "
            "near_term_cash_needs_other_ccy is listed separately rather than FX-converted, "
            "to avoid silently picking an FX rate on the RM's behalf.",
            "commitments.uncalled is a potential future outflow with a call timing given by "
            "expected_call_window (free text) rather than a hard date -- read it, don't just sum it.",
        ],
        "sources": {
            "holdings.csv": f"{len(holdings)} rows, client_id={client_id}, snapshot_date={as_of}",
            "planned_cash_needs.csv": [n["need_id"] for n in cash_needs],
            "commitments.csv": [c["commitment_id"] for c in commitments],
            "credit_facilities.csv": [f["facility_id"] for f in facilities],
        },
    }


# ---------------------------------------------------------------------------
# bonus: look-through / concentration helper
# ---------------------------------------------------------------------------

# Generic asset-class/product vocabulary that appears across many unrelated
# instruments (an equity fund and a bond fund and a private credit fund are
# not "the same theme" just because they share the word "fund" or "credit")
# -- added after get_lookthrough_exposure was found chaining unrelated
# holdings together this way (see tools_lookthrough fix notes). Genuine
# issuer/company names (golden, harbour, helios, pacific, orient, shipping,
# bara, nusantara) are deliberately NOT in this list -- those are exactly
# the words that should keep linking a company's stock to a bond or note
# that references it.
_STOPWORDS = {
    "ltd", "the", "of", "fund", "note", "ref", "and", "a", "an", "properties",
    "equity", "global", "developed", "grade", "investment", "corporate",
    "credit", "energy", "majors", "bond", "fixed", "income", "market",
    "private", "short", "long", "index", "infrastructure", "inc", "corp",
    "tbk", "kk", "ab", "pte", "plc",
}


def _significant_words(text: str) -> set:
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def get_lookthrough_exposure(client_id: str, as_of: str | None = None) -> dict:
    """
    Groups a client's holdings by shared name-references -- e.g. a single
    stock, a subordinated perpetual issued by the same company, and an
    accumulator or FCN that references it -- to surface concentration that is
    invisible position-by-position but obvious once you look through the
    wrapper.

    This is text-matching on instrument_name and instruments.underlying_reference,
    not a security master cross-reference. It is a *candidate* grouping for a
    human (or a downstream agent) to confirm, not a definitive look-through --
    labelled as such throughout.
    """
    as_of = resolve_snapshot_date(as_of)
    _require_client(client_id)

    holdings = db.query(
        "SELECT h.*, i.underlying_reference FROM holdings h "
        "JOIN instruments i ON h.instrument_id = i.instrument_id "
        "WHERE h.client_id = ? AND h.snapshot_date = ?",
        (client_id, as_of),
    )
    total = holdings["market_value_usd"].sum()
    client = _require_client(client_id)
    sow_words = _significant_words(client.get("source_of_wealth") or "")

    rows = []
    for _, h in holdings.iterrows():
        name_words = _significant_words(h["instrument_name"])
        underlying = "" if pd.isna(h["underlying_reference"]) else h["underlying_reference"]
        underlying_words = _significant_words(underlying)
        rows.append({
            "instrument_id": h["instrument_id"],
            "instrument_name": h["instrument_name"],
            "asset_class": h["asset_class"],
            "market_value_usd": float(h["market_value_usd"]),
            "weight_pct": float(h["weight_pct"]),
            "underlying_reference": underlying or None,
            "name_words": name_words,
            "underlying_words": underlying_words,
            "overlaps_source_of_wealth": bool(name_words & sow_words) or bool(underlying_words & sow_words),
        })

    # union holdings that share at least 2 significant words -- naive
    # clustering, fine at this scale (a handful of holdings per client). A
    # single shared word isn't enough evidence of the same issuer (e.g.
    # "Pacific Rim Bank" and "Pacific Orient Shipping" share only "pacific"
    # and are unrelated companies); two shared words reliably catches a
    # company's stock/bond/note ("golden" + "harbour") without also
    # catching same-asset-class coincidences.
    MIN_SHARED_WORDS = 2
    clusters = []
    used = [False] * len(rows)
    for i, r in enumerate(rows):
        if used[i]:
            continue
        cluster = [r]
        used[i] = True
        tokens = set(r["name_words"]) | set(r["underlying_words"])
        changed = True
        while changed:
            changed = False
            for j, r2 in enumerate(rows):
                if used[j]:
                    continue
                r2_tokens = set(r2["name_words"]) | set(r2["underlying_words"])
                if len(tokens & r2_tokens) >= MIN_SHARED_WORDS:
                    cluster.append(r2)
                    used[j] = True
                    tokens |= r2_tokens
                    changed = True
        if len(cluster) > 1:
            clusters.append(cluster)

    theme_summary = []
    for cluster in clusters:
        cluster_value = sum(c["market_value_usd"] for c in cluster)
        label_words = set()
        for c in cluster:
            label_words |= c["name_words"]
        theme_summary.append({
            "label_guess": " ".join(sorted(label_words))[:60],
            "instruments": [
                {"instrument_id": c["instrument_id"], "instrument_name": c["instrument_name"],
                 "asset_class": c["asset_class"], "weight_pct": round(c["weight_pct"], 2)}
                for c in cluster
            ],
            "combined_market_value_usd": round(cluster_value, 2),
            "combined_pct_of_client_aum": round(_pct(cluster_value, total) or 0.0, 2),
        })
    theme_summary.sort(key=lambda t: t["combined_market_value_usd"], reverse=True)

    return {
        "client_id": client_id,
        "as_of": as_of,
        "total_market_value_usd": round(total, 2),
        "candidate_concentration_themes": theme_summary,
        "holdings_overlapping_source_of_wealth": [
            {"instrument_id": r["instrument_id"], "instrument_name": r["instrument_name"],
             "weight_pct": round(r["weight_pct"], 2)}
            for r in rows if r["overlaps_source_of_wealth"]
        ],
        "source_of_wealth": client.get("source_of_wealth"),
        "caveats": [
            "candidate_concentration_themes is derived by keyword-matching instrument names and "
            "underlying_reference text, not a confirmed issuer/entity cross-reference -- verify "
            "before presenting to a client.",
        ],
        "sources": {
            "holdings.csv": f"{len(holdings)} rows, client_id={client_id}, snapshot_date={as_of}",
            "instruments.csv": "underlying_reference column",
            "clients.csv": f"source_of_wealth, client_id={client_id}",
        },
    }


# ---------------------------------------------------------------------------
# bonus: book-wide view for the dashboard / prioritisation agent
# ---------------------------------------------------------------------------

def list_clients(as_of: str | None = None) -> list:
    """One row per client: AUM (from holdings, at as_of), quick risk flags. For the book overview."""
    as_of = resolve_snapshot_date(as_of)
    clients = db.query("SELECT * FROM clients ORDER BY total_aum_usd DESC")
    holdings = db.query("SELECT * FROM holdings WHERE snapshot_date = ?", (as_of,))
    portfolios = db.query("SELECT * FROM portfolios")
    facilities_raw = db.query("SELECT * FROM credit_facilities")
    cash_needs = db.query("SELECT * FROM planned_cash_needs")

    aum_by_client = holdings.groupby("client_id")["market_value_usd"].sum()

    out = []
    for _, c in clients.iterrows():
        cid = c["client_id"]
        client_portfolios = portfolios[portfolios.client_id == cid]
        any_breach = False
        for pid in client_portfolios["portfolio_id"]:
            breach = check_mandate_breach(pid, as_of=as_of)
            if breach["status"] == "breach":
                any_breach = True
                break

        client_facilities = facilities_raw[facilities_raw.client_id == cid]
        ltv_breach = False
        for _, f in client_facilities.iterrows():
            ltv = f.get(f"ltv_pct_{as_of}")
            trigger = f.get("margin_call_ltv_pct")
            if ltv is not None and trigger is not None and ltv >= trigger:
                ltv_breach = True
                break

        horizon_end = (pd.Timestamp(as_of) + pd.Timedelta(days=90)).strftime("%Y-%m-%d")
        upcoming_needs = cash_needs[
            (cash_needs.client_id == cid) & (cash_needs.due_from <= horizon_end)
        ]

        out.append({
            "client_id": cid,
            "client_name": c["client_name"],
            "wealth_band": c["wealth_band"],
            "risk_profile": c["risk_profile"],
            "booking_centre": c["booking_centre"],
            "aum_usd_from_holdings": round(float(aum_by_client.get(cid, 0.0)), 2),
            "aum_usd_client_record": c["total_aum_usd"],
            "kyc_review_due": c["kyc_review_due"],
            "mandate_breach_flag": any_breach,
            "ltv_breach_flag": ltv_breach,
            "upcoming_cash_need_90d_flag": len(upcoming_needs) > 0,
        })
    return out


# ---------------------------------------------------------------------------
# escape hatch: raw SQL, read-only
# ---------------------------------------------------------------------------

def run_sql(sql: str, params: tuple = ()) -> list:
    """
    Read-only SQL access to the underlying tables, for questions the named
    tools above don't cover. SELECT/WITH only -- rejects anything else so an
    agent can't be tricked into mutating the in-memory DB.
    """
    stripped = sql.strip().lower()
    if not (stripped.startswith("select") or stripped.startswith("with")):
        raise ValueError("run_sql only accepts SELECT/WITH statements")
    return _records(db.query(sql, params))
