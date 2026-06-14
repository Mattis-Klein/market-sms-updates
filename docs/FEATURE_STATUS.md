# Feature Status

Date: 2026-06-09

Implemented in this rebuild:
- Twilio webhook endpoint at /api/market-updates/sms.
- Commands: MENU, CHECK, DATECHECK, TICKER/LOOKUP/FIND, BEAST, FEEDBACK, REMIND, LIST, CANCELREMINDER, STOP.
- New keyword: `TICKERS` returns the supported ticker list.
- New keyword: `SYMBOL <name>` maps text queries (for example `SYMBOL S&P`) to ticker symbols.
- MENU now supports top-level number replies that return next-step instructions.
- Direct ticker messages (for example `AAPL`, `TSLA`, `BTC-USD`) now return quick quotes without `CHECK`.
- Direct ticker parsing accepts common SMS formatting (for example `$AAPL`, `AAPL?`, `(TSLA)`).
- BEAST also accepts the `@mrbeast` alias.
- BEAST uses livecounts.io stats API for exact followerCount with HTML fallback.
- BEAST always returns a friendly TwiML fallback if Livecounts fails unexpectedly.
- BEAST bypasses active reminder sessions so it responds immediately as a global command.
- Permanent env allowlist support from MARKET_UPDATES_ALLOWED_NUMBERS (startup sync + runtime bypass).
- Invite request flow for non-allowlisted users.
- Approver commands: PENDING, YES <id>, NO <id>.
- Notification creation flow for PRICE/ONCE/DAILY/INTERVAL reminder types.
- Notification runner batch execution script.
- Admin API endpoints for allowlist/invite/feedback operations.
- Admin API endpoint `/api/market-updates/admin/beast-count` for live BEAST debug value.
- Feedback portal ingest and dashboard.

Known gaps and recommended next hardening:
- Add exchange-licensed market feed if strict real-time guarantees are required.
- Add stronger auth (SSO/JWT) for admin and feedback portal.
- Add retry/queueing for outbound and forwarding failures.
- Add full test suite and CI workflow.
