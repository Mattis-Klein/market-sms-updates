from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from .config import load_config
from .db import Database, utc_now
from .sms_sender import send_sms_with_result


logger = logging.getLogger(__name__)


def _next_retry_utc(delay_seconds: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=max(delay_seconds, 15))


async def process_due_reminders_once(db: Database, config) -> dict:
    if not config.reminders_enabled:
        return {"processed": 0, "sent": 0, "failed": 0, "retried": 0}

    db.recover_stuck_processing_reminders(config.reminder_processing_timeout_seconds)
    due_rows = db.claim_due_scheduled_reminders(utc_now(), limit=100)

    processed = 0
    sent = 0
    failed = 0
    retried = 0

    for item in due_rows:
        processed += 1
        reminder_id = int(item["id"])
        attempts = int(item.get("attempt_count") or 0)
        body = f"Reminder: {item['reminder_text']}"

        result = await send_sms_with_result(
            config.twilio_account_sid,
            config.twilio_auth_token,
            config.twilio_from_number,
            item["phone_number"],
            body,
        )

        if result["ok"]:
            db.mark_scheduled_reminder_sent(reminder_id)
            sent += 1
            continue

        permanent = result.get("error_type") == "permanent"
        maxed = (attempts + 1) >= max(config.reminder_max_attempts, 1)
        error_text = result.get("error") or "send_failed"

        if permanent or maxed:
            db.mark_scheduled_reminder_failed(reminder_id, error_text)
            failed += 1
            continue

        db.mark_scheduled_reminder_retry(reminder_id, error_text)
        retry_due = _next_retry_utc(config.reminder_retry_delay_seconds).isoformat()
        db.update_scheduled_reminder(
            phone_number=item["phone_number"],
            reminder_id=reminder_id,
            reminder_text=item["reminder_text"],
            scheduled_at_utc=retry_due,
            scheduled_at_local=item["scheduled_at_local"],
            timezone_name=item["timezone"],
        )
        retried += 1

    return {"processed": processed, "sent": sent, "failed": failed, "retried": retried}


async def run_reminder_worker_forever() -> None:
    config = load_config()
    db = Database(config.market_updates_db_path)

    if not config.reminders_enabled:
        logger.info("reminders_disabled_worker_idle")
        return

    logger.info("reminder_worker_started", extra={"poll_seconds": config.reminder_poll_seconds})
    while True:
        try:
            result = await process_due_reminders_once(db, config)
            if result["processed"]:
                logger.info("reminder_worker_batch", extra=result)
        except Exception:
            logger.exception("reminder_worker_unhandled_error")
        await asyncio.sleep(max(config.reminder_poll_seconds, 5))


if __name__ == "__main__":
    asyncio.run(run_reminder_worker_forever())
