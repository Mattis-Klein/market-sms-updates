# 2026-06-15 regularMarketPrice Clean Output

Adjusted quote response formatting:

- Keep fetching and using `regularMarketPrice` from Yahoo quote metadata.
- Remove explicit field label text from SMS output.

Before:
- `... | "regularMarketPrice": 214.32`

After:
- clean quote line, using regularMarketPrice as displayed price value.

Files:
- `backend/market_updates/keyword_handlers.py`
- `backend/tests/test_direct_ticker_keyword.py`
