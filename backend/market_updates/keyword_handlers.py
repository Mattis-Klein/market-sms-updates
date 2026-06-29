from __future__ import annotations

import logging
from datetime import datetime, timezone

from .assistant_mode import (
    ASSIST_EXIT_REPLY,
    ASSIST_START_REPLY,
    assistant_now,
    compliance_reply,
    generate_assistant_reply,
    is_assist_exit_command,
    is_assist_start_command,
    is_compliance_command,
)

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
from .keywords import (
    list_supported_tickers,
    lookup_tickers,
    normalize_text,
    parse_check_symbols,
    parse_datecheck,
    parse_direct_symbol,
    parse_list_action,
)
from .lottery import get_powerball_summary
from .market_data import get_historical_close, get_latest_quote
from .notifications import create_notification, list_notifications, summarize_notification, update_notification_flags
from .profiles import POWERBALL_ONLY_PROFILE, get_user_profile
from .sms_sender import send_sms
from .youtube_service import MRBEAST_CHANNEL_ID, LivecountsServiceError, format_subscriber_count, get_channel_subscriber_count


logger = logging.getLogger(__name__)
COMMAND_PREFIXES = ("CHECK", "DATECHECK", "TICKER", "LOOKUP", "FIND", "SYMBOL", "FEEDBACK", "CANCELREMINDER")


MENU_TEXT = (
    "Market SMS Assistant\n"
    "Reply with a number to get the next step:\n"
    "1. Check live prices\n"
    "2. Check historical close\n"
    "3. Find ticker symbol\n"
    "4. BEAST\n"
    "5. REMIND\n"
    "6. LIST\n"
    "7. CANCELREMINDER <index>\n"
    "8. FEEDBACK <message>\n"
    "9. TICKERS\n"
    "10. SYMBOL <name>\n"
    "Tip: send a ticker like AAPL directly for a quick quote."
)

MENU_NUMBER_HELP = {
    "1": "Send: CHECK <ticker1 ticker2 ...>. Example: CHECK AAPL TSLA ^GSPC",
    "2": "Send: DATECHECK YYYY-MM-DD <ticker1 ticker2 ...>. Example: DATECHECK 2026-01-15 AAPL",
    "3": "Send: SYMBOL <word or phrase> and I'll return matching tickers. Example: SYMBOL S&P",
    "4": "Send: BEAST",
    "5": "Send: REMIND to start reminder setup.",
    "6": "Send: LIST to view your notifications.",
    "7": "Send: CANCELREMINDER <index>. Example: CANCELREMINDER 1",
    "8": "Send: FEEDBACK <message>",
    "9": "Send: TICKERS to list supported symbols.",
    "10": "Send: SYMBOL <name>. Example: SYMBOL S&P",
}

GLOBAL_COMMANDS = {
    "MENU",
    "REMIND",
    "TICKERS",
    "SYMBOL",
    "CHECK",
    "DATECHECK",
    "TICKER",
    "LOOKUP",
    "FIND",
    "BEAST",
    "FEEDBACK",
    "LIST",
    "NOTIFICATIONS",
    "ALERTS",
    "CANCELREMINDER",
}

COMMAND_ALIASES = {
    "@MRBEAST": "BEAST",
}

REMINDER_MENU_NUMBER_MAP = {
    "1": "PRICE",
    "2": "ONCE",
    "3": "DAILY",
    "4": "INTERVAL",
}

POWERBALL_MENU_TEXT = (
    "Market SMS Alerts - Powerball menu:\n"
    "PB/POWERBALL = full update\n"
    "JACKPOT = jackpot\n"
    "NUMBERS = last draw\n"
    "GUIDE = how to use\n"
    "Next: reply POWERBALL, JACKPOT, NUMBERS, or GUIDE.\n"
    "Reply STOP to unsubscribe. Reply HELP for help."
)

