from __future__ import annotations

from datetime import datetime, timezone

from .allowlist import (
    create_invite_request,
    is_allowlisted,
    is_permanent_allowlisted,
    list_invite_requests,
    normalize_phone_number,
    set_invite_request_status,
    upsert_allowlist_entry,
)
from .config import MarketConfig
from .db import Database
from .feedback_store import forward_feedback, store_feedback
from .keywords import lookup_tickers, normalize_text, parse_check_symbols, parse_datecheck, parse_list_action
from .market_data import get_historical_close, get_latest_quote
from .notifications import create_notification, list_notifications, summarize_notification, update_notification_flags
from .sms_sender import send_sms
from .youtube_service import MRBEAST_CHANNEL_ID, LivecountsServiceError, format_subscriber_count, get_channel_subscriber_count


MENU_TEXT = (
    "Market SMS Assistant helps you check market/date info, look up tickers, set text reminders, and send feedback. "
    "Keywords: CHECK - see available checks; DATECHECK - check market/date info; TICKER - look up ticker info; "
    "BEAST - check MrBeast subscribers; "
    "REMIND - create a reminder; LIST - see reminders; CANCELREMINDER - cancel a reminder; "
    "FEEDBACK - send feedback or request access. Reply with a keyword to continue."
)


def _twiml_message(body: str) -> str:
    escaped = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{escaped}</Message></Response>"


async def handle_inbound_sms(db: Database, config: MarketConfig, from_number: str, body: str) -> str:
    sender = normalize_phone_number(from_number)
    incoming = body.strip()
    normalized = normalize_text(incoming)

    if sender == normalize_phone_number(config.market_access_approver_number):
        approver_reply = await _handle_approver_message(db, config, normalized)
        if approver_reply:
            return _twiml_message(approver_reply)

    if not (is_allowlisted(db, sender) or is_permanent_allowlisted(config.market_updates_allowed_numbers, sender)):
        blocked = await _handle_unapproved_sender(db, config, sender, incoming, normalized)
        return _twiml_message(blocked)

    session = db.get_session(sender)
    if normalized == "STOP":
        db.clear_session(sender)
        return _twiml_message("Canceled. Send MENU for commands.")

    if session:
        return _twiml_message(await _continue_session(db, sender, normalized, session["state"], session["draft"]))

    if normalized == "MENU":
        return _twiml_message(MENU_TEXT)

    if normalized.startswith("CHECK"):
        symbols = parse_check_symbols(normalized)
        if not symbols:
            return _twiml_message("Usage: CHECK BTC-USD AAPL TSLA")
        lines = []
        for symbol in symbols:
            result = await get_latest_quote(symbol)
            if not result["available"]:
                lines.append(f"{symbol}: unavailable")
            else:
                lines.append(
                    f"{result['symbol']}: ${result['price']:.2f} ({result['change']:+.2f}, {result['change_pct']:+.2f}%)"
                )
        return _twiml_message(" | ".join(lines))

    if normalized.startswith("DATECHECK"):
        parsed = parse_datecheck(normalized)
        if not parsed:
            return _twiml_message("Usage: DATECHECK YYYY-MM-DD AAPL TSLA")
        lines = []
        for symbol in parsed["symbols"]:
            result = await get_historical_close(symbol, parsed["date"])
            if not result["available"]:
                lines.append(f"{symbol}: unavailable")
            else:
                lines.append(f"{symbol} {result['actual_date']}: ${result['close']:.2f}")
        return _twiml_message(" | ".join(lines))

    if normalized.startswith(("TICKER", "LOOKUP", "FIND")):
        query = incoming.split(" ", 1)[1] if " " in incoming else ""
        results = lookup_tickers(query)
        if not results:
            return _twiml_message("No ticker matches found.")
        preview = [f"{item['symbol']} - {item['name']}" for item in results[:8]]
        return _twiml_message("Matches: " + " | ".join(preview))

    if normalized == "BEAST":
        try:
            count = await get_channel_subscriber_count(MRBEAST_CHANNEL_ID)
        except LivecountsServiceError:
            return _twiml_message("I couldn't check MrBeast subscribers right now. Try again soon.")
        return _twiml_message(
            f"MrBeast currently has {format_subscriber_count(count)} YouTube subscribers."
        )

    if normalized.startswith("FEEDBACK"):
        text = incoming[8:].strip() if len(incoming) > 8 else ""
        if not text:
            return _twiml_message("Usage: FEEDBACK <message>")
        entry_id = store_feedback(db, sender, text)
        await forward_feedback(
            config.feedback_portal_ingest_url,
            config.feedback_portal_ingest_token,
            {"id": entry_id, "phone_number": sender, "message": text, "source": "sms"},
        )
        return _twiml_message("Thanks, feedback received.")

    if normalized == "REMIND":
        db.upsert_session(sender, "await_remind_type", {})
        return _twiml_message("Reminder type? Reply PRICE, ONCE, DAILY, INTERVAL")

    if normalized in {"LIST", "NOTIFICATIONS", "ALERTS"}:
        return _twiml_message(_render_notifications(db, sender))

    if normalized.startswith("CANCELREMINDER"):
        parts = normalized.split()
        if len(parts) != 2 or not parts[1].isdigit():
            return _twiml_message("Usage: CANCELREMINDER <index>. Send LIST first.")
        return _twiml_message(_apply_notification_action(db, sender, "DELETE", int(parts[1])))

    action = parse_list_action(normalized)
    if action:
        return _twiml_message(_apply_notification_action(db, sender, action["action"], action["index"]))

    return _twiml_message("Unknown command. Send MENU.")


