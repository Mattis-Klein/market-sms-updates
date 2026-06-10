def format_market_line(symbol: str, price: float, change: float, change_pct: float) -> str:
    return f"{symbol}: ${price:.2f} ({change:+.2f}, {change_pct:+.2f}%)"
