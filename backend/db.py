"""
Reference dataset access -- Postgres (Supabase) when reachable, local SQLite
otherwise.

Why a relational store over the raw CSVs rather than a vector store: the
data is small, structured and relational (client -> portfolio -> holding ->
instrument). Every answer an agent gives should be traceable back to exact
rows, and SQL gives us that for free -- a query plus its result set is
itself an audit trail. There is nothing here that benefits from
semantic/embedding search.

Why Postgres as the primary backend: it mirrors how this would actually run
in a bank -- a backend service holding a direct connection to its own
database, not a vector index. Postgres is seeded once via
backend/seed_postgres.py; this module just connects and queries it.

Why SQLite as a fallback rather than a hard dependency on Postgres: if
DATABASE_URL is unset or the connection fails at startup (network down mid-
demo, say), the app falls back to rebuilding an equivalent in-memory
database from the same CSVs rather than refusing to run. Same schema, same
column names (including the hyphenated aum_2025-12-31 style date columns),
so nothing above this module needs to know which backend answered.
"""
import json
import os
import sqlite3
import warnings

import pandas as pd

try:
    import psycopg2
except ImportError:
    psycopg2 = None

from . import config

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(REPO_ROOT, "singhacks-jb-wealth-intelligence", "data")

CSV_TABLES = [
    "clients",
    "portfolios",
    "holdings",
    "instruments",
    "mandates",
    "transactions",
    "credit_facilities",
    "commitments",
    "planned_cash_needs",
    "market_context",
    "event_log",
]

# The five dated snapshots this dataset is built around. Fixed and known
# ahead of time, so we treat them as an enum rather than discovering them
# fresh from holdings.csv on every call.
SNAPSHOT_DATES = ["2025-12-31", "2026-02-27", "2026-03-31", "2026-06-30", "2026-08-26"]
TODAY = SNAPSHOT_DATES[-1]

# Reused by both backends for CREATE INDEX -- every column referenced here
# is a plain identifier (no hyphens), so the statements are valid SQL
# unchanged on both SQLite and Postgres.
INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_holdings_client ON holdings(client_id, snapshot_date)",
    "CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON holdings(portfolio_id, snapshot_date)",
    "CREATE INDEX IF NOT EXISTS idx_holdings_instrument ON holdings(instrument_id)",
    "CREATE INDEX IF NOT EXISTS idx_portfolios_client ON portfolios(client_id)",
    "CREATE INDEX IF NOT EXISTS idx_txn_client ON transactions(client_id, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_txn_portfolio ON transactions(portfolio_id, trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_facilities_client ON credit_facilities(client_id)",
    "CREATE INDEX IF NOT EXISTS idx_commitments_client ON commitments(client_id)",
    "CREATE INDEX IF NOT EXISTS idx_cashneeds_client ON planned_cash_needs(client_id)",
    "CREATE INDEX IF NOT EXISTS idx_notes_client ON rm_notes(client_id, note_date)",
    "CREATE INDEX IF NOT EXISTS idx_market_series ON market_context(series_id, snapshot_date)",
]

_conn = None
_backend = None  # "postgres" | "sqlite", set once get_connection() has run


def build_sqlite_database(db_path=":memory:"):
    """Builds an in-memory SQLite database from the raw CSVs and returns the connection."""
    conn = sqlite3.connect(db_path, check_same_thread=False)

    for name in CSV_TABLES:
        df = pd.read_csv(os.path.join(DATA_DIR, f"{name}.csv"))
        df.to_sql(name, conn, if_exists="replace", index=False)

    with open(os.path.join(DATA_DIR, "rm_notes.json"), encoding="utf-8") as f:
        notes = json.load(f)
    pd.DataFrame(notes).to_sql("rm_notes", conn, if_exists="replace", index=False)

    cur = conn.cursor()
    for stmt in INDEX_STATEMENTS:
        cur.execute(stmt)
    conn.commit()

    return conn


# kept for backwards compatibility with any external caller expecting the old name
build_database = build_sqlite_database


def get_connection():
    """
    Returns the shared, lazily-created connection.

    Tries Postgres first if DATABASE_URL is configured (see
    backend/seed_postgres.py for how that database gets populated). Falls
    back to an in-memory SQLite build from the CSVs if DATABASE_URL is
    unset, or if the Postgres connection fails -- e.g. no network. The
    fallback is logged, never silent, so a demo running on the fallback
    path is visible in the logs rather than a surprise later.
    """
    global _conn, _backend
    if _conn is not None:
        return _conn

    if config.DATABASE_URL and psycopg2 is not None:
        try:
            _conn = psycopg2.connect(config.DATABASE_URL, connect_timeout=5)
            _backend = "postgres"
            return _conn
        except Exception as e:
            print(f"[backend.db] Postgres unavailable ({e}); falling back to local SQLite.")

    _conn = build_sqlite_database()
    _backend = "sqlite"
    return _conn


def backend_name() -> str:
    """Which backend actually answered the last get_connection() call. Mostly for diagnostics/logging."""
    get_connection()
    return _backend


def query(sql, params=()):
    """Runs a read query and returns a DataFrame. Thin wrapper so callers don't import sqlite3/psycopg2/pandas."""
    conn = get_connection()
    if _backend == "postgres":
        sql = sql.replace("?", "%s")
        # pandas only officially tests sqlite3/SQLAlchemy connections; a raw
        # psycopg2 connection works fine (verified against the full tool-layer
        # self-test, byte-for-byte identical output to the SQLite backend) but
        # triggers this warning on every call. Suppressed narrowly rather than
        # switching to SQLAlchemy, which trades this for a paramstyle
        # (?  vs :name) compatibility problem instead.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")
            return pd.read_sql_query(sql, conn, params=params)
    return pd.read_sql_query(sql, conn, params=params)


def resolve_snapshot_date(as_of=None):
    """Validates a snapshot date against the five known dates. None means 'today' (the latest snapshot)."""
    if as_of is None:
        return TODAY
    if as_of not in SNAPSHOT_DATES:
        raise ValueError(
            f"'{as_of}' is not one of the five snapshot dates: {SNAPSHOT_DATES}"
        )
    return as_of


def snapshot_index(date):
    return SNAPSHOT_DATES.index(date)
