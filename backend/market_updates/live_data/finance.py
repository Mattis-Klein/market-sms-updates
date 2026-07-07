from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

import httpx

from .cache import CACHE
from .models import LiveDataResult, utc_now_iso


logger = logging.getLogger(__name__)

COMMON_EQUITY_SYMBOLS = {
    "apple": "AAPL",
    "tesla": "TSLA",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "meta": "META",
    "amazon": "AMZN",
    "google": "GOOGL",
}

COMMON_INDEX_SYMBOLS = {
    "dow": "^DJI",
    "djia": "^DJI",
    "nasdaq": "^IXIC",
    "s&p": "^GSPC",
    "sp500": "^GSPC",
    "spx": "^GSPC",
}

COMMON_CRYPTO_SYMBOLS = {
    "btc": "BTC",
    "bitcoin": "BTC",
    "eth": "ETH",
    "ethereum": "ETH",
    "sol": "SOL",
}

AMBIGUOUS_COMPANY_TERMS = {
    "ford": "Do you mean Ford stock, ticker F, or another company?",
}

_VALID_SYMBOL_RE = re.compile(r"^[A-Z0-9^.-]{1,15}$")


def _safe_error(provider: str, message: str, raw_status: str = "error") -> LiveDataResult:
    return LiveDataResult(
        success=False,
        provider=provider,
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


def resolve_stock_symbol(symbol: str) -> tuple[str | None, str | None]:
    value = (symbol or "").strip()
    if not value:
        return None, "Please provide a stock symbol."

    lowered = value.lower()
    if lowered in AMBIGUOUS_COMPANY_TERMS:
        return None, AMBIGUOUS_COMPANY_TERMS[lowered]
    if lowered in COMMON_EQUITY_SYMBOLS:
        return COMMON_EQUITY_SYMBOLS[lowered], None
    upper = value.upper()
    if not _VALID_SYMBOL_RE.match(upper):
        return None, "I couldn't identify that symbol. Please try a ticker symbol."
    return upper, None


def resolve_index_symbol(symbol: str) -> tuple[str | None, str | None]:
    value = (symbol or "").strip()
    if not value:
        return None, "Please provide an index symbol."
    lowered = value.lower()
    if lowered in COMMON_INDEX_SYMBOLS:
        return COMMON_INDEX_SYMBOLS[lowered], None
    upper = value.upper()
    if not _VALID_SYMBOL_RE.match(upper):
        return None, "I couldn't identify that symbol. Please try an index symbol."
    return upper, None


def resolve_crypto_symbol(symbol: str) -> tuple[str | None, str | None]:
    value = (symbol or "").strip()
    if not value:
        return None, "Please provide a crypto symbol."
    lowered = value.lower()
    if lowered in COMMON_CRYPTO_SYMBOLS:
        return COMMON_CRYPTO_SYMBOLS[lowered], None
    upper = value.upper()
    if not _VALID_SYMBOL_RE.match(upper):
        return None, "I couldn't identify that symbol. Please try a crypto symbol."
    return upper, None


def _provider_settings(config) -> tuple[str, str, int, int, bool]:
    provider = (getattr(config, "finance_data_provider", "finnhub") or "finnhub").lower()
    cache_seconds = int(getattr(config, "finance_cache_seconds", 15) or 15)
    stale_after = int(getattr(config, "finance_stale_after_seconds", 60) or 60)
    require_timestamp = bool(getattr(config, "finance_require_provider_timestamp", True))

    if provider == "finnhub":
        key = getattr(config, "finnhub_api_key", "")
    elif provider == "twelvedata":
        key = getattr(config, "twelve_data_api_key", "")
    elif provider == "fmp":
        key = getattr(config, "fmp_api_key", "")
    else:
        key = ""
    return provider, key, cache_seconds, stale_after, require_timestamp


def _parse_source_timestamp(raw, provider: str) -> datetime | None:
    if raw is None:
        return None
    if provider == "finnhub":
        try:
            return datetime.fromtimestamp(int(raw), tz=UTC)
        except Exception:
            return None
    if provider == "twelvedata":
        try:
            # TwelveData returns YYYY-MM-DD HH:MM:SS
            return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except Exception:
            return None
    if provider == "fmp":
        try:
            return datetime.fromtimestamp(int(raw), tz=UTC)
        except Exception:
            return None
    return None


def _render_quote_summary(symbol: str, price: float, change_pct: float, source_dt: datetime | None, provider: str, market_closed: bool = False, delayed: bool = False) -> str:
    direction = "+" if change_pct >= 0 else ""
    status_prefix = "The market is closed. Latest available quote:" if market_closed else ""
    delayed_line = "This quote may be delayed about 15 minutes." if delayed else ""
    updated = source_dt.astimezone().strftime("%I:%M %p ET") if source_dt else "Unknown"
    lines = [
        f"{status_prefix} {symbol} is ${price:.2f}, {direction}{change_pct:.2f}% today.".strip(),
        f"Updated: {updated}",
        f"Source: {provider.title()}",
    ]
    if delayed_line:
        lines.append(delayed_line)
    return "\n".join(lines)


async def _fetch_quote_from_provider(provider: str, api_key: str, symbol: str) -> dict:
    if provider == "finnhub":
        url = "https://finnhub.io/api/v1/quote"
        params = {"symbol": symbol, "token": api_key}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    if provider == "twelvedata":
        url = "https://api.twelvedata.com/quote"
        params = {"symbol": symbol, "apikey": api_key}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    if provider == "fmp":
        url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}"
        params = {"apikey": api_key}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0]
            return {}

    raise ValueError("unsupported_provider")