async def _handle_unapproved_sender(db: Database, config: MarketConfig, sender: str, incoming: str, normalized: str) -> str:
    if normalized.startswith("@MARKET") or normalized.startswith("REQUEST") or normalized.startswith("INVITE") or normalized.startswith("ACCESS"):
        request_id = create_invite_request(db, sender, incoming)
        await send_sms(
            config.twilio_account_sid,
            config.twilio_auth_token,
            config.twilio_from_number,
            normalize_phone_number(config.market_access_approver_number),
            f"Market invite request #{request_id} from {sender}. Reply YES {request_id} to approve.",
        )
        return f"Invite request submitted. Request ID: {request_id}."
    return "Access blocked. Reply REQUEST ACCESS to request approval."


async def _handle_approver_message(db: Database, config: MarketConfig, normalized: str):
    if normalized == "PENDING":
        pending = list_invite_requests(db, "pending")
        if not pending:
            return "No pending requests."
        lines = [f"#{row['id']} {row['phone_number']}" for row in pending[:10]]
        return "Pending: " + " | ".join(lines)

    if normalized.startswith("YES "):
        tail = normalized.split(" ", 1)[1]
        if not tail.isdigit():
            return "Usage: YES <request_id>"
        request_id = int(tail)
        requests = list_invite_requests(db)
        target = next((r for r in requests if r["id"] == request_id), None)
        if not target:
            return "Request not found."
        set_invite_request_status(db, request_id, "approved")
        upsert_allowlist_entry(db, target["phone_number"], "invite-approved", True)
        await send_sms(
            config.twilio_account_sid,
            config.twilio_auth_token,
            config.twilio_from_number,
            target["phone_number"],
            "You are approved for Market SMS. Reply MENU to begin.",
        )
        return f"Approved #{request_id}"

    if normalized.startswith("NO "):
        tail = normalized.split(" ", 1)[1]
        if not tail.isdigit():
            return "Usage: NO <request_id>"
        request_id = int(tail)
        ok = set_invite_request_status(db, request_id, "denied")
        return f"Denied #{request_id}" if ok else "Request not found."

    return None


def _render_notifications(db: Database, phone_number: str) -> str:
    items = list_notifications(db, phone_number)
    if not items:
        return "No notifications."
    lines = [f"{idx}. {summarize_notification(item)}" for idx, item in enumerate(items, start=1)]
    return "Notifications: " + " | ".join(lines[:15])


