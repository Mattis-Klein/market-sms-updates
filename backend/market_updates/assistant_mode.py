from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from .db import Database
from .reminders import format_local_confirmation, parse_iso_or_natural_local_time, schedule_reminder


logger = logging.getLogger(__name__)

ASSIST_START_COMMAND = "@ASSIST"
ASSIST_EXIT_COMMANDS = {"@EXIT", "@ASSIST OFF"}
ASSIST_START_REPLY = "How can I assist you today?"
ASSIST_EXIT_REPLY = "Assistant mode closed. Reply MENU to see the main menu."
ASSIST_IMAGE_UNAVAILABLE_REPLY = (
    "Image generation is not available in this assistant. "
    "I can help with image descriptions, ad copy, or design instructions instead."
)
ASSIST_WEB_SEARCH_FAILURE_REPLY = "I couldn't access live information right now. Please try again shortly."
ASSIST_AI_FAILURE_REPLY = (
    "The AI assistant is temporarily unavailable. "
    "Please try again shortly or reply MENU to return to the main menu."
)

CARRIER_STOP_COMMANDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
CARRIER_START_COMMANDS = {"START", "YES", "UNSTOP"}
CARRIER_HELP_COMMANDS = {"HELP", "INFO"}

_IMAGE_REQUEST_PATTERNS = [
    r"\bgenerate\b.*\bimage\b",
    r"\bcreate\b.*\bimage\b",
    r"\bmake\b.*\bimage\b",
    r"\bedit\b.*\bimage\b",
    r"\bedit\b.*\bphoto\b",
    r"\bai art\b",
    r"\btext to image\b",
    r"\bdall[\s-]?e\b",
    r"\bmidjourney\b",
    r"\bstable diffusion\b",
]

_SEXUAL_BLOCK_PATTERNS = [
    r"\bporn\b",
    r"\bpornographic\b",
    r"\bexplicit sex\b",
    r"\bsexual roleplay\b",
    r"\berotic\b",
    r"\bsex chat\b",
    r"\bnudes?\b",
]

_DANGEROUS_BLOCK_PATTERNS = [
    r"\bbuild\b.*\bbomb\b",
    r"\bmake\b.*\bexplosive\b",
    r"\bhow to hack\b",
    r"\bsteal\b.*\bpassword\b",
    r"\bmalware\b",
    r"\bphishing\b",
]

_CURRENT_INFO_HINT_PATTERNS = [
    r"\bcurrent\b",
    r"\bcurrently\b",
    r"\blatest\b",
    r"\btoday\b",
    r"\btonight\b",
    r"\byesterday\b",
    r"\btomorrow\b",
    r"\brecent\b",
    r"\brecently\b",
    r"\bnews\b",
    r"\bnow\b",
    r"\blive\b",
    r"\bupdated\b",
    r"\bupdate\b",
    r"\bthis week\b",
    r"\bthis month\b",
    r"\bthis year\b",
    r"\bweather\b",
    r"\bscore\b",
    r"\bschedule\b",
    r"\bjackpot\b",
    r"\bprice\b",
    r"\bstore hours\b",
    r"\blocal events\b",
    r"\bavailability\b",
    r"\bversion\b",
    r"\brelease\b",
]


@dataclass
class ResponsesExecutionResult:
    text: str
    web_search_used: bool
    web_search_failed: bool


def assistant_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_phone_number(phone_number: str) -> str:
    if len(phone_number) <= 4:
        return "****"
    return f"***{phone_number[-4:]}"


def is_compliance_command(normalized: str) -> bool:
    return normalized in CARRIER_STOP_COMMANDS | CARRIER_START_COMMANDS | CARRIER_HELP_COMMANDS


def compliance_reply(normalized: str) -> str:
    if normalized in CARRIER_STOP_COMMANDS:
        return "You are unsubscribed. Reply START to re-subscribe."
    if normalized in CARRIER_START_COMMANDS:
        return "You are subscribed. Reply MENU to see available options."
    return "Help: Reply MENU to see available options. Reply STOP to unsubscribe."


