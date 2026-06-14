# 2026-06-14 BEAST Exact Count API + Fallback

Improved BEAST subscriber retrieval to prefer a machine-readable Livecounts stats API response for exact values.

What changed:
- Updated `backend/market_updates/youtube_service.py` to call:
  - `https://api.livecounts.io/youtube-live-subscriber-counter/stats/{channel_id}`
- Added browser-style headers (`Origin`, `Referer`, `User-Agent`, `x-service`) required for successful stats API responses.
- Added parser validation for `success` and `followerCount` fields.
- Kept resilient fallback to HTML parsing from `https://livecounts.io/youtube-live-subscriber-counter/{channel_id}` when stats API fails.
- Added tests in `backend/tests/test_youtube_service.py` for parser correctness and fallback behavior.

Result:
- BEAST now returns the most accurate available subscriber value while preserving reliability.