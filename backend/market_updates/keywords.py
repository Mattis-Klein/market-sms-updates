from __future__ import annotations

from datetime import datetime
import re

TICKER_CATALOG = [
    {"symbol": "AAPL", "name": "Apple Inc", "keywords": ["apple", "iphone", "ios"]},
    {"symbol": "TSLA", "name": "Tesla Inc", "keywords": ["tesla", "ev", "elon"]},
    {"symbol": "MSFT", "name": "Microsoft Corp", "keywords": ["microsoft", "azure", "office"]},
    {"symbol": "NVDA", "name": "NVIDIA Corp", "keywords": ["nvidia", "gpu", "ai"]},
    {"symbol": "BTC-USD", "name": "Bitcoin USD", "keywords": ["bitcoin", "btc", "crypto"]},
    {
        "symbol": "^GSPC",
        "name": "S&P 500 Index",
        "keywords": ["s&p", "s&p 500", "spx", "sp500", "s and p", "standard and poor", "index"],
    },
]


def normalize_text(message: str) -> str:
    return " ".join(message.strip().upper().split())


def _is_valid_symbol_token(token: str) -> bool:
    # Yahoo-style symbols commonly include characters like ., -, ^, and =.
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-^=")
    return bool(token) and all(ch in allowed for ch in token)


def _normalize_direct_symbol_token(token: str) -> str:
    # Support common SMS formatting like "$AAPL" or "AAPL?"
    cleaned = token.strip().upper().strip("()[]{}\"'")
    if cleaned.startswith("$"):
        cleaned = cleaned[1:]
    cleaned = cleaned.rstrip(".,!?:;")
    return cleaned


def parse_direct_symbol(message: str) -> str | None:
    parts = normalize_text(message).split()
    if len(parts) != 1:
        return None

    token = _normalize_direct_symbol_token(parts[0])
    if not _is_valid_symbol_token(token):
        return None
    return token


def parse_check_symbols(message: str) -> list[str]:
    parts = normalize_text(message).split()
    if not parts or parts[0] != "CHECK":
        return []
    return [p for p in parts[1:] if _is_valid_symbol_token(p)]


def parse_datecheck(message: str):
    parts = normalize_text(message).split()
    if len(parts) < 3 or parts[0] != "DATECHECK":
        return None
    try:
        datetime.strptime(parts[1], "%Y-%m-%d")
    except ValueError:
        return None
    symbols = [p for p in parts[2:] if _is_valid_symbol_token(p)]
    if not symbols:
        return None
    return {"date": parts[1], "symbols": symbols}


def parse_list_action(message: str):
    parts = normalize_text(message).split()
    if len(parts) != 2:
        return None
    action = parts[0]
    if action not in {"DELETE", "PAUSE", "RESUME"}:
        return None
    if not parts[1].isdigit():
        return None
    return {"action": action, "index": int(parts[1])}


def lookup_tickers(query: str):
    normalized = query.strip().lower()
    normalized = normalized.replace("s & p", "s&p")
    normalized = normalized.replace("s and p", "s&p")
    normalized = " ".join(normalized.split())
    query_tokens = [t for t in re.split(r"\s+", normalized) if t]
    if not query_tokens:
        return []
    results = []
    for ticker in TICKER_CATALOG:
        haystack = " ".join([ticker["symbol"], ticker["name"], *ticker["keywords"]]).lower()
        if all(token in haystack for token in query_tokens):
            results.append(ticker)
    return results


def list_supported_tickers() -> list[dict]:
    return list(TICKER_CATALOG)
