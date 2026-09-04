"""
Self-test / checkpoint for the tool layer (step 1).

Not a test suite -- a readable smoke test, in the spirit of
singhacks-jb-wealth-intelligence/starter/quickstart.py, that exercises every
tool function against the three clients we're going deep on, so we can see
the shape of the output before any agent or UI touches it.

Run from the repo root:  python check_tools.py
"""
import json

from backend import tools
from backend.db import SNAPSHOT_DATES, TODAY

FOCAL = ["CL-0012", "CL-0019", "CL-0014"]


def section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def show(label, obj):
    print(f"\n--- {label} ---")
    print(json.dumps(obj, indent=2, default=str)[:2000])


section(f"BOOK OVERVIEW  (as of {TODAY})")
book = tools.list_clients()
print(f"{'ID':<9}{'Name':<24}{'AUM USDm':>9}  {'Mandate':<8}{'LTV':<6}{'CashNeed90d'}")
for c in book:
    print(f"{c['client_id']:<9}{c['client_name'][:22]:<24}"
          f"{c['aum_usd_from_holdings']/1e6:>9.1f}  "
          f"{'BREACH' if c['mandate_breach_flag'] else 'ok':<8}"
          f"{'BREACH' if c['ltv_breach_flag'] else 'ok':<6}"
          f"{'YES' if c['upcoming_cash_need_90d_flag'] else ''}")

for cid in FOCAL:
    section(f"{cid}  --  get_client_snapshot (today)")
    snap = tools.get_client_snapshot(cid)
    print(f"Client: {snap['profile']['client_name']}  |  "
          f"AUM (holdings): {snap['aum_usd_from_holdings_all_portfolios']:,.0f}  |  "
          f"AUM (client record): {snap['aum_usd_client_record']:,.0f}")
    for p in snap["portfolios"]:
        print(f"  {p['portfolio_id']}  {p['portfolio_name']:<32} "
              f"{p['service_model']:<12} mandate={p['mandate_status']}")
        for b in p["mandate_breaches"]:
            print(f"      BREACH: {b}")
    print(f"  Facilities: {len(snap['credit_facilities'])}  "
          f"Commitments: {len(snap['commitments'])}  "
          f"Cash needs: {len(snap['planned_cash_needs'])}  "
          f"Notes: {len(snap['notes'])}")

    section(f"{cid}  --  diff_snapshots (2025-12-31 -> today)")
    diff = tools.diff_snapshots(cid, "2025-12-31", TODAY)
    print(f"AUM: {diff['aum_usd_from']:,.0f} -> {diff['aum_usd_to']:,.0f}  "
          f"({diff['change_pct']:+.1f}%)" if diff['change_pct'] is not None else "")
    print("Top asset-class moves:")
    for ac in diff["asset_class_change"][:3]:
        print(f"  {ac['asset_class']:<22} {ac['change_usd']:>+14,.0f}  "
              f"({ac['weight_pct_from']}% -> {ac['weight_pct_to']}%)")
    print("Top instrument movers:")
    for m in diff["instrument_movers"][:3]:
        print(f"  {m['instrument_name'][:42]:<42} {m['change_usd']:>+12,.0f}  "
              f"price_effect={m['approx_price_effect_usd']}  flow_effect={m['approx_flow_effect_usd']}  "
              f"qty_unchanged={m['quantity_unchanged']}")
    print(f"Events in window: {len(diff['events_in_window'])}")
    for e in diff["events_in_window"][:3]:
        print(f"  {e['event_date']} [{e['severity']}] {e['description'][:70]}")
        print(f"      candidate holdings touched: {e['candidate_related_holdings_heuristic']}")

    section(f"{cid}  --  get_liquidity_map")
    liq = tools.get_liquidity_map(cid)
    for t in liq["tier_breakdown"]:
        if "cumulative_sellable_pct" in t:
            print(f"  {t['liquidity_tier']:<16} {t['pct_of_portfolio']:>6.1f}%   "
                  f"cumulative sellable: {t['cumulative_sellable_pct']:>6.1f}%")
    print(f"  Facility headroom: {liq['credit_facility_headroom_usd']:,.0f}  "
          f"USD cash needs in horizon: {liq['near_term_cash_needs_usd_only']:,.0f}  "
          f"non-USD needs: {len(liq['near_term_cash_needs_other_ccy'])}")

    section(f"{cid}  --  get_lookthrough_exposure")
    lt = tools.get_lookthrough_exposure(cid)
    for theme in lt["candidate_concentration_themes"]:
        print(f"  theme~'{theme['label_guess']}': {theme['combined_pct_of_client_aum']:.1f}% of AUM "
              f"across {len(theme['instruments'])} instruments")
        for i in theme["instruments"]:
            print(f"      {i['weight_pct']:>5.1f}%  {i['instrument_name']}")

    section(f"{cid}  --  get_notes")
    for n in tools.get_notes(cid):
        print(f"  {n['note_date']} ({n['channel']}): {n['note'][:110]}")

print("\n" + "=" * 78)
print("Ad hoc SQL escape hatch check")
print("=" * 78)
rows = tools.run_sql(
    "SELECT event_type, COUNT(*) as n FROM event_log GROUP BY event_type ORDER BY n DESC"
)
print(rows)

print("\nDone. Snapshot dates known to the system:", SNAPSHOT_DATES)