def is_assist_start_command(normalized: str, incoming: str) -> bool:
    return incoming.strip() and incoming.strip().upper() == ASSIST_START_COMMAND and normalized == ASSIST_START_COMMAND


def is_assist_exit_command(normalized: str) -> bool:
    return normalized in ASSIST_EXIT_COMMANDS


def is_image_request(message: str) -> bool:
    text = message.lower()
    return any(re.search(pattern, text) for pattern in _IMAGE_REQUEST_PATTERNS)


def is_explicit_content_request(message: str) -> bool:
    text = message.lower()
    return any(re.search(pattern, text) for pattern in _SEXUAL_BLOCK_PATTERNS)


def is_dangerous_request(message: str) -> bool:
    text = message.lower()
    return any(re.search(pattern, text) for pattern in _DANGEROUS_BLOCK_PATTERNS)


def should_force_web_search(message: str, force_enabled: bool) -> bool:
    if not force_enabled:
        return False
    text = message.lower()
    return any(re.search(pattern, text) for pattern in _CURRENT_INFO_HINT_PATTERNS)


def trim_history(history: list[dict[str, str]], max_history_messages: int) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for item in history:
        role = item.get("role", "")
        content = item.get("content", "")
        if role not in {"user", "assistant"}:
            continue
        if not isinstance(content, str):
            continue
        cleaned.append({"role": role, "content": content[:1200]})
    if max_history_messages <= 0:
        return []
    return cleaned[-max_history_messages:]


def _safe_zoneinfo(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _fit_for_sms(text: str, max_chars: int) -> str:
    body = "\n".join(line.rstrip() for line in text.strip().splitlines() if line.strip())
    if len(body) <= max_chars:
        return body
    clipped = body[: max(120, max_chars - 120)].rstrip()
    return (
        f"{clipped}\n"
        "More is available. Reply with:\n"
        "1. Continue\n"
        "2. Short summary\n"
        "3. New question"
    )


def _is_eligible_for_fallback(error: httpx.HTTPError | Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status in {401, 403, 429, 500, 502, 503, 504}:
            return True
        return False
    if isinstance(error, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)):
        return True
    return False


def _build_reminder_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "schedule_reminder",
            "description": "Schedule a reminder when the user asks for one.",
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "reminder_text": {"type": "string"},
                    "scheduled_time_local": {"type": "string"},
                    "timezone": {"type": "string"},
                },
                "required": ["reminder_text", "scheduled_time_local", "timezone"],
            },
        },
        {
            "type": "function",
            "name": "list_reminders",
            "description": "List user's reminders.",
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "include_inactive": {"type": "boolean"},
                },
                "required": ["include_inactive"],
            },
        },
        {
            "type": "function",
            "name": "cancel_reminder",
            "description": "Cancel one reminder or all reminders.",
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "reminder_id": {"type": "integer"},
                    "match_text": {"type": "string"},
                    "cancel_all": {"type": "boolean"},
                    "confirm": {"type": "boolean"},
                },
                "required": ["reminder_id", "match_text", "cancel_all", "confirm"],
            },
        },
        {
            "type": "function",
            "name": "update_reminder",
            "description": "Update reminder text and/or reminder time.",
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "reminder_id": {"type": "integer"},
                    "new_reminder_text": {"type": "string"},
                    "new_scheduled_time_local": {"type": "string"},
                    "timezone": {"type": "string"},
                },
                "required": ["reminder_id", "new_reminder_text", "new_scheduled_time_local", "timezone"],
            },
        },
    ]


def _extract_output_text(response_data: dict) -> str:
    parts: list[str] = []
    output = response_data.get("output") or []
    for item in output:
        item_type = item.get("type")
        if item_type == "message":
            for content in item.get("content") or []:
                if content.get("type") in {"output_text", "text"}:
                    text = content.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
        if item_type == "output_text":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    if not parts and isinstance(response_data.get("output_text"), str):
        parts.append(response_data["output_text"].strip())
    return "\n".join(p for p in parts if p)


