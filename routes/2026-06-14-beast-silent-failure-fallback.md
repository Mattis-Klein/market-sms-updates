# 2026-06-14 BEAST Silent Failure Fallback

Hardened the BEAST keyword so it always returns a TwiML response, even if Livecounts raises an unexpected exception.

Changes:
- Updated `backend/market_updates/keyword_handlers.py` to catch unexpected exceptions in the BEAST branch.
- Preserved the same user-facing fallback message: `I couldn't check MrBeast subscribers right now. Try again soon.`
- Added regression coverage in `backend/tests/test_beast_keyword.py` for unexpected runtime failures.

Result:
- BEAST no longer risks a silent SMS reply failure if Livecounts or another upstream dependency misbehaves.