# 2026-06-15 regularMarketPrice Output Contract

Added explicit `"regularMarketPrice": <value>` output to quote responses.

Changes:
- `backend/market_updates/market_data.py`
  - `get_latest_quote` now returns `regularMarketPrice` (from Yahoo meta when present, fallback to computed latest close).
- `backend/market_updates/keyword_handlers.py`
  - `CHECK` and direct ticker responses now append:
    - `"regularMarketPrice": <value>`
- `backend/tests/test_direct_ticker_keyword.py`
  - Updated assertions and mocks for new output field.

Result:
- SMS output includes a predictable `regularMarketPrice` field for downstream parsing/use.