POWERBALL_GUIDE_TEXT = (
    "How to use this:\n"
    "POWERBALL/PB = full update\n"
    "JACKPOT = jackpot only\n"
    "NUMBERS = last draw\n"
    "MENU = choices\n"
    "Next: reply POWERBALL, JACKPOT, NUMBERS, or MENU."
)

POWERBALL_BLOCKED_TEXT = (
    "That word is not available here.\n"
    "Use POWERBALL, JACKPOT, NUMBERS, GUIDE, or MENU.\n"
    "Next: reply MENU to see the choices."
)

POWERBALL_FETCH_FAILURE_TEXT = (
    "I could not get the Powerball info right now.\n"
    "Next: reply MENU or try POWERBALL again later."
)


def _twiml_message(body: str) -> str:
    escaped = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{escaped}</Message></Response>"


async def handle_inbound_sms(db: Database, config: MarketConfig, from_number: str, body: str) -> str:
    sender = normalize_phone_number(from_number)
    incoming = body.strip()
    normalized = normalize_text(incoming)
    profile = get_user_profile(sender)

    if normalized in COMMAND_ALIASES:
        normalized = COMMAND_ALIASES[normalized]

    direct_symbol = parse_direct_symbol(normalized)
    if _is_dedicated_command(normalized, direct_symbol):
        direct_symbol = None if (normalized in GLOBAL_COMMANDS or normalized.startswith(COMMAND_PREFIXES)) else direct_symbol

    if is_compliance_command(normalized):
        if db.get_session(sender):
            db.clear_session(sender)
        db.deactivate_assistant_session(sender)
        return _twiml_message(compliance_reply(normalized))

    if sender == normalize_phone_number(config.market_access_approver_number):
        approver_reply = await _handle_approver_message(db, config, normalized)
        if approver_reply:
            return _twiml_message(approver_reply)

    if not (
        profile
        or is_allowlisted(db, sender)
        or is_permanent_allowlisted(config.market_updates_allowed_numbers, sender)
    ):
        blocked = await _handle_unapproved_sender(db, config, sender, incoming, normalized)
        return _twiml_message(blocked)

    if profile == POWERBALL_ONLY_PROFILE:
        if db.get_session(sender):
            db.clear_session(sender)
        db.deactivate_assistant_session(sender)
        return _twiml_message(await _handle_powerball_only_profile(normalized))

    session = db.get_session(sender)

    if is_assist_start_command(normalized, incoming):
        if session and _is_critical_session_state(session["state"]):
            return _twiml_message("Finish or cancel your current confirmation step first. Reply STOP to cancel it.")
        if session:
            db.clear_session(sender)
        now = assistant_now()
        db.activate_assistant_session(sender, now, now)
        logger.info("assistant_mode_started", extra={"phone": sender[-4:]})
        return _twiml_message(ASSIST_START_REPLY)

    active_assistant_session = db.get_active_assistant_session(sender, config.assistant_session_expiration_minutes)

    # Assistant mode routing is evaluated before all app keywords and workflows.
    if active_assistant_session:
        if is_assist_exit_command(normalized):
            db.deactivate_assistant_session(sender)
            logger.info("assistant_mode_closed", extra={"phone": sender[-4:]})
            return _twiml_message(ASSIST_EXIT_REPLY)

        response, new_history = await generate_assistant_reply(
            config=config,
            db=db,
            phone_number=sender,
            user_message=incoming,
            history=active_assistant_session.get("assistant_conversation_history", []),
        )
        now = assistant_now()
        db.upsert_assistant_session(
            phone_number=sender,
            assistant_mode_active=True,
            assistant_started_at=active_assistant_session.get("assistant_started_at") or now,
            assistant_last_activity_at=now,
            assistant_conversation_history=new_history,
        )
        return _twiml_message(response)

    if session and session["state"] == "await_remind_type" and normalized in REMINDER_MENU_NUMBER_MAP:
        direct_symbol = None

    if _is_dedicated_command(normalized, direct_symbol):
        if session:
            db.clear_session(sender)
    elif session:
        return _twiml_message(await _continue_session(db, sender, normalized, session["state"], session["draft"]))

    if normalized in MENU_NUMBER_HELP:
        return _twiml_message(MENU_NUMBER_HELP[normalized])

    if normalized == "MENU":
        return _twiml_message(MENU_TEXT)

    if normalized.startswith("CHECK"):
        symbols = parse_check_symbols(normalized)
        if not symbols:
            return _twiml_message("Usage:\n1. CHECK BTC-USD AAPL TSLA\n2. CHECK BRK.B ^GSPC")
        lines = []
        for symbol in symbols:
            result = await get_latest_quote(symbol)
            if not result["available"]:
                lines.append(f"{symbol}: unavailable")
            else:
                regular_market_price = result.get("regularMarketPrice", result["price"])
                lines.append(
                    f"{result['symbol']}: ${regular_market_price:.2f} ({result['change']:+.2f}, {result['change_pct']:+.2f}%)"
                )
        return _twiml_message("\n".join(lines))

    if normalized.startswith("DATECHECK"):
        parsed = parse_datecheck(normalized)
        if not parsed:
            return _twiml_message("Usage:\n1. DATECHECK YYYY-MM-DD AAPL TSLA\n2. DATECHECK 2026-01-15 BRK.B ^GSPC")
        lines = []
        for symbol in parsed["symbols"]:
            result = await get_historical_close(symbol, parsed["date"])
            if not result["available"]:
                lines.append(f"{symbol}: unavailable")
            else:
                lines.append(f"{symbol} {result['actual_date']}: ${result['close']:.2f}")
        return _twiml_message("\n".join(lines))

    if normalized == "TICKERS":
        results = list_supported_tickers()
        if not results:
            return _twiml_message("No tickers available right now.")
        lines = [f"{item['symbol']} - {item['name']}" for item in results[:20]]
        return _twiml_message("Supported tickers:\n" + "\n".join(lines))

    if normalized.startswith(("TICKER", "LOOKUP", "FIND")):
        query = incoming.split(" ", 1)[1] if " " in incoming else ""
        results = lookup_tickers(query)
        if not results:
            return _twiml_message("No ticker matches found.")
        preview = [f"{item['symbol']} - {item['name']}" for item in results[:8]]
        return _twiml_message("Matches:\n" + "\n".join(preview))

    if normalized.startswith("SYMBOL"):
        query = incoming.split(" ", 1)[1] if " " in incoming else ""
        if not query.strip():
            return _twiml_message("Usage: SYMBOL <name or keyword>. Example: SYMBOL S&P")
        results = lookup_tickers(query)
        if not results:
            return _twiml_message("No ticker matches found.")
        preview = [f"{item['symbol']} - {item['name']}" for item in results[:8]]
        return _twiml_message("Matches:\n" + "\n".join(preview))

    if direct_symbol:
        try:
            result = await get_latest_quote(direct_symbol)
        except Exception:
            return _twiml_message("I couldn't check that ticker right now. Try again soon.")
        if not result["available"]:
            return _twiml_message(f"{direct_symbol}: unavailable")
        regular_market_price = result.get("regularMarketPrice", result["price"])
        return _twiml_message(
            f"{result['symbol']}: ${regular_market_price:.2f} ({result['change']:+.2f}, {result['change_pct']:+.2f}%)"
        )

    if normalized == "BEAST":
        try:
            count = await get_channel_subscriber_count(MRBEAST_CHANNEL_ID)
        except LivecountsServiceError:
            return _twiml_message("I couldn't check MrBeast subscribers right now. Try again soon.")
        except Exception:
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
        return _twiml_message(
            "Reminder type. Reply with one option:\n"
            "1. PRICE\n"
            "2. ONCE\n"
            "3. DAILY\n"
            "4. INTERVAL"
        )

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


