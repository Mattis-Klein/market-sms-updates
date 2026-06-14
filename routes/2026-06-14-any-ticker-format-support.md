# 2026-06-14 Any Ticker Format Support

Improved direct ticker handling so users can text ticker symbols in common SMS formats and still get a quote.

Supported examples:
- `AAPL`
- `$AAPL`
- `AAPL?`
- `(TSLA)`
- `BTC-USD`

Implementation:
- Updated `parse_direct_symbol` in `backend/market_updates/keywords.py` to normalize leading `$` and trailing punctuation wrappers.
- Preserved command priority in `backend/market_updates/keyword_handlers.py` so commands like `REMIND`, `BEAST`, and `MENU` are never treated as symbols.
- Added regression coverage in `backend/tests/test_direct_ticker_keyword.py`.

Result:
- "Any ticker" now works with natural texting punctuation and casing.