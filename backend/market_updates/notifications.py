from __future__ import annotations

from .db import Database, utc_now


def create_notification(db: Database, payload: dict) -> int:
    now = utc_now()
    with db.connect() as conn:
        duplicate = conn.execute(
            """
            SELECT id FROM market_notifications
            WHERE phone_number = ? AND notification_type = ? AND COALESCE(symbol, '') = COALESCE(?, '')
              AND COALESCE(condition, '') = COALESCE(?, '') AND COALESCE(threshold, 0) = COALESCE(?, 0)
              AND COALESCE(message, '') = COALESCE(?, '') AND enabled = 1 AND completed = 0
            LIMIT 1
            """,
            (
                payload["phone_number"],
                payload["notification_type"],
                payload.get("symbol"),
                payload.get("condition"),
                payload.get("threshold"),
                payload.get("message"),
            ),
        ).fetchone()
        if duplicate:
            return int(duplicate["id"])

        cur = conn.execute(
            """
            INSERT INTO market_notifications (
                phone_number, notification_type, symbol, condition, threshold, message,
                due_at, daily_time, interval_minutes, interval_start_at, interval_stop_at,
                enabled, completed, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)
            """,
            (
                payload["phone_number"],
                payload["notification_type"],
                payload.get("symbol"),
                payload.get("condition"),
                payload.get("threshold"),
                payload.get("message"),
                payload.get("due_at"),
                payload.get("daily_time"),
                payload.get("interval_minutes"),
                payload.get("interval_start_at"),
                payload.get("interval_stop_at"),
                now,
                now,
            ),
        )
        return int(cur.lastrowid)


def list_notifications(db: Database, phone_number: str):
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM market_notifications
            WHERE phone_number = ?
            ORDER BY created_at DESC
            """,
            (phone_number,),
        ).fetchall()
        return [dict(row) for row in rows]


def update_notification_flags(db: Database, notification_id: int, *, enabled: bool | None = None, completed: bool | None = None):
    sets = []
    values = []
    if enabled is not None:
        sets.append("enabled = ?")
        values.append(1 if enabled else 0)
    if completed is not None:
        sets.append("completed = ?")
        values.append(1 if completed else 0)
    sets.append("updated_at = ?")
    values.append(utc_now())
    values.append(notification_id)
    with db.connect() as conn:
        conn.execute(f"UPDATE market_notifications SET {', '.join(sets)} WHERE id = ?", tuple(values))


def mark_triggered(db: Database, notification_id: int, complete_now: bool):
    with db.connect() as conn:
        conn.execute(
            "UPDATE market_notifications SET last_triggered_at = ?, completed = ?, updated_at = ? WHERE id = ?",
            (utc_now(), 1 if complete_now else 0, utc_now(), notification_id),
        )


def summarize_notification(row: dict) -> str:
    ntype = row["notification_type"]
    state = "active" if row["enabled"] and not row["completed"] else "inactive"
    if ntype == "price_alert":
        return f"{row['symbol']} {row['condition']} {row['threshold']} ({state})"
    if ntype == "one_time_reminder":
        return f"one-time {row.get('due_at') or ''} ({state})"
    if ntype == "daily_reminder":
        return f"daily {row.get('daily_time') or ''} ({state})"
    if ntype == "interval_reminder":
        return f"every {row.get('interval_minutes')}m ({state})"
    return f"{ntype} ({state})"