def _extract_function_calls(response_data: dict) -> list[dict[str, str]]:
    calls: list[dict[str, str]] = []
    output = response_data.get("output") or []
    for item in output:
        if item.get("type") == "function_call":
            calls.append(
                {
                    "call_id": str(item.get("call_id") or ""),
                    "name": str(item.get("name") or ""),
                    "arguments": str(item.get("arguments") or "{}"),
                }
            )
    return calls


def _extract_web_search_state(response_data: dict) -> tuple[bool, bool]:
    used = False
    failed = False
    output = response_data.get("output") or []
    for item in output:
        if item.get("type") == "web_search_call":
            used = True
            if str(item.get("status") or "").lower() in {"failed", "error"}:
                failed = True
    return used, failed


async def _request_responses_with_key(
    api_key: str,
    payload: dict[str, Any],
    base_url: str,
    timeout: float,
) -> tuple[dict | None, Exception | None]:
    if not api_key:
        return None, ValueError("API key is empty")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    max_retries = 2
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"{base_url}/responses", headers=headers, json=payload)
                response.raise_for_status()
                return response.json(), None
        except (httpx.HTTPError, httpx.NetworkError, httpx.TimeoutException) as exc:
            if attempt < max_retries - 1:
                continue
            return None, exc
        except Exception as exc:
            return None, exc

    return None, RuntimeError("responses_request_failed")


async def _call_openai_responses(payload: dict[str, Any], config: Any) -> tuple[dict | None, bool, bool]:
    if not config.openai_api_key_primary:
        logger.warning("openai_primary_key_not_configured")
        return None, False, False

    base_url = (config.assistant_ai_base_url or "https://api.openai.com/v1").rstrip("/")
    timeout = max(float(config.assistant_ai_timeout_seconds), 2.0)

    primary, primary_error = await _request_responses_with_key(
        api_key=config.openai_api_key_primary,
        payload=payload,
        base_url=base_url,
        timeout=timeout,
    )
    if primary is not None:
        logger.info("openai_primary_request_succeeded")
        return primary, True, False

    if primary_error is None or not _is_eligible_for_fallback(primary_error):
        logger.warning("both_openai_providers_failed")
        return None, False, False

    if not config.openai_api_key_fallback:
        logger.warning("both_openai_providers_failed")
        return None, False, False

    logger.info("openai_primary_failed_attempting_fallback")
    fallback, _ = await _request_responses_with_key(
        api_key=config.openai_api_key_fallback,
        payload=payload,
        base_url=base_url,
        timeout=timeout,
    )
    if fallback is not None:
        logger.info("openai_fallback_request_succeeded")
        return fallback, False, True

    logger.warning("both_openai_providers_failed")
    return None, False, False


def _render_list_reminders(items: list[dict]) -> str:
    if not items:
        return "No reminders found."
    lines = []
    for item in items[:10]:
        rid = item["id"]
        when = item.get("scheduled_at_local", "")
        tz_name = item.get("timezone", "")
        text = item.get("reminder_text", "")
        status = item.get("status", "")
        lines.append(f"#{rid} [{status}] {when} ({tz_name}) - {text}")
    return "\n".join(lines)


def _handle_schedule_reminder_tool(db: Database, phone_number: str, args: dict, config: Any) -> dict:
    reminder_text = str(args.get("reminder_text") or "").strip()
    scheduled_time_local = str(args.get("scheduled_time_local") or "").strip()
    timezone_name = str(args.get("timezone") or config.assist_default_timezone or "America/New_York").strip()

    if not reminder_text or not scheduled_time_local:
        return {"ok": False, "message": "Missing reminder details."}

    result = schedule_reminder(
        db=db,
        phone_number=phone_number,
        reminder_text=reminder_text,
        scheduled_time_local=scheduled_time_local,
        timezone_name=timezone_name,
    )
    if not result.get("ok"):
        if result.get("error") == "time_parse_failed":
            return {"ok": False, "message": "What time should I set for this reminder?"}
        if result.get("error") == "time_in_past":
            return {"ok": False, "message": "That time is in the past. Please provide a future time."}
        return {"ok": False, "message": "I could not schedule that reminder."}

    local_dt = parse_iso_or_natural_local_time(result["scheduled_at_local"], result["timezone"]).local_dt
    now_local = datetime.now(timezone.utc).astimezone(_safe_zoneinfo(result["timezone"]))
    pretty = format_local_confirmation(local_dt, now_local)
    confirmation = f"Reminder set for {pretty}: {reminder_text}."
    return {
        "ok": True,
        "id": result["id"],
        "scheduled_at_local": result["scheduled_at_local"],
        "scheduled_at_utc": result["scheduled_at_utc"],
        "timezone": result["timezone"],
        "confirmation": confirmation,
    }


