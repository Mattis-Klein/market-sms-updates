from __future__ import annotations

from datetime import datetime, timezone

import httpx


YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


async def _fetch_chart(symbol: str, params: dict):
    url = YAHOO_URL.format(symbol=symbol)
    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        payload = resp.json()
    chart = payload.get("chart", {})
    error = chart.get("error")
    result = (chart.get("result") or [None])[0]
    if error or not result:
        return None
    return result


async def get_latest_quote(symbol: str):
    symbol = symbol.upper()
    intraday = await _fetch_chart(symbol, {"range": "1d", "interval": "1m"})
    result = intraday
    if not result:
        result = await _fetch_chart(symbol, {"range": "5d", "interval": "1d"})
    if not result:
        return {"symbol": symbol, "available": False}

    meta = result.get("meta", {})
    close_values = (result.get("indicators", {}).get("quote", [{}])[0].get("close", []))
    valid = [v for v in close_values if v is not None]
    if not valid:
        return {"symbol": symbol, "available": False}

    latest = float(valid[-1])
    regular_market_price_raw = meta.get("regularMarketPrice")
    regular_market_price = float(regular_market_price_raw) if isinstance(regular_market_price_raw, (int, float)) else latest
    prev = float(meta.get("previousClose") or valid[0])
    change = latest - prev
    change_pct = (change / prev * 100.0) if prev else 0.0
    return {
        "symbol": symbol,
        "regularMarketPrice": regular_market_price,
        "price": latest,
        "change": change,
        "change_pct": change_pct,
        "available": True,
    }


async def get_historical_close(symbol: str, target_date: str):
    symbol = symbol.upper()
    day = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    period_end = int(day.timestamp()) + 86400
    period_start = period_end - 86400 * 10
    result = await _fetch_chart(
        symbol,
        {
            "period1": str(period_start),
            "period2": str(period_end),
            "interval": "1d",
        },
    )
    if not result:
        return {"symbol": symbol, "date": target_date, "available": False}

    timestamps = result.get("timestamp") or []
    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    best = None
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        if dt <= target_date:
            best = (dt, float(close))

    if not best:
        return {"symbol": symbol, "date": target_date, "available": False}

    return {
        "symbol": symbol,
        "requested_date": target_date,
        "actual_date": best[0],
        "close": best[1],
        "available": True,
    }
