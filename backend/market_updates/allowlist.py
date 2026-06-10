from __future__ import annotations

from typing import Optional

from .db import Database, utc_now


def normalize_phone_number(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if value.startswith("+") and digits:
        return f"+{digits}"
    return f"+{digits}" if digits else value.strip()


def seed_allowlist(db: Database, csv_numbers: str) -> None:
    if not csv_numbers.strip():
        return
    for raw in csv_numbers.split(","):
        phone = normalize_phone_number(raw.strip())
        if phone:
            upsert_allowlist_entry(db, phone, "env-seed", True)


def upsert_allowlist_entry(db: Database, phone_number: str, label: str = "", enabled: bool = True) -> None:
    now = utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO market_sms_allowlist (phone_number, label, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(phone_number)
            DO UPDATE SET label = excluded.label, enabled = excluded.enabled, updated_at = excluded.updated_at
            """,
            (normalize_phone_number(phone_number), label, 1 if enabled else 0, now, now),
        )


def disable_allowlist_entry(db: Database, phone_number: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE market_sms_allowlist SET enabled = 0, updated_at = ? WHERE phone_number = ?",
            (utc_now(), normalize_phone_number(phone_number)),
        )


def is_allowlisted(db: Database, phone_number: str) -> bool:
    normalized = normalize_phone_number(phone_number)
    candidates = {normalized}
    if normalized.startswith("+1") and len(normalized) == 12:
        candidates.add(normalized[2:])
    with db.connect() as conn:
        row = conn.execute(
            f"SELECT 1 FROM market_sms_allowlist WHERE enabled = 1 AND phone_number IN ({','.join('?' for _ in candidates)}) LIMIT 1",
            tuple(candidates),
        ).fetchone()
        return bool(row)


def list_allowlist(db: Database):
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT phone_number, label, enabled, updated_at FROM market_sms_allowlist ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def create_invite_request(db: Database, phone_number: str, request_text: str = "") -> int:
    now = utc_now()
    normalized = normalize_phone_number(phone_number)
    with db.connect() as conn:
        existing = conn.execute(
            "SELECT id FROM market_sms_invite_requests WHERE phone_number = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
            (normalized,),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE market_sms_invite_requests SET request_text = ?, updated_at = ? WHERE id = ?",
                (request_text, now, existing["id"]),
            )
            return int(existing["id"])

        cur = conn.execute(
            """
            INSERT INTO market_sms_invite_requests (phone_number, status, request_text, created_at, updated_at)
            VALUES (?, 'pending', ?, ?, ?)
            """,
            (normalized, request_text, now, now),
        )
        return int(cur.lastrowid)


def list_invite_requests(db: Database, status: Optional[str] = None):
    with db.connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM market_sms_invite_requests WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM market_sms_invite_requests ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def set_invite_request_status(db: Database, request_id: int, status: str) -> bool:
    with db.connect() as conn:
        cur = conn.execute(
            "UPDATE market_sms_invite_requests SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now(), request_id),
        )
        return cur.rowcount > 0
