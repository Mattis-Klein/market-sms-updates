from __future__ import annotations

import re

import httpx

from .cache import CACHE
from .models import LiveDataResult, utc_now_iso


_RELIABLE_SOURCES_HINT = "Reuters, AP, BBC, NPR, WSJ, Bloomberg, CNBC"


def _safe_error(message: str, raw_status: str = "error") -> LiveDataResult:
    return LiveDataResult(
        success=False,
        provider="openai_web_search",
        retrieved_at_utc=utc_now_iso(),
        source_timestamp_utc=None,
        is_live=False,
        is_delayed=False,
        delay_minutes=None,
        confidence="low",
        raw_status=raw_status,
        human_summary=message,
        safe_error=message,
    )


def _extract_text(response_data: dict) -> str:
    parts: list[str] = []
    for item in response_data.get("output") or []:
        if item.get("type") == "message":
            for content in item.get("content") or []:
                if content.get("type") in {"output_text", "text"}:
                    text = content.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
    return "\n".join(parts).strip()


async def get_current_news(config, query: str) -> LiveDataResult:
    provider = (getattr(config, "news_provider", "openai_web_search") or "openai_web_search").lower()
    if provider != "openai_web_search":
        return _safe_error("I couldn't get reliable live data right now. Please try again shortly.", "unsupported_news_provider")

    cache_seconds = int(getattr(config, "news_cache_seconds", 120) or 120)
    max_results = int(getattr(config, "news_max_results", 5) or 5)
    cache_key = f"news:{provider}:{query.lower().strip()}:{max_results}"
    cached, stale = CACHE.get(cache_key)
    if isinstance(cached, LiveDataResult) and not stale and not cached.safe_error:
        return cached

    api_key = getattr(config, "openai_api_key_primary", "")
    if not api_key:
        return _safe_error("I couldn't get reliable live data right now. Please try again shortly.", "missing_api_key")

    base_url = (getattr(config, "assistant_ai_base_url", "https://api.openai.com/v1") or "https://api.openai.com/v1").rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    prompt = (
        "Provide current news in plain SMS text with short numbered lines. "
        "Use reliable sources only. Prefer Reuters, AP, BBC, NPR, WSJ, Bloomberg, CNBC, or official sources. "
        "Do not include URLs, markdown, citation markers, or links. "
        f"Limit to {max_results} items and include source names only. "
        f"User request: {query}"
    )

    payload = {
        "model": getattr(config, "openai_model", "gpt-4o-mini"),
        "input": [
            {"role": "system", "content": "You are a current news summarizer for SMS."},
            {"role": "user", "content": prompt},
        ],
        "tools": [{"type": "web_search"}],
        "tool_choice": "required",
    }

    try:
        async with httpx.AsyncClient(timeout=float(getattr(config, "assistant_ai_timeout_seconds", 20) or 20)) as client:
            response = await client.post(f"{base_url}/responses", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        result = _safe_error("I couldn't get reliable live data right now. Please try again shortly.", f"http_{status}")
        CACHE.set(cache_key, result, cache_seconds, cache_seconds, is_error=True)
        return result
    except Exception:
        result = _safe_error("I couldn't get reliable live data right now. Please try again shortly.", "search_error")
        CACHE.set(cache_key, result, cache_seconds, cache_seconds, is_error=True)
        return result

    used_web_search = False
    for item in data.get("output") or []:
        if item.get("type") == "web_search_call":
            used_web_search = True
            break
    if not used_web_search:
        result = _safe_error("I couldn't access live information right now. Please try again shortly.", "missing_web_search_call")
        CACHE.set(cache_key, result, cache_seconds, cache_seconds, is_error=True)
        return result

    text = _extract_text(data)
    if not text:
        result = _safe_error("I couldn't get reliable live data right now. Please try again shortly.", "empty_news")
        CACHE.set(cache_key, result, cache_seconds, cache_seconds, is_error=True)
        return result

    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    result = LiveDataResult(
        success=True,
        provider=provider,
        retrieved_at_utc=utc_now_iso(),
        source_timestamp_utc=utc_now_iso(),
        is_live=True,
        is_delayed=False,
        delay_minutes=None,
        confidence="medium",
        raw_status="ok",
        human_summary=text,
        data={"reliable_sources_hint": _RELIABLE_SOURCES_HINT, "web_search_used": True},
    )
    CACHE.set(cache_key, result, cache_seconds, cache_seconds)
    return result
