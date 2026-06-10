import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS market_sms_sessions (
    phone_number TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    draft_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    symbol TEXT,
    condition TEXT,
    threshold REAL,
    message TEXT,
    due_at TEXT,
    daily_time TEXT,
    interval_minutes INTEGER,
    interval_start_at TEXT,
    interval_stop_at TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    completed INTEGER NOT NULL DEFAULT 0,
    last_triggered_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_sms_allowlist (
    phone_number TEXT PRIMARY KEY,
    label TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_sms_invite_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT NOT NULL,
    status TEXT NOT NULL,
    request_text TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_feedback_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT NOT NULL,
    message TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_session(self, phone_number: str):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM market_sms_sessions WHERE phone_number = ?", (phone_number,)
            ).fetchone()
            if not row:
                return None
            return {
                "phone_number": row["phone_number"],
                "state": row["state"],
                "draft": json.loads(row["draft_json"]),
            }

    def upsert_session(self, phone_number: str, state: str, draft: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO market_sms_sessions (phone_number, state, draft_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(phone_number)
                DO UPDATE SET state = excluded.state, draft_json = excluded.draft_json, updated_at = excluded.updated_at
                """,
                (phone_number, state, json.dumps(draft), utc_now()),
            )

    def clear_session(self, phone_number: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM market_sms_sessions WHERE phone_number = ?", (phone_number,))
