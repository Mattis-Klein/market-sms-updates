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

CREATE TABLE IF NOT EXISTS market_scheduled_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT NOT NULL,
    reminder_text TEXT NOT NULL,
    scheduled_at_utc TEXT NOT NULL,
    scheduled_at_local TEXT NOT NULL,
    timezone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    sent_at TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    deduplication_key TEXT,
    claimed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_market_scheduled_reminders_due
ON market_scheduled_reminders (status, scheduled_at_utc);

CREATE INDEX IF NOT EXISTS idx_market_scheduled_reminders_phone
ON market_scheduled_reminders (phone_number, status, scheduled_at_utc);

CREATE UNIQUE INDEX IF NOT EXISTS idx_market_scheduled_reminders_dedup
ON market_scheduled_reminders (phone_number, deduplication_key)
WHERE deduplication_key IS NOT NULL;
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

    def create_scheduled_reminder(
        self,
        phone_number: str,
        reminder_text: str,
        scheduled_at_utc: str,
        scheduled_at_local: str,
        timezone_name: str,
        deduplication_key: str | None = None,
    ) -> int:
        with self.connect() as conn:
            if deduplication_key:
                existing = conn.execute(
                    """
                    SELECT id FROM market_scheduled_reminders
                    WHERE phone_number = ? AND deduplication_key = ?
                    LIMIT 1
                    """,
                    (phone_number, deduplication_key),
                ).fetchone()
                if existing:
                    return int(existing["id"])

            cur = conn.execute(
                """
                INSERT INTO market_scheduled_reminders (
                    phone_number, reminder_text, scheduled_at_utc, scheduled_at_local,
                    timezone, status, created_at, deduplication_key
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    phone_number,
                    reminder_text,
                    scheduled_at_utc,
                    scheduled_at_local,
                    timezone_name,
                    utc_now(),
                    deduplication_key,
                ),
            )
            return int(cur.lastrowid)

    def list_scheduled_reminders(self, phone_number: str, include_inactive: bool = False) -> list[dict]:
        with self.connect() as conn:
            if include_inactive:
                rows = conn.execute(
                    """
                    SELECT * FROM market_scheduled_reminders
                    WHERE phone_number = ?
                    ORDER BY scheduled_at_utc ASC, id ASC
                    """,
                    (phone_number,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM market_scheduled_reminders
                    WHERE phone_number = ? AND status IN ('pending', 'processing')
                    ORDER BY scheduled_at_utc ASC, id ASC
                    """,
                    (phone_number,),
                ).fetchall()
        return [dict(row) for row in rows]

    def cancel_scheduled_reminder(self, phone_number: str, reminder_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                """
                UPDATE market_scheduled_reminders
                SET status = 'cancelled', last_error = NULL
                WHERE id = ? AND phone_number = ? AND status IN ('pending', 'processing')
                """,
                (reminder_id, phone_number),
            )
            return cur.rowcount > 0

    def cancel_scheduled_reminders_by_text(self, phone_number: str, text_fragment: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                UPDATE market_scheduled_reminders
                SET status = 'cancelled', last_error = NULL
                WHERE phone_number = ? AND status IN ('pending', 'processing')
                  AND lower(reminder_text) LIKE ?
                """,
                (phone_number, f"%{text_fragment.lower()}%"),
            )
            return cur.rowcount

    def cancel_all_scheduled_reminders(self, phone_number: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                UPDATE market_scheduled_reminders
                SET status = 'cancelled', last_error = NULL
                WHERE phone_number = ? AND status IN ('pending', 'processing')
                """,
                (phone_number,),
            )
            return cur.rowcount

    def update_scheduled_reminder(
        self,
        phone_number: str,
        reminder_id: int,
        reminder_text: str,
        scheduled_at_utc: str,
        scheduled_at_local: str,
        timezone_name: str,
    ) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                """
                UPDATE market_scheduled_reminders
                SET reminder_text = ?,
                    scheduled_at_utc = ?,
                    scheduled_at_local = ?,
                    timezone = ?,
                    status = 'pending',
                    claimed_at = NULL,
                    sent_at = NULL,
                    last_error = NULL
                WHERE id = ? AND phone_number = ? AND status IN ('pending', 'processing')
                """,
                (
                    reminder_text,
                    scheduled_at_utc,
                    scheduled_at_local,
                    timezone_name,
                    reminder_id,
                    phone_number,
                ),
            )
            return cur.rowcount > 0

    def recover_stuck_processing_reminders(self, timeout_seconds: int) -> int:
        with self.connect() as conn:
            cutoff = datetime.now(timezone.utc).timestamp() - max(timeout_seconds, 30)
            rows = conn.execute(
                """
                SELECT id, claimed_at FROM market_scheduled_reminders
                WHERE status = 'processing' AND claimed_at IS NOT NULL
                """
            ).fetchall()
            recover_ids: list[int] = []
            for row in rows:
                claimed_at = row["claimed_at"]
                try:
                    claimed_ts = datetime.fromisoformat(claimed_at).timestamp()
                except (TypeError, ValueError):
                    claimed_ts = 0
                if claimed_ts <= cutoff:
                    recover_ids.append(int(row["id"]))

            if not recover_ids:
                return 0

            conn.executemany(
                """
                UPDATE market_scheduled_reminders
                SET status = 'pending', claimed_at = NULL
                WHERE id = ? AND status = 'processing'
                """,
                [(reminder_id,) for reminder_id in recover_ids],
            )
            return len(recover_ids)

    def claim_due_scheduled_reminders(self, now_utc: str, limit: int = 50) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM market_scheduled_reminders
                WHERE status = 'pending' AND scheduled_at_utc <= ?
                ORDER BY scheduled_at_utc ASC, id ASC
                LIMIT ?
                """,
                (now_utc, max(1, limit)),
            ).fetchall()

            claimed: list[int] = []
            for row in rows:
                reminder_id = int(row["id"])
                cur = conn.execute(
                    """
                    UPDATE market_scheduled_reminders
                    SET status = 'processing', claimed_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (utc_now(), reminder_id),
                )
                if cur.rowcount > 0:
                    claimed.append(reminder_id)

            if not claimed:
                return []

            placeholders = ",".join("?" for _ in claimed)
            claimed_rows = conn.execute(
                f"SELECT * FROM market_scheduled_reminders WHERE id IN ({placeholders}) ORDER BY scheduled_at_utc ASC, id ASC",
                tuple(claimed),
            ).fetchall()
            return [dict(row) for row in claimed_rows]

    def mark_scheduled_reminder_sent(self, reminder_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE market_scheduled_reminders
                SET status = 'sent', sent_at = ?, claimed_at = NULL, attempt_count = attempt_count + 1, last_error = NULL
                WHERE id = ?
                """,
                (utc_now(), reminder_id),
            )

    def mark_scheduled_reminder_retry(self, reminder_id: int, error_text: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE market_scheduled_reminders
                SET status = 'pending', claimed_at = NULL, attempt_count = attempt_count + 1, last_error = ?
                WHERE id = ?
                """,
                (error_text[:500], reminder_id),
            )

    def mark_scheduled_reminder_failed(self, reminder_id: int, error_text: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE market_scheduled_reminders
                SET status = 'failed', claimed_at = NULL, attempt_count = attempt_count + 1, last_error = ?
                WHERE id = ?
                """,
                (error_text[:500], reminder_id),
            )
