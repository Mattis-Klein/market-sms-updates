from __future__ import annotations

import httpx

from .db import Database, utc_now


def store_feedback(db: Database, phone_number: str, message: str, source: str = "sms") -> int:
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO market_feedback_entries (phone_number, message, source, created_at) VALUES (?, ?, ?, ?)",
            (phone_number, message.strip(), source, utc_now()),
        )
        return int(cur.lastrowid)


def list_feedback(db: Database, limit: int = 100):
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM market_feedback_entries ORDER BY id DESC LIMIT ?",
            (max(1, min(500, limit)),),
        ).fetchall()
        return [dict(row) for row in rows]


async def forward_feedback(ingest_url: str, ingest_token: str, payload: dict) -> bool:
    if not ingest_url:
        return False
    headers = {}
    if ingest_token:
        headers["Authorization"] = f"Bearer {ingest_token}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(ingest_url, json=payload, headers=headers)
            return 200 <= resp.status_code < 300
    except httpx.HTTPError:
        return False
