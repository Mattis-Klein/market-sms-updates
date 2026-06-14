# 2026-06-14 Direct Ticker SMS Shortcut

Added support for direct single-symbol ticker queries so users can text a ticker without `CHECK`.

Examples:
- `AAPL`
- `TSLA`
- `BTC-USD`

Implementation details:
- Added `parse_direct_symbol` in `backend/market_updates/keywords.py`.
- Updated `backend/market_updates/keyword_handlers.py` to route single-symbol messages through `get_latest_quote`.
- Direct ticker requests now bypass active reminder sessions and return immediately.
- Added regression tests in `backend/tests/test_direct_ticker_keyword.py`.

Result:
- Users can send any valid ticker token directly and get price/change output in one step.