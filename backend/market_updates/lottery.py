from __future__ import annotations

from datetime import datetime, timezone
import os
import time
from typing import Any

import httpx


POWERBALL_RECENT_URL = "https://www.powerball.com/api/v1/numbers/powerball/recent10?_format=json"
POWERBALL_ESTIMATES_URL = "https://www.powerball.com/api/v1/estimates/powerball?_format=json"
POWERBALL_SOURCE = "Official Powerball"

_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "value": None,
}


class PowerballServiceError(Exception):
    pass


def _cache_ttl_seconds() -> int:
    raw = os.getenv("POWERBALL_CACHE_TTL_SECONDS", "900")
    try:
        return max(0, int(raw))
    except ValueError:
        return 900


def _coalesce(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return "N/A"


def _normalize_date(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        return "N/A"
    text = text.replace("Z", "+00:00")
    for parser in (datetime.fromisoformat,):
        try:
            parsed = parser(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.date().isoformat()
        except ValueError:
            continue
    if len(text) >= 10:
        return text[:10]
    return text


def _normalize_whites(value: Any) -> str:
    if isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
        return " ".join(values) if values else "N/A"
    text = str(value).strip() if value is not None else ""
    if not text:
        return "N/A"
    tokens = [token for token in text.replace(",", " ").split() if token]
    return " ".join(tokens) if tokens else "N/A"


def _pick_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "results", "data", "drawings"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _latest_draw(payload: Any) -> dict[str, Any]:
    draws = _pick_list(payload)
    if not draws:
        raise PowerballServiceError("powerball latest draw payload missing")
    return draws[0]


def _next_draw(payload: Any) -> dict[str, Any]:
    draws = _pick_list(payload)
    return draws[0] if draws else {}


async def _fetch_json(client: httpx.AsyncClient, url: str) -> Any:
    response = await client.get(
        url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        },
    )
    response.raise_for_status()
    return response.json()


async def _fetch_powerball_summary_uncached() -> dict[str, str]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        recent_payload = await _fetch_json(client, POWERBALL_RECENT_URL)
        estimates_payload = await _fetch_json(client, POWERBALL_ESTIMATES_URL)

    latest = _latest_draw(recent_payload)
    upcoming = _next_draw(estimates_payload)

    white_numbers = _normalize_whites(
        latest.get("field_white_balls")
        or latest.get("white_numbers")
        or latest.get("winning_numbers")
        or latest.get("field_winning_numbers")
    )
    powerball = _coalesce(
        latest.get("field_powerball"),
        latest.get("powerball"),
        latest.get("power_ball"),
    )
    power_play = _coalesce(
        latest.get("field_multiplier"),
        latest.get("multiplier"),
        latest.get("power_play"),
    )

    summary = {
        "next_jackpot": _coalesce(
            upcoming.get("field_amount") if isinstance(upcoming, dict) else None,
            upcoming.get("amount") if isinstance(upcoming, dict) else None,
            upcoming.get("jackpot") if isinstance(upcoming, dict) else None,
            latest.get("field_jackpot"),
            latest.get("jackpot"),
        ),
        "cash_option": _coalesce(
            upcoming.get("field_cash_value") if isinstance(upcoming, dict) else None,
            upcoming.get("cash_value") if isinstance(upcoming, dict) else None,
            upcoming.get("cash_option") if isinstance(upcoming, dict) else None,
            latest.get("field_cash_value"),
            latest.get("cash_value"),
        ),
        "next_draw_date": _normalize_date(
            upcoming.get("field_draw_date") if isinstance(upcoming, dict) else None,
        ),
        "latest_draw_date": _normalize_date(
            latest.get("field_draw_date") or latest.get("draw_date") or latest.get("date"),
        ),
        "white_numbers": white_numbers,
        "powerball": powerball,
        "power_play": power_play,
        "jackpot_winner_status": _coalesce(
            latest.get("jackpot_winner_status"),
            latest.get("winner_status"),
            "N/A",
        ),
        "source": POWERBALL_SOURCE,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    return summary


async def get_powerball_summary() -> dict[str, str]:
    now = time.time()
    cached = _CACHE.get("value")
    expires_at = float(_CACHE.get("expires_at") or 0.0)
    if cached and expires_at > now:
        return dict(cached)

    try:
        summary = await _fetch_powerball_summary_uncached()
    except Exception as exc:
        raise PowerballServiceError("powerball fetch failed") from exc

    ttl = _cache_ttl_seconds()
    _CACHE["value"] = dict(summary)
    _CACHE["expires_at"] = now + ttl
    return summary


def reset_powerball_cache_for_tests() -> None:
    _CACHE["value"] = None
    _CACHE["expires_at"] = 0.0