def _normalize_quote(provider: str, symbol: str, payload: dict, require_timestamp: bool) -> LiveDataResult:
    now = datetime.now(UTC)
    if provider == "finnhub":
        price = float(payload.get("c") or 0)
        prev = float(payload.get("pc") or 0)
        source_dt = _parse_source_timestamp(payload.get("t"), provider)
        market_closed = bool(payload.get("t") and price and prev and price == prev)
    elif provider == "twelvedata":
        price = float(payload.get("close") or payload.get("price") or 0)
        prev = float(payload.get("previous_close") or 0)
        source_dt = _parse_source_timestamp(payload.get("datetime"), provider)
        market_closed = str(payload.get("is_market_open", "")).lower() == "false"
    else:
        price = float(payload.get("price") or 0)
        prev = float(payload.get("previousClose") or payload.get("price") or 0)
        source_dt = _parse_source_timestamp(payload.get("timestamp"), provider)
        market_closed = False

    if price <= 0:
        return _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "no_quote")

    if require_timestamp and source_dt is None:
        return _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "missing_timestamp")

    age_seconds = int((now - source_dt).total_seconds()) if source_dt else 0
    delayed = age_seconds > 900
    change_pct = ((price - prev) / prev * 100.0) if prev else 0.0

    summary = _render_quote_summary(symbol, price, change_pct, source_dt, provider, market_closed=market_closed, delayed=delayed)

    return LiveDataResult(
        success=True,
        provider=provider,
        retrieved_at_utc=utc_now_iso(),
        source_timestamp_utc=source_dt.isoformat() if source_dt else None,
        is_live=age_seconds <= 120 if source_dt else False,
        is_delayed=delayed,
        delay_minutes=max(1, age_seconds // 60) if delayed else None,
        confidence="high" if not delayed else "medium",
        raw_status="ok",
        human_summary=summary,
        data={"symbol": symbol, "price": price, "change_pct": round(change_pct, 2), "age_seconds": age_seconds},
    )


async def _get_quote(config, symbol: str, kind: str) -> LiveDataResult:
    provider, api_key, cache_seconds, stale_after, require_timestamp = _provider_settings(config)
    if provider not in {"finnhub", "twelvedata", "fmp"}:
        return _safe_error("finance", "I couldn't get reliable live data right now. Please try again shortly.", "unsupported_provider")
    if not api_key:
        return _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "missing_api_key")

    if kind == "quote":
        resolved, prompt = resolve_stock_symbol(symbol)
    elif kind == "index":
        resolved, prompt = resolve_index_symbol(symbol)
    else:
        resolved, prompt = resolve_crypto_symbol(symbol)

    if prompt:
        return _safe_error(provider, prompt, "ambiguous")
    if not resolved:
        return _safe_error(provider, "I couldn't identify that symbol. Please try a ticker symbol.", "missing_symbol")

    cache_key = f"finance:{kind}:{provider}:{resolved}"
    cached, stale = CACHE.get(cache_key)
    if isinstance(cached, LiveDataResult) and not stale and not cached.safe_error:
        return cached

    try:
        payload = await _fetch_quote_from_provider(provider, api_key, resolved)
        result = _normalize_quote(provider, resolved, payload, require_timestamp=require_timestamp)
        CACHE.set(cache_key, result, cache_seconds, stale_after, is_error=not result.success)
        logger.info(
            "live_data.finance quote",
            extra={
                "provider": provider,
                "symbol": resolved,
                "success": result.success,
                "age_seconds": result.data.get("age_seconds", -1),
            },
        )
        return result
    except httpx.TimeoutException:
        result = _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "timeout")
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raw_status = "rate_limited" if status == 429 else f"http_{status}"
        result = _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", raw_status)
    except Exception:
        result = _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "exception")

    CACHE.set(cache_key, result, cache_seconds, stale_after, is_error=True)
    return result