def _apply_notification_action(db: Database, phone_number: str, action: str, index: int) -> str:
    items = list_notifications(db, phone_number)
    if index < 1 or index > len(items):
        return "Invalid notification index."
    target = items[index - 1]
    if action == "DELETE":
        update_notification_flags(db, target["id"], enabled=False, completed=True)
        return "Deleted."
    if action == "PAUSE":
        update_notification_flags(db, target["id"], enabled=False)
        return "Paused."
    if action == "RESUME":
        update_notification_flags(db, target["id"], enabled=True, completed=False)
        return "Resumed."
    return "Unsupported action."


async def _continue_session(db: Database, phone_number: str, normalized: str, state: str, draft: dict) -> str:
    if state == "await_remind_type":
        if normalized not in {"PRICE", "ONCE", "DAILY", "INTERVAL"}:
            return "Reply PRICE, ONCE, DAILY, or INTERVAL"
        draft["notification_type"] = {
            "PRICE": "price_alert",
            "ONCE": "one_time_reminder",
            "DAILY": "daily_reminder",
            "INTERVAL": "interval_reminder",
        }[normalized]
        if normalized == "PRICE":
            db.upsert_session(phone_number, "await_price_rule", draft)
            return "Format: SYMBOL ABOVE|BELOW PRICE. Example: AAPL ABOVE 210"
        if normalized == "ONCE":
            db.upsert_session(phone_number, "await_once_rule", draft)
            return "Format: YYYY-MM-DD HH:MM | message"
        if normalized == "DAILY":
            db.upsert_session(phone_number, "await_daily_rule", draft)
            return "Format: HH:MM | message"
        db.upsert_session(phone_number, "await_interval_rule", draft)
        return "Format: minutes|start YYYY-MM-DD HH:MM|stop YYYY-MM-DD HH:MM|message"

    if state == "await_price_rule":
        parts = normalized.split()
        if len(parts) != 3 or parts[1] not in {"ABOVE", "BELOW"}:
            return "Use: AAPL ABOVE 210"
        try:
            threshold = float(parts[2])
        except ValueError:
            return "Price must be numeric."
        create_notification(
            db,
            {
                "phone_number": phone_number,
                "notification_type": "price_alert",
                "symbol": parts[0],
                "condition": parts[1],
                "threshold": threshold,
                "message": f"Price alert {parts[0]} {parts[1]} {threshold}",
            },
        )
        db.clear_session(phone_number)
        return "Saved price alert."

    if state == "await_once_rule":
        if "|" not in normalized:
            return "Use: YYYY-MM-DD HH:MM | message"
        left, right = [x.strip() for x in normalized.split("|", 1)]
        try:
            due = datetime.strptime(left, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            return "Invalid datetime format."
        create_notification(
            db,
            {
                "phone_number": phone_number,
                "notification_type": "one_time_reminder",
                "due_at": due,
                "message": right,
            },
        )
        db.clear_session(phone_number)
        return "Saved one-time reminder."

    if state == "await_daily_rule":
        if "|" not in normalized:
            return "Use: HH:MM | message"
        left, right = [x.strip() for x in normalized.split("|", 1)]
        try:
            datetime.strptime(left, "%H:%M")
        except ValueError:
            return "Invalid time format."
        create_notification(
            db,
            {
                "phone_number": phone_number,
                "notification_type": "daily_reminder",
                "daily_time": left,
                "message": right,
            },
        )
        db.clear_session(phone_number)
        return "Saved daily reminder."

    if state == "await_interval_rule":
        chunks = [chunk.strip() for chunk in normalized.split("|")]
        if len(chunks) != 4:
            return "Use: minutes|start YYYY-MM-DD HH:MM|stop YYYY-MM-DD HH:MM|message"
        try:
            minutes = int(chunks[0])
            if minutes < 30:
                return "Minimum interval is 30 minutes."
            start_at = datetime.strptime(chunks[1], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).isoformat()
            stop_at = datetime.strptime(chunks[2], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            return "Invalid interval format."
        create_notification(
            db,
            {
                "phone_number": phone_number,
                "notification_type": "interval_reminder",
                "interval_minutes": minutes,
                "interval_start_at": start_at,
                "interval_stop_at": stop_at,
                "message": chunks[3],
            },
        )
        db.clear_session(phone_number)
        return "Saved interval reminder."

    db.clear_session(phone_number)
    return "Session reset. Send REMIND to start over."
