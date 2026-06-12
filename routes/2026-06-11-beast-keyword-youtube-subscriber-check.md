# Route History - BEAST Keyword YouTube Subscriber Check

Date: 2026-06-11

Summary:
- Added BEAST SMS keyword for allowlisted users.
- BEAST fetches MrBeast subscriber count from YouTube Data API.
- Added friendly fallback messages for missing YOUTUBE_API_KEY and upstream API failures.
- Updated MENU keyword list and project documentation to include BEAST.
- Added automated tests for BEAST routing, number formatting, missing key behavior, and API failure behavior.

HTTP routes:
- No route changes.
- Twilio webhook remains POST /api/market-updates/sms.
- Admin and feedback routes unchanged.
