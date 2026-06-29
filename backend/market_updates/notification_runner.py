from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from .config import load_config
from .db import Database, utc_now
from .market_data import get_latest_quote
from .notifications import mark_triggered
from .sms_sender import send_sms


def _parse_iso(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def run_notification_batch(dry_run: bool = False):
    config = load_config()
    db = Database(config.market_updates_db_path, database_url=config.database_url)
    now = datetime.now(timezone.utc)
    sent = 0

    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM market_notifications
            WHERE enabled = 1 AND completed = 0
            ORDER BY id ASC
            """
        ).fetchall()

    for row in rows:
        item = dict(row)
        ntype = item["notification_type"]
        should_send = False

        if ntype == "price_alert":
            quote = await get_latest_quote(item["symbol"])
            if quote["available"]:
                price = quote["price"]
                if item["condition"] == "ABOVE" and price >= item["threshold"]:
                    should_send = True
                if item["condition"] == "BELOW" and price <= item["threshold"]:
                    should_send = True

        elif ntype == "one_time_reminder":
            due = _parse_iso(item.get("due_at"))
            if due and now >= due:
                should_send = True

        elif ntype == "daily_reminder":
            daily = item.get("daily_time")
            if daily:
                target = now.strftime("%H:%M")
                last = _parse_iso(item.get("last_triggered_at"))
                already_today = last and last.date() == now.date()
                if target >= daily and not already_today:
                    should_send = True

        elif ntype == "interval_reminder":
            start_at = _parse_iso(item.get("interval_start_at"))
            stop_at = _parse_iso(item.get("interval_stop_at"))
            if stop_at and now > stop_at:
                mark_triggered(db, item["id"], True)
                continue
            if start_at and now >= start_at:
                last = _parse_iso(item.get("last_triggered_at"))
                mins = int(item.get("interval_minutes") or 0)
                elapsed = (now - last).total_seconds() / 60.0 if last else None
                if last is None or elapsed >= mins:
                    should_send = True

        if not should_send:
            continue

        message = item.get("message") or f"Market notification #{item['id']}"
        if dry_run:
            print(f"DRY_RUN -> {item['phone_number']}: {message}")
            sent += 1
            continue

        ok = await send_sms(
            config.twilio_account_sid,
            config.twilio_auth_token,
            config.twilio_from_number,
            item["phone_number"],
            message,
        )
        if ok:
            sent += 1
            complete_now = ntype == "one_time_reminder"
            mark_triggered(db, item["id"], complete_now)

    print(f"Processed at {utc_now()} - sent {sent} messages")


if __name__ == "__main__":
    asyncio.run(run_notification_batch(dry_run=False))
