"""
Robustness sweep: every tool function against every one of the 20 clients
(and every portfolio), not just the three focal ones. Catches edge cases
the focal clients happen not to exercise -- e.g. a client with zero
facilities, a custody-only portfolio, a client with no structured products
for get_lookthrough_exposure to cluster.

Run from the repo root:  python check_all_clients.py
Exits non-zero if anything raised.
"""
from backend import tools
from backend.db import SNAPSHOT_DATES, TODAY

failures = []


def run(label, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as e:
        failures.append((label, f"{type(e).__name__}: {e}"))


clients = tools.list_clients()
print(f"Sweeping {len(clients)} clients across every tool function...\n")

run("get_events()", tools.get_events)
run("get_market_context()", tools.get_market_context)

for c in clients:
    cid = c["client_id"]
    run(f"{cid} get_client_snapshot", tools.get_client_snapshot, cid)
    run(f"{cid} diff_snapshots", tools.diff_snapshots, cid, SNAPSHOT_DATES[0], TODAY)
    run(f"{cid} get_notes", tools.get_notes, cid)
    run(f"{cid} get_liquidity_map", tools.get_liquidity_map, cid)
    run(f"{cid} get_lookthrough_exposure", tools.get_lookthrough_exposure, cid)
    run(f"{cid} get_facility_status", tools.get_facility_status, cid)

    snap = tools.get_client_snapshot(cid)
    for p in snap["portfolios"]:
        run(f"{cid}/{p['portfolio_id']} check_mandate_breach", tools.check_mandate_breach, p["portfolio_id"])

print(f"Done. {len(failures)} failures out of {len(clients)} clients x 6 client-level tools + mandate checks.\n")
for label, err in failures:
    print(f"  FAIL  {label:<45} {err}")

if failures:
    raise SystemExit(1)
print("All tools ran clean for all clients.")
