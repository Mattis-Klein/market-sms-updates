from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None

from market_updates.db import POSTGRES_SCHEMA_STATEMENTS

TABLES = [
    "market_sms_sessions",
    "market_notifications",
    "market_sms_allowlist",
    "market_sms_invite_requests",
    "market_feedback_entries",
    "market_assistant_sessions",
    "market_scheduled_reminders",
]


def _now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def backup_sqlite(sqlite_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{sqlite_path.stem}.backup-{_now_stamp()}{sqlite_path.suffix}"
    shutil.copy2(sqlite_path, backup_path)
    return backup_path


def sqlite_tables(sqlite_path: Path) -> list[str]:
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()
        return [row[0] for row in rows]


def init_postgres(conn) -> None:
    with conn.cursor() as cur:
        for statement in POSTGRES_SCHEMA_STATEMENTS:
            cur.execute(statement)
    conn.commit()


def postgres_has_data(conn) -> bool:
    with conn.cursor(row_factory=dict_row) as cur:
        for table in TABLES:
            cur.execute(f"SELECT COUNT(*) AS count FROM {table}")
            count = int(cur.fetchone()["count"])
            if count > 0:
                return True
    return False


def copy_table(sqlite_path: Path, pg_conn, table: str) -> int:
    with sqlite3.connect(sqlite_path) as src:
        src.row_factory = sqlite3.Row
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
    if not rows:
        return 0

    columns = list(rows[0].keys())
    col_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    query = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"

    with pg_conn.cursor() as cur:
        for row in rows:
            cur.execute(query, tuple(row[col] for col in columns))
    return len(rows)


def run(sqlite_path: str, database_url: str, backup_dir: str, force_if_destination_nonempty: bool) -> None:
    src_path = Path(sqlite_path)
    if not src_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {src_path}")

    existing_tables = sqlite_tables(src_path)
    print("SQLite source:", src_path)
    print("SQLite tables:", ", ".join(existing_tables) if existing_tables else "(none)")

    backup_path = backup_sqlite(src_path, Path(backup_dir))
    print("SQLite backup created:", backup_path)

    if psycopg is None:
        raise RuntimeError("psycopg is required to run PostgreSQL migration")

    with psycopg.connect(database_url) as pg_conn:
        init_postgres(pg_conn)

        if postgres_has_data(pg_conn) and not force_if_destination_nonempty:
            raise RuntimeError(
                "Destination PostgreSQL already contains data. "
                "Refusing migration to avoid duplicate/conflicting records."
            )

        total = 0
        for table in TABLES:
            count = copy_table(src_path, pg_conn, table)
            print(f"Migrated {count} rows: {table}")
            total += count

        pg_conn.commit()
        print("Migration complete. Total rows migrated:", total)

    print("Rollback notes:")
    print("1) Keep using original SQLite path while investigating issues.")
    print("2) Point app back to SQLite by clearing DATABASE_URL.")
    print(f"3) SQLite backup is preserved at: {backup_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="One-time SQLite -> PostgreSQL migration")
    parser.add_argument("--sqlite-path", default=os.getenv("MARKET_UPDATES_DB_PATH", "backend/data/market_updates.sqlite"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--backup-dir", default="backend/data/backups")
    parser.add_argument("--force-if-destination-nonempty", action="store_true")
    args = parser.parse_args()

    if not args.database_url:
        raise RuntimeError("DATABASE_URL (or --database-url) is required")

    run(
        sqlite_path=args.sqlite_path,
        database_url=args.database_url,
        backup_dir=args.backup_dir,
        force_if_destination_nonempty=args.force_if_destination_nonempty,
    )


if __name__ == "__main__":
    main()
