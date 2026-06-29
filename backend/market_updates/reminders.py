from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .db import Database


@dataclass
class ParsedLocalTime:
    local_dt: datetime
    timezone_name: str


def _normalize_for_hash(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _safe_zoneinfo(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def build_deduplication_key(phone_number: str, reminder_text: str, scheduled_at_local: str, timezone_name: str) -> str:
    normalized = "|".join(
        [
            _normalize_for_hash(phone_number),
            _normalize_for_hash(reminder_text),
            _normalize_for_hash(scheduled_at_local),
            _normalize_for_hash(timezone_name),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_natural_local_time(
    value: str,
    timezone_name: str,
    now_utc: datetime | None = None,
) -> ParsedLocalTime | None:
    tz_name = timezone_name or "America/New_York"
    tz = _safe_zoneinfo(tz_name)
    now = (now_utc or datetime.now(timezone.utc)).astimezone(tz)
    text = value.strip().lower()

    word_to_number = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
    }

    def _parse_hhmm(token: str, default_hour: int = 9) -> tuple[int, int] | None:
        token = token.strip().lower()
        am_pm_match = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", token)
        if am_pm_match:
            hour = int(am_pm_match.group(1))
            minute = int(am_pm_match.group(2) or "0")
            if am_pm_match.group(3) == "pm" and hour != 12:
                hour += 12
            if am_pm_match.group(3) == "am" and hour == 12:
                hour = 0
            return hour, minute

        twenty_four_match = re.match(r"^(\d{1,2}):(\d{2})$", token)
        if twenty_four_match:
            return int(twenty_four_match.group(1)), int(twenty_four_match.group(2))

        if token in {"morning"}:
            return 9, 0
        if token in {"afternoon"}:
            return 15, 0
        if token in {"evening", "tonight"}:
            return 19, 0
        return default_hour, 0

    if "half an hour" in text or "half hour" in text:
        return ParsedLocalTime(local_dt=now + timedelta(minutes=30), timezone_name=tz_name)

    mins_match = re.search(r"in\s+(\d+)\s+minutes?", text)
    if mins_match:
        return ParsedLocalTime(local_dt=now + timedelta(minutes=int(mins_match.group(1))), timezone_name=tz_name)

    if "in an hour" in text or "in a hour" in text:
        return ParsedLocalTime(local_dt=now + timedelta(hours=1), timezone_name=tz_name)

    hours_match = re.search(r"in\s+(\d+)\s+hours?", text)
    if hours_match:
        return ParsedLocalTime(local_dt=now + timedelta(hours=int(hours_match.group(1))), timezone_name=tz_name)

    day_word_match = re.search(r"in\s+(\w+)\s+days?", text)
    if day_word_match:
        token = day_word_match.group(1)
        count = int(token) if token.isdigit() else word_to_number.get(token)
        if count:
            target = now + timedelta(days=count)
            return ParsedLocalTime(local_dt=target.replace(hour=9, minute=0, second=0, microsecond=0), timezone_name=tz_name)

    if text.startswith("tomorrow"):
        target = now + timedelta(days=1)
        if "morning" in text:
            hour, minute = 9, 0
        elif "afternoon" in text:
            hour, minute = 15, 0
        elif "evening" in text or "tonight" in text:
            hour, minute = 19, 0
        else:
            time_match = re.search(r"tomorrow\s+at\s+(.+)$", text)
            hour, minute = _parse_hhmm(time_match.group(1) if time_match else "", default_hour=9)
        return ParsedLocalTime(local_dt=target.replace(hour=hour, minute=minute, second=0, microsecond=0), timezone_name=tz_name)

    if text == "tonight":
        target = now
        hour, minute = 19, 0
        if target.hour >= hour:
            target = target + timedelta(days=1)
        return ParsedLocalTime(local_dt=target.replace(hour=hour, minute=minute, second=0, microsecond=0), timezone_name=tz_name)

    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    for name, idx in weekday_map.items():
        if f"next {name}" in text or f"this {name}" in text or text == name or text.startswith(name + " "):
            days_ahead = (idx - now.weekday()) % 7
            if f"next {name}" in text and days_ahead == 0:
                days_ahead = 7
            target = now + timedelta(days=days_ahead)
            if "afternoon" in text:
                hour, minute = 15, 0
            elif "evening" in text:
                hour, minute = 19, 0
            elif "morning" in text:
                hour, minute = 9, 0
            else:
                at_match = re.search(r"at\s+(.+)$", text)
                hour, minute = _parse_hhmm(at_match.group(1) if at_match else "", default_hour=9)
            return ParsedLocalTime(local_dt=target.replace(hour=hour, minute=minute, second=0, microsecond=0), timezone_name=tz_name)

    month_day_time = re.search(r"([a-z]+)\s+(\d{1,2})\s+at\s+(.+)$", text)
    if month_day_time:
        month_name, day_str, at_part = month_day_time.groups()
        month_map = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }
        month = month_map.get(month_name)
        if month:
            hour, minute = _parse_hhmm(at_part, default_hour=9)
            year = now.year
            try:
                target = datetime(year, month, int(day_str), hour, minute, tzinfo=tz)
            except ValueError:
                return None
            if target <= now:
                target = target.replace(year=year + 1)
            return ParsedLocalTime(local_dt=target, timezone_name=tz_name)

    at_time = re.search(r"^at\s+(.+)$", text)
    if at_time:
        hour, minute = _parse_hhmm(at_time.group(1), default_hour=9)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return ParsedLocalTime(local_dt=target, timezone_name=tz_name)

    return None


def parse_iso_or_natural_local_time(
    value: str,
    timezone_name: str,
    now_utc: datetime | None = None,
) -> ParsedLocalTime | None:
    if not value:
        return None

    tz_name = timezone_name or "America/New_York"
    tz = _safe_zoneinfo(tz_name)

    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        else:
            dt = dt.astimezone(tz)
        return ParsedLocalTime(local_dt=dt, timezone_name=tz_name)
    except ValueError:
        return parse_natural_local_time(value, tz_name, now_utc)


def format_local_confirmation(dt_local: datetime, now_local: datetime) -> str:
    same_day = dt_local.date() == now_local.date()
    tomorrow = dt_local.date() == (now_local.date()).fromordinal(now_local.date().toordinal() + 1)
    time_part = dt_local.strftime("%I:%M %p").lstrip("0")

    if same_day:
        return f"{time_part} today"
    if tomorrow:
        return f"{time_part} tomorrow"
    month_day = dt_local.strftime("%B %d").replace(" 0", " ")
    return f"{dt_local.strftime('%A')}, {month_day} at {time_part}"


def schedule_reminder(
    db: Database,
    phone_number: str,
    reminder_text: str,
    scheduled_time_local: str,
    timezone_name: str,
) -> dict:
    parsed = parse_iso_or_natural_local_time(scheduled_time_local, timezone_name)
    if parsed is None:
        return {"ok": False, "error": "time_parse_failed"}

    local_dt = parsed.local_dt
    utc_dt = local_dt.astimezone(timezone.utc)
    if utc_dt <= datetime.now(timezone.utc):
        return {"ok": False, "error": "time_in_past"}

    local_iso = local_dt.isoformat()
    utc_iso = utc_dt.isoformat()
    dedup = build_deduplication_key(phone_number, reminder_text, local_iso, parsed.timezone_name)
    reminder_id = db.create_scheduled_reminder(
        phone_number=phone_number,
        reminder_text=reminder_text.strip(),
        scheduled_at_utc=utc_iso,
        scheduled_at_local=local_iso,
        timezone_name=parsed.timezone_name,
        deduplication_key=dedup,
    )

    return {
        "ok": True,
        "id": reminder_id,
        "scheduled_at_utc": utc_iso,
        "scheduled_at_local": local_iso,
        "timezone": parsed.timezone_name,
    }
