from __future__ import annotations

import httpx
import logging
import re
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
import time


logger = logging.getLogger(__name__)

ASSIST_START_COMMAND = "@ASSIST"
ASSIST_EXIT_COMMANDS = {"EXIT", "EXIT ASSIST", "MENU", "MAIN MENU"}
ASSIST_START_REPLY = "How can I assist you today?"
ASSIST_EXIT_REPLY = "Assistant mode closed. Reply MENU to see available options."
ASSIST_IMAGE_UNAVAILABLE_REPLY = (
    "Image generation is not available in this assistant. "
    "I can help you write an image description, advertisement layout, or design instructions instead."
)
ASSIST_WEB_SEARCH_FAILURE_REPLY = (
    "I couldn't access live web results right now. "
    "I can still give you a general answer, but current details may need verification."
)
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

_WEB_HINT_PATTERNS = [
    r"\bright now\b",
    r"\bcurrent\b",
    r"\btoday\b",
    r"\blatest\b",
    r"\brecent\b",
    r"\bnews\b",
    r"\bweather\b",
    r"\bforecast\b",
    r"\bjackpot\b",
    r"\bscore\b",
    r"\bschedule\b",
    r"\bprice\b",
    r"\bcost\b",
    r"\bavailability\b",
    r"\bversion\b",
    r"\brelease\b",
    r"\bnear me\b",
    r"\bopen now\b",
]


@dataclass
class WebSearchResult:
    title: str
    source: str
    url: str
    publication_date: str
    snippet: str


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


def should_use_web_search(message: str) -> bool:
    text = message.lower()
    return any(re.search(pattern, text) for pattern in _WEB_HINT_PATTERNS)


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


def _is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False
    except ValueError:
        pass
    return True


def _source_name_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host or "unknown"


