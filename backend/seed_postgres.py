"""
One-time (re-runnable) load of the reference dataset into Postgres.

Mirrors exactly what backend/db.py's SQLite build does, table for table --
same column names (including the hyphenated aum_2025-12-31 style date
columns, kept identical via double-quoted identifiers so nothing downstream
in tools.py has to know which backend it's talking to), same dtype-inferred
types. Drops and recreates each table so it's safe to re-run whenever the
CSVs change; the dataset is small (~1,700 rows across all tables) so a full
reload takes well under a second.

Run with:  docker compose run --rm backend python -m backend.seed_postgres
"""
import json

import pandas as pd
import psycopg2
import psycopg2.extras

from . import config, db

PG_TYPE_MAP = {
    "int64": "BIGINT",
    "float64": "DOUBLE PRECISION",
    "bool": "BOOLEAN",
}


def _pg_type(dtype) -> str:
    return PG_TYPE_MAP.get(str(dtype), "TEXT")


def _quote(col: str) -> str:
    return f'"{col}"'


def _create_and_load(conn, table_name: str, df: pd.DataFrame):
    cur = conn.cursor()
    cur.execute(f'DROP TABLE IF EXISTS {_quote(table_name)} CASCADE;')

    cols_ddl = ", ".join(f"{_quote(c)} {_pg_type(df[c].dtype)}" for c in df.columns)
    cur.execute(f'CREATE TABLE {_quote(table_name)} ({cols_ddl});')

    cols_list = ", ".join(_quote(c) for c in df.columns)
    insert_sql = f'INSERT INTO {_quote(table_name)} ({cols_list}) VALUES %s'
    rows = [tuple(r) for r in df.astype(object).where(pd.notnull(df), None).itertuples(index=False, name=None)]
    if rows:
        psycopg2.extras.execute_values(cur, insert_sql, rows, page_size=500)

    conn.commit()
    print(f"  {table_name:<22} {len(df):>5} rows, {len(df.columns):>2} columns")


def seed():
    config.require("DATABASE_URL")
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        print("Seeding reference tables into Postgres...")
        for name in db.CSV_TABLES:
            df = pd.read_csv(f"{db.DATA_DIR}/{name}.csv")
            _create_and_load(conn, name, df)

        with open(f"{db.DATA_DIR}/rm_notes.json", encoding="utf-8") as f:
            notes = json.load(f)
        _create_and_load(conn, "rm_notes", pd.DataFrame(notes))

        cur = conn.cursor()
        for stmt in db.INDEX_STATEMENTS:
            cur.execute(stmt)
        conn.commit()
        print("Indices created.")
        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