async def get_live_quote(config, symbol: str) -> LiveDataResult:
    return await _get_quote(config, symbol, kind="quote")


async def get_market_index_quote(config, symbol: str) -> LiveDataResult:
    return await _get_quote(config, symbol, kind="index")


async def get_crypto_quote(config, symbol: str, currency: str = "USD") -> LiveDataResult:
    _ = currency
    return await _get_quote(config, symbol, kind="crypto")


async def get_market_status(config) -> LiveDataResult:
    provider, api_key, _, _, _ = _provider_settings(config)
    if not api_key:
        return _safe_error(provider, "I couldn't verify whether the market is open right now.", "missing_api_key")

    # We provide a conservative local market-hours estimate if provider market status is unavailable.
    now_et = datetime.now(UTC).astimezone().astimezone()
    weekday_open = now_et.weekday() < 5
    hhmm = now_et.hour * 100 + now_et.minute
    open_now = weekday_open and 930 <= hhmm <= 1600
    status_text = "open" if open_now else "closed"

    return LiveDataResult(
        success=True,
        provider=provider,
        retrieved_at_utc=utc_now_iso(),
        source_timestamp_utc=None,
        is_live=True,
        is_delayed=False,
        delay_minutes=None,
        confidence="medium",
        raw_status=status_text,
        human_summary=f"US market status appears {status_text} right now.",
        data={"status": status_text},
    )


async def get_financial_news(config, topic: str) -> LiveDataResult:
    provider, api_key, _, _, _ = _provider_settings(config)
    if provider != "finnhub" or not api_key:
        return _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "unsupported_financial_news")

    url = "https://finnhub.io/api/v1/news"
    params = {"category": "general", "token": api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            items = resp.json() or []
    except Exception:
        return _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "financial_news_error")

    summaries = []
    lowered = (topic or "").lower()
    for item in items[:20]:
        title = str(item.get("headline") or "").strip()
        source = str(item.get("source") or "").strip()
        if not title:
            continue
        if lowered and lowered not in title.lower():
            continue
        summaries.append(f"{title} ({source})")
        if len(summaries) == 3:
            break

    if not summaries:
        return _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "no_financial_news")

    return LiveDataResult(
        success=True,
        provider=provider,
        retrieved_at_utc=utc_now_iso(),
        source_timestamp_utc=None,
        is_live=True,
        is_delayed=False,
        delay_minutes=None,
        confidence="medium",
        raw_status="ok",
        human_summary="Financial headlines:\n" + "\n".join(f"{i + 1}. {line}" for i, line in enumerate(summaries)),
    )
