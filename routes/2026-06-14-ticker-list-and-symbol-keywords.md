# 2026-06-14 Ticker List and Symbol Keywords

Added two symbol-discovery keywords for SMS.

New keywords:
- `TICKERS`
  - Returns a formatted list of supported symbols and names.
- `SYMBOL <name or keyword>`
  - Resolves text queries to ticker symbols.
  - Example: `SYMBOL S&P` returns `^GSPC - S&P 500 Index`.

Implementation details:
- Added `^GSPC` to catalog in `backend/market_updates/keywords.py` with S&P aliases.
- Added `list_supported_tickers()` helper in `backend/market_updates/keywords.py`.
- Added keyword routes in `backend/market_updates/keyword_handlers.py`.
- Added tests in `backend/tests/test_ticker_keywords.py`.

Result:
- Users can discover symbols via keyword without guessing exact ticker strings.