def _is_critical_session_state(state: str) -> bool:
    critical_states = set()
    return state in critical_states


def _is_dedicated_command(normalized: str, direct_symbol: str | None) -> bool:
    return normalized in GLOBAL_COMMANDS or normalized.startswith(COMMAND_PREFIXES) or bool(direct_symbol)


async def _handle_powerball_only_profile(normalized: str) -> str:
    if normalized == "STOP":
        return (
            "Market SMS Alerts: You are unsubscribed.\n"
            "Next: reply START to re-subscribe.\n"
            "Reply HELP for help."
        )

    if normalized == "START":
        return (
            "Market SMS Alerts: You are subscribed.\n"
            "Next: reply MENU for commands."
        )

    if normalized == "HELP":
        return (
            "Market SMS Alerts help.\n"
            "Commands: MENU, POWERBALL/PB, JACKPOT, NUMBERS, GUIDE.\n"
            "Next: reply MENU for commands.\n"
            "Reply STOP to unsubscribe."
        )

    if normalized in {"MENU", "CHECK", "LOTTO"}:
        return POWERBALL_MENU_TEXT

    if normalized == "GUIDE":
        return POWERBALL_GUIDE_TEXT

    if normalized in {"POWERBALL", "PB"}:
        try:
            summary = await get_powerball_summary()
        except Exception:
            return POWERBALL_FETCH_FAILURE_TEXT
        return (
            "Powerball update:\n"
            f"Jackpot: {_pb_value(summary, 'next_jackpot')} | Cash: {_pb_value(summary, 'cash_option')}\n"
            f"Next draw: {_pb_value(summary, 'next_draw_date')}\n"
            f"Last {_pb_value(summary, 'latest_draw_date')}: {_pb_value(summary, 'white_numbers')} PB {_pb_value(summary, 'powerball')}\n"
            f"Power Play: {_pb_value(summary, 'power_play')}\n"
            "Next: reply JACKPOT, NUMBERS, GUIDE, or MENU."
        )

    if normalized == "JACKPOT":
        try:
            summary = await get_powerball_summary()
        except Exception:
            return POWERBALL_FETCH_FAILURE_TEXT
        return (
            "Powerball jackpot:\n"
            f"Jackpot: {_pb_value(summary, 'next_jackpot')} | Cash: {_pb_value(summary, 'cash_option')}\n"
            f"Next draw: {_pb_value(summary, 'next_draw_date')}\n"
            "Next: reply POWERBALL for all info, NUMBERS for last numbers, or MENU."
        )

    if normalized == "NUMBERS":
        try:
            summary = await get_powerball_summary()
        except Exception:
            return POWERBALL_FETCH_FAILURE_TEXT
        return (
            "Last Powerball numbers:\n"
            f"Draw date: {_pb_value(summary, 'latest_draw_date')}\n"
            f"Numbers: {_pb_value(summary, 'white_numbers')}\n"
            f"Powerball: {_pb_value(summary, 'powerball')} | Power Play: {_pb_value(summary, 'power_play')}\n"
            "Next: reply JACKPOT for the jackpot, POWERBALL for all info, or MENU."
        )

    return POWERBALL_BLOCKED_TEXT


def _pb_value(summary: dict, key: str) -> str:
    value = summary.get(key)
    if value is None:
        return "N/A"
    text = str(value).strip()
    return text or "N/A"


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
        return "Pending:\n" + "\n".join(lines)

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
    return "Notifications:\n" + "\n".join(lines[:15])


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
        normalized = REMINDER_MENU_NUMBER_MAP.get(normalized, normalized)
        if normalized not in {"PRICE", "ONCE", "DAILY", "INTERVAL"}:
            return "Reply with one option:\n1. PRICE\n2. ONCE\n3. DAILY\n4. INTERVAL"
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