def _handle_cancel_reminder_tool(db: Database, phone_number: str, args: dict) -> dict:
    reminder_id = int(args.get("reminder_id") or 0)
    match_text = str(args.get("match_text") or "").strip()
    cancel_all = bool(args.get("cancel_all"))
    confirm = bool(args.get("confirm"))

    if cancel_all:
        if not confirm:
            return {"ok": False, "message": "Please confirm delete all reminders by saying: Yes, delete all my reminders."}
        deleted = db.cancel_all_scheduled_reminders(phone_number)
        return {"ok": True, "deleted": deleted, "message": f"Cancelled {deleted} reminder(s)."}

    if reminder_id > 0:
        ok = db.cancel_scheduled_reminder(phone_number, reminder_id)
        return {"ok": ok, "message": "Reminder cancelled." if ok else "I could not find that reminder."}

    if match_text:
        count = db.cancel_scheduled_reminders_by_text(phone_number, match_text)
        return {"ok": count > 0, "message": f"Cancelled {count} reminder(s)." if count > 0 else "No matching reminder found."}

    return {"ok": False, "message": "Please specify which reminder to cancel."}


def _handle_update_reminder_tool(db: Database, phone_number: str, args: dict, config: Any) -> dict:
    reminder_id = int(args.get("reminder_id") or 0)
    text = str(args.get("new_reminder_text") or "").strip()
    local_time = str(args.get("new_scheduled_time_local") or "").strip()
    timezone_name = str(args.get("timezone") or config.assist_default_timezone or "America/New_York").strip()

    if reminder_id <= 0:
        return {"ok": False, "message": "Please provide a valid reminder id."}

    parsed = parse_iso_or_natural_local_time(local_time, timezone_name)
    if parsed is None:
        return {"ok": False, "message": "I could not parse that time. Please provide a clearer time."}

    utc_iso = parsed.local_dt.astimezone(timezone.utc).isoformat()
    local_iso = parsed.local_dt.isoformat()
    ok = db.update_scheduled_reminder(phone_number, reminder_id, text, utc_iso, local_iso, timezone_name)
    if not ok:
        return {"ok": False, "message": "I could not update that reminder."}

    now_local = datetime.now(timezone.utc).astimezone(ZoneInfo(timezone_name))
    pretty = format_local_confirmation(parsed.local_dt, now_local)
    return {"ok": True, "message": f"Reminder updated to {pretty}: {text}."}


async def _execute_responses_loop(
    payload: dict[str, Any],
    db: Database,
    phone_number: str,
    config: Any,
) -> ResponsesExecutionResult:
    web_used = False
    web_failed = False

    response, _, _ = await _call_openai_responses(payload, config)
    if response is None:
        return ResponsesExecutionResult(text=ASSIST_AI_FAILURE_REPLY, web_search_used=False, web_search_failed=False)

    max_turns = 4
    for _ in range(max_turns):
        used_now, failed_now = _extract_web_search_state(response)
        web_used = web_used or used_now
        web_failed = web_failed or failed_now

        function_calls = _extract_function_calls(response)
        if not function_calls:
            text = _extract_output_text(response)
            if not text:
                text = ASSIST_AI_FAILURE_REPLY
            return ResponsesExecutionResult(text=text, web_search_used=web_used, web_search_failed=web_failed)

        function_outputs = []
        for call in function_calls:
            call_id = call.get("call_id")
            name = call.get("name")
            try:
                args = json.loads(call.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}

            if name == "schedule_reminder":
                output_obj = _handle_schedule_reminder_tool(db, phone_number, args, config)
            elif name == "list_reminders":
                include_inactive = bool(args.get("include_inactive"))
                items = db.list_scheduled_reminders(phone_number, include_inactive=include_inactive)
                output_obj = {"ok": True, "items": items, "rendered": _render_list_reminders(items)}
            elif name == "cancel_reminder":
                output_obj = _handle_cancel_reminder_tool(db, phone_number, args)
            elif name == "update_reminder":
                output_obj = _handle_update_reminder_tool(db, phone_number, args, config)
            else:
                output_obj = {"ok": False, "message": "Unknown function."}

            function_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(output_obj),
                }
            )

        chained_payload = {
            "model": config.openai_model,
            "previous_response_id": response.get("id"),
            "input": function_outputs,
            "tools": payload.get("tools") or [],
            "tool_choice": "auto",
        }
        response, _, _ = await _call_openai_responses(chained_payload, config)
        if response is None:
            return ResponsesExecutionResult(text=ASSIST_AI_FAILURE_REPLY, web_search_used=web_used, web_search_failed=web_failed)

    return ResponsesExecutionResult(text=ASSIST_AI_FAILURE_REPLY, web_search_used=web_used, web_search_failed=web_failed)


