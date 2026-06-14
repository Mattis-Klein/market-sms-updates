# 2026-06-14 @mrbeast Alias

Added support for the `@mrbeast` SMS alias so it routes to the BEAST command directly.

Changes:
- Mapped `@MRBEAST` to `BEAST` in `backend/market_updates/keyword_handlers.py` before command dispatch.
- Added regression coverage in `backend/tests/test_beast_keyword.py`.

Result:
- Users can now send `@mrbeast` and receive the same live subscriber response as `BEAST`.