from __future__ import annotations

from datetime import datetime

TICKER_CATALOG = [
    {"symbol": "AAPL", "name": "Apple Inc", "keywords": ["apple", "iphone", "ios"]},
    {"symbol": "TSLA", "name": "Tesla Inc", "keywords": ["tesla", "ev", "elon"]},
    {"symbol": "MSFT", "name": "Microsoft Corp", "keywords": ["microsoft", "azure", "office"]},
    {"symbol": "NVDA", "name": "NVIDIA Corp", "keywords": ["nvidia", "gpu", "ai"]},
    {"symbol": "BTC-USD", "name": "Bitcoin USD", "keywords": ["bitcoin", "btc", "crypto"]},
]


def normalize_text(message: str) -> str:
    return " ".join(message.strip().upper().split())


def _is_valid_symbol_token(token: str) -> bool:
    # Yahoo-style symbols commonly include characters like ., -, ^, and =.
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-^=")
    return bool(token) and all(ch in allowed for ch in token)


def parse_direct_symbol(message: str) -> str | None:
    parts = normalize_text(message).split()
    if len(parts) != 1:
        return None

    token = parts[0]
    reserved = {
        "MENU",
        "STOP",
        "CHECK",
        "DATECHECK",
        "TICKER",
        "LOOKUP",
        "FIND",
        "BEAST",
        "REMIND",
        "LIST",
        "NOTIFICATIONS",
        "ALERTS",
        "CANCELREMINDER",
        "FEEDBACK",
        "REQUEST",
        "INVITE",
        "ACCESS",
        "PENDING",
        "YES",
        "NO",
        "DELETE",
        "PAUSE",
        "RESUME",
        "PRICE",
        "ONCE",
        "DAILY",
        "INTERVAL",
    }
    if token in reserved:
        return None
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
    query_tokens = [t.lower() for t in query.strip().split() if t.strip()]
    if not query_tokens:
        return []
    results = []
    for ticker in TICKER_CATALOG:
        haystack = " ".join([ticker["symbol"], ticker["name"], *ticker["keywords"]]).lower()
        if all(token in haystack for token in query_tokens):
            results.append(ticker)
    return results