async def search_web(query: str, config: Any) -> list[WebSearchResult]:
    provider = (config.assistant_search_provider or "tavily").lower().strip()
    if provider != "tavily":
        raise RuntimeError(f"Unsupported search provider: {provider}")

    if not config.assistant_search_api_key:
        raise RuntimeError("Search provider API key is not configured")

    payload = {
        "api_key": config.assistant_search_api_key,
        "query": query,
        "max_results": max(1, min(config.assistant_search_max_results, 8)),
        "search_depth": "basic",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
    }

    timeout = max(float(config.assistant_search_timeout_seconds), 1.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post("https://api.tavily.com/search", json=payload)
        response.raise_for_status()
        data = response.json()

    results: list[WebSearchResult] = []
    for item in data.get("results", []):
        url = str(item.get("url", "")).strip()
        if not _is_safe_url(url):
            continue
        title = str(item.get("title", "")).strip()[:200]
        content = str(item.get("content", "")).strip()[:700]
        publication_date = str(item.get("published_date", "") or "").strip()[:50]
        results.append(
            WebSearchResult(
                title=title or "Untitled",
                source=_source_name_from_url(url),
                url=url,
                publication_date=publication_date or "N/A",
                snippet=content,
            )
        )
        if len(results) >= max(1, min(config.assistant_search_max_results, 8)):
            break
    return results


def _is_eligible_for_fallback(error: httpx.HTTPError | Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 401:
            return True
        if status == 429:
            return True
        if status in {500, 502, 503, 504}:
            return True
        if status == 400:
            try:
                data = error.response.json()
                error_code = data.get("error", {}).get("code", "")
                if error_code in {"invalid_api_key", "invalid_request_error"}:
                    return True
            except Exception:
                pass
            return False
        return False
    if isinstance(error, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)):
        return True
    return False


async def _call_ai_chat_completion_with_key(
    messages: list[dict[str, str]],
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
) -> tuple[str | None, httpx.HTTPError | Exception | None]:
    if not api_key:
        return None, ValueError("API key is empty")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    max_retries = 2
    backoff_base = 1.0

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            choices = data.get("choices") or []
            if not choices:
                return None, ValueError("No choices in response")
            content = choices[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
            if not isinstance(content, str) or not content.strip():
                return None, ValueError("Invalid content in response")
            return content.strip(), None
        except (httpx.HTTPError, httpx.NetworkError, httpx.TimeoutException) as exc:
            if attempt < max_retries - 1:
                wait_time = backoff_base * (2 ** attempt)
                time.sleep(min(wait_time, 4.0))
                continue
            return None, exc
        except Exception as exc:
            return None, exc

    return None, httpx.NetworkError("Max retries exceeded")


async def _call_ai_chat_completion(messages: list[dict[str, str]], config: Any) -> str:
    if not config.openai_api_key_primary:
        logger.warning("openai_primary_key_not_configured")
        return ASSIST_AI_FAILURE_REPLY

    base_url = (config.assistant_ai_base_url or "https://api.openai.com/v1").rstrip("/")
    timeout = max(float(config.assistant_ai_timeout_seconds), 2.0)
    model = config.openai_model

    response, error = await _call_ai_chat_completion_with_key(
        messages, config.openai_api_key_primary, base_url, model, timeout
    )

    if response:
        logger.info("openai_primary_request_succeeded")
        return response

    if not error:
        logger.warning("openai_primary_request_failed", extra={"error_type": "unknown"})
        return ASSIST_AI_FAILURE_REPLY

    if not _is_eligible_for_fallback(error):
        logger.warning(
            "openai_primary_request_failed_not_eligible_for_fallback",
            extra={"error_type": type(error).__name__}
        )
        return ASSIST_AI_FAILURE_REPLY

    if not config.openai_api_key_fallback:
        logger.warning("openai_primary_failed_no_fallback_configured", extra={"error_type": type(error).__name__})
        return ASSIST_AI_FAILURE_REPLY

    logger.info("openai_primary_failed_attempting_fallback", extra={"error_type": type(error).__name__})

    response, fallback_error = await _call_ai_chat_completion_with_key(
        messages, config.openai_api_key_fallback, base_url, model, timeout
    )

    if response:
        logger.info("openai_fallback_request_succeeded")
        return response

    logger.warning(
        "both_openai_providers_failed",
        extra={
            "primary_error_type": type(error).__name__,
            "fallback_error_type": type(fallback_error).__name__ if fallback_error else "none"
        }
    )
    return ASSIST_AI_FAILURE_REPLY


def _format_web_context(results: list[WebSearchResult]) -> str:
    lines = ["Live web context:"]
    for item in results:
        lines.append(
            f"- title: {item.title}; source: {item.source}; url: {item.url}; date: {item.publication_date}; details: {item.snippet}"
        )
    return "\n".join(lines)


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


def call_image_generation_service(_: str) -> str:
    raise RuntimeError("Image generation is disabled for assistant mode")


async def generate_assistant_reply(
    config: Any,
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

    search_results: list[WebSearchResult] = []
    search_failure_note = ""
    if should_use_web_search(user_message):
        try:
            search_results = await search_web(user_message, config)
        except Exception as exc:
            logger.warning("assistant_web_search_failed", extra={"phone": mask_phone_number(phone_number), "error": str(exc)[:120]})
            search_failure_note = ASSIST_WEB_SEARCH_FAILURE_REPLY

    system_prompt = (
        "You are an SMS assistant. Keep replies concise but complete, use simple language, and avoid long intros. "
        "Break long answers into short readable sections. Do not use markdown tables. "
        "If user request is unclear, ask one clear follow-up question. "
        "When applicable, explicitly state the next step the user should take. "
        "When live web context is provided, prioritize it, summarize directly, mention source names, and include at most 3 useful links."
    )

    model_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    model_messages.extend(trim_history(history, config.assistant_max_history_messages))

    user_payload = user_message
    if search_results:
        user_payload = f"{user_payload}\n\n{_format_web_context(search_results)}"
    model_messages.append({"role": "user", "content": user_payload})

    reply = await _call_ai_chat_completion(model_messages, config)
    if search_failure_note:
        if search_failure_note not in reply:
            reply = f"{search_failure_note}\n\n{reply}"

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
            "used_web_search": bool(search_results),
            "search_failed": bool(search_failure_note),
        },
    )
    return sms_reply, updated_history
