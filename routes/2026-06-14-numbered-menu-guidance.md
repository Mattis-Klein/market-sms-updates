# 2026-06-14 Numbered Menu Guidance

Updated MENU navigation so users can reply with a top-level number and receive clear next-step instructions.

Examples:
- Reply `3` after MENU to get symbol lookup instructions.
- Reply `1` after MENU to get CHECK command format guidance.

Behavior notes:
- Top-level menu numbers return instructions (they do not execute the command directly).
- Reminder flow numeric choices still work inside active reminder sessions.

Implementation:
- Added `MENU_NUMBER_HELP` mapping in `backend/market_updates/keyword_handlers.py`.
- Added session-priority guard for `await_remind_type` numeric replies.
- Added tests in `backend/tests/test_menu_number_guidance.py`.