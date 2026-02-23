"""
Copy TrustSeal data from a local SQLite database into a PostgreSQL database.

Usage:
    python scripts/migrate_sqlite_to_postgres.py \
      --sqlite-path trustseal.db \
      --postgres-url "postgresql://user:pass@host:5432/postgres?sslmode=require"

If --postgres-url is omitted, DATABASE_URL from environment is used.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")


TABLE_ORDER: List[str] = [
    "users",
    "devices",
    "shipments",
    "shipment_legs",
    "sensor_logs",
    "custody_checkpoints",
]

TRUNCATE_ORDER: List[str] = list(reversed(TABLE_ORDER))

BOOL_COLUMNS: Dict[str, set[str]] = {
    "users": {"is_active", "is_verified"},
    "sensor_logs": {"light_exposure"},
    "custody_checkpoints": {"biometric_verified"},
}


@dataclass
class TableDump:
    name: str
    columns: List[str]
    rows: List[Dict[str, object]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL.")
    parser.add_argument(
        "--sqlite-path",
        default="trustseal.db",
        help="Path to source SQLite DB file (default: trustseal.db).",
    )
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("DATABASE_URL"),
        help="Target PostgreSQL URL. Falls back to DATABASE_URL env.",
    )
    parser.add_argument(
        "--skip-rag-index",
        action="store_true",
        help="Skip RAG reindexing after data copy.",
    )
    return parser.parse_args()


def read_table(conn: sqlite3.Connection, table: str) -> TableDump:
    column_rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    columns = [row[1] for row in column_rows]
    data_rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    rows = [dict(zip(columns, row)) for row in data_rows]
    return TableDump(name=table, columns=columns, rows=rows)


def normalize_row(table: str, row: Dict[str, object]) -> Dict[str, object]:
    bool_cols = BOOL_COLUMNS.get(table, set())
    for col in bool_cols:
        if col in row and row[col] is not None:
            row[col] = bool(row[col])
    return row


def build_insert_sql(table: str, columns: Iterable[str]) -> str:
    cols = list(columns)
    cols_sql = ", ".join(cols)
    params_sql = ", ".join(f":{c}" for c in cols)
    return f"INSERT INTO {table} ({cols_sql}) VALUES ({params_sql})"


def migrate(sqlite_path: str, postgres_url: str) -> None:
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"SQLite file not found: {sqlite_path}")
    if not postgres_url:
        raise ValueError("PostgreSQL URL is missing. Pass --postgres-url or set DATABASE_URL.")
    if not postgres_url.startswith("postgresql"):
        raise ValueError("Target URL must start with postgresql://")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    table_dumps: List[TableDump] = []
    for table in TABLE_ORDER:
        table_dumps.append(read_table(sqlite_conn, table))
    sqlite_conn.close()

    engine = create_engine(postgres_url, future=True)
    with engine.begin() as pg_conn:
        truncate_sql = f"TRUNCATE TABLE {', '.join(TRUNCATE_ORDER)} CASCADE"
        pg_conn.execute(text(truncate_sql))

        for dump in table_dumps:
            if not dump.rows:
                print(f"{dump.name}: 0 rows")
                continue

            insert_sql = text(build_insert_sql(dump.name, dump.columns))
            payload = [normalize_row(dump.name, dict(row)) for row in dump.rows]
            pg_conn.execute(insert_sql, payload)
            print(f"{dump.name}: {len(payload)} rows")

    print("Migration completed.")


def refresh_rag_index(postgres_url: str) -> None:
    os.environ["DATABASE_URL"] = postgres_url
    from app.database import SessionLocal  # noqa: WPS433
    from app.services.chat_service import chat_service  # noqa: WPS433

    db = SessionLocal()
    try:
        chat_service.refresh_index(db)
        print("RAG index refreshed.")
    finally:
        db.close()


def main() -> None:
    args = parse_args()
    migrate(sqlite_path=args.sqlite_path, postgres_url=args.postgres_url)
    if not args.skip_rag_index:
        refresh_rag_index(postgres_url=args.postgres_url)


if __name__ == "__main__":
    main()
