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

CREATE TABLE IF NOT EXISTS market_assistant_sessions (
    phone_number TEXT PRIMARY KEY,
    assistant_mode_active INTEGER NOT NULL DEFAULT 0,
    assistant_started_at TEXT,
    assistant_last_activity_at TEXT,
    assistant_conversation_history TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
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

    def get_assistant_session(self, phone_number: str):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM market_assistant_sessions WHERE phone_number = ?",
                (phone_number,),
            ).fetchone()
            if not row:
                return None
            try:
                history = json.loads(row["assistant_conversation_history"] or "[]")
                if not isinstance(history, list):
                    history = []
            except json.JSONDecodeError:
                history = []
            return {
                "phone_number": row["phone_number"],
                "assistant_mode_active": bool(row["assistant_mode_active"]),
                "assistant_started_at": row["assistant_started_at"],
                "assistant_last_activity_at": row["assistant_last_activity_at"],
                "assistant_conversation_history": history,
            }

    def upsert_assistant_session(
        self,
        phone_number: str,
        assistant_mode_active: bool,
        assistant_started_at: str | None,
        assistant_last_activity_at: str | None,
        assistant_conversation_history: list[dict],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO market_assistant_sessions (
                    phone_number,
                    assistant_mode_active,
                    assistant_started_at,
                    assistant_last_activity_at,
                    assistant_conversation_history,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(phone_number)
                DO UPDATE SET
                    assistant_mode_active = excluded.assistant_mode_active,
                    assistant_started_at = excluded.assistant_started_at,
                    assistant_last_activity_at = excluded.assistant_last_activity_at,
                    assistant_conversation_history = excluded.assistant_conversation_history,
                    updated_at = excluded.updated_at
                """,
                (
                    phone_number,
                    1 if assistant_mode_active else 0,
                    assistant_started_at,
                    assistant_last_activity_at,
                    json.dumps(assistant_conversation_history),
                    utc_now(),
                ),
            )

    def activate_assistant_session(self, phone_number: str, started_at: str, last_activity_at: str) -> None:
        self.upsert_assistant_session(
            phone_number=phone_number,
            assistant_mode_active=True,
            assistant_started_at=started_at,
            assistant_last_activity_at=last_activity_at,
            assistant_conversation_history=[],
        )

    def deactivate_assistant_session(self, phone_number: str) -> None:
        existing = self.get_assistant_session(phone_number)
        if not existing:
            return
        self.upsert_assistant_session(
            phone_number=phone_number,
            assistant_mode_active=False,
            assistant_started_at=existing.get("assistant_started_at"),
            assistant_last_activity_at=existing.get("assistant_last_activity_at"),
            assistant_conversation_history=[],
        )

    def get_active_assistant_session(self, phone_number: str, expiration_minutes: int):
        session = self.get_assistant_session(phone_number)
        if not session or not session.get("assistant_mode_active"):
            return None

        last_activity_at = session.get("assistant_last_activity_at")
        if not last_activity_at:
            self.deactivate_assistant_session(phone_number)
            return None

        try:
            last_dt = datetime.fromisoformat(last_activity_at)
            now_dt = datetime.now(timezone.utc)
            elapsed_seconds = (now_dt - last_dt).total_seconds()
        except ValueError:
            self.deactivate_assistant_session(phone_number)
            return None

        if elapsed_seconds > max(expiration_minutes, 1) * 60:
            self.deactivate_assistant_session(phone_number)
            return None

        return session