async def generate_assistant_reply(
    config: Any,
    db: Database,
    phone_number: str,
    user_message: str,
    history: list[dict[str, str]],
) -> tuple[str, list[dict[str, str]]]:
    if is_image_request(user_message):
        updated_history = trim_history(
            history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": ASSIST_IMAGE_UNAVAILABLE_REPLY}],
            config.assistant_max_history_messages,
        )
        return ASSIST_IMAGE_UNAVAILABLE_REPLY, updated_history

    if is_explicit_content_request(user_message):
        refusal = (
            "I can't help with explicit sexual content. "
            "I can help with a non-explicit version, relationship advice, or general health information."
        )
        updated_history = trim_history(
            history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": refusal}],
            config.assistant_max_history_messages,
        )
        return refusal, updated_history

    if is_dangerous_request(user_message):
        refusal = "I can't help with dangerous, criminal, or abusive instructions. I can help with legal safety guidance instead."
        updated_history = trim_history(
            history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": refusal}],
            config.assistant_max_history_messages,
        )
        return refusal, updated_history

    tz_name = config.assist_default_timezone or "America/New_York"
    local_now = datetime.now(timezone.utc).astimezone(_safe_zoneinfo(tz_name))
    force_web = should_force_web_search(user_message, config.assist_force_web_for_current_info)

    system_prompt = (
        "You are an SMS assistant. Keep replies concise and direct. "
        "Never claim a web search happened unless a web_search tool call actually occurred. "
        "If web search fails, respond exactly: I couldn't access live information right now. Please try again shortly. "
        "When using relative time words like today, tomorrow, tonight, in 30 minutes, or next Friday, resolve them against the provided current date/time. "
        f"Current server date/time: {local_now.isoformat()}. User timezone: {tz_name}."
    )

    input_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    input_messages.extend(trim_history(history, config.assistant_max_history_messages))
    input_messages.append({"role": "user", "content": user_message})

    payload = {
        "model": config.openai_model,
        "input": input_messages,
        "tools": [{"type": "web_search"}] + _build_reminder_tools(),
        "tool_choice": "required" if force_web else "auto",
    }

    result = await _execute_responses_loop(payload, db, phone_number, config)

    if force_web and (result.web_search_failed or not result.web_search_used):
        reply = ASSIST_WEB_SEARCH_FAILURE_REPLY
    elif result.web_search_failed:
        reply = ASSIST_WEB_SEARCH_FAILURE_REPLY
    else:
        reply = result.text

    sms_reply = _fit_for_sms(reply, config.assistant_sms_max_chars)
    updated_history = trim_history(
        history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": sms_reply}],
        config.assistant_max_history_messages,
    )

    logger.info(
        "assistant_reply_generated",
        extra={
            "phone": mask_phone_number(phone_number),
            "message_length": len(user_message),
            "forced_web_search": force_web,
            "web_search_used": result.web_search_used,
            "web_search_failed": result.web_search_failed,
        },
    )
    return sms_reply, updated_history
