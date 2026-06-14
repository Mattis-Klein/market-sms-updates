# 2026-06-14 GSPC No-Response Fix

Issue:
- Sending `gspc` could result in no SMS reply when direct quote fetch raised an exception before TwiML response creation.

Fixes:
- Added direct symbol aliases in `backend/market_updates/keywords.py`:
  - `GSPC` -> `^GSPC`
  - `SPX` -> `^GSPC`
  - `S&P` -> `^GSPC`
  - `SP500` -> `^GSPC`
- Hardened direct ticker branch in `backend/market_updates/keyword_handlers.py` with exception fallback:
  - `I couldn't check that ticker right now. Try again soon.`

Tests:
- Added regression tests in `backend/tests/test_direct_ticker_keyword.py` for:
  - alias mapping (`gspc` -> `^GSPC`)
  - runtime exception fallback response
