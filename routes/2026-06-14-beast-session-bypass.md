# 2026-06-14 BEAST Session Bypass

Adjusted the SMS dispatcher so BEAST is treated as a global command even when the sender is inside an active reminder session.

What changed:
- Added a global-command path in `backend/market_updates/keyword_handlers.py`.
- BEAST now clears any active session before replying.
- Added regression coverage in `backend/tests/test_beast_keyword.py` to prove BEAST works during an active `REMIND` flow.

Result:
- Users can send `BEAST` at any time without needing to exit a previous session first.