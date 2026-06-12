# Route History - Permanent Env Allowlist Sync

Date: 2026-06-11

Summary:
- Added permanent allowlist behavior for MARKET_UPDATES_ALLOWED_NUMBERS.
- Env value used: +18483291230,+18458981872,+19145870597.
- Comma-separated values are normalized to E.164 format.
- On startup, env allowlist numbers are synced into the market_sms_allowlist table.
- During inbound SMS checks, env allowlist numbers are always allowed even if DB rows are missing.
- Dynamic invite approval flow remains unchanged for other numbers.

HTTP routes:
- No route changes.
- Twilio webhook remains POST /api/market-updates/sms.
- Admin and feedback routes unchanged.
