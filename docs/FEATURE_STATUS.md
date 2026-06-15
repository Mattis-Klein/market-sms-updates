# Feature Status

Date: 2026-06-14

## Implemented

### Inbound SMS and Command System
- Twilio webhook endpoint at `/api/market-updates/sms`.
- MENU-driven command discovery with numbered next-step guidance.
- Core commands: `CHECK`, `DATECHECK`, `TICKER/LOOKUP/FIND`, `BEAST`, `FEEDBACK`, `REMIND`, `LIST`, `CANCELREMINDER`, `STOP`.
- Discovery commands: `TICKERS`, `SYMBOL <name>`.
- Direct ticker shortcut for single-symbol messages.
- Direct ticker parsing supports formatted SMS input (`$AAPL`, `AAPL?`, `(TSLA)`).
- Direct index aliases map to Yahoo symbols (for example `GSPC`/`SPX` -> `^GSPC`).
- Direct ticker branch returns a friendly fallback message on upstream/runtime failures.
- Quote responses now include explicit `"regularMarketPrice": <value>` in message text.

### BEAST Utility
- `BEAST` and `@mrbeast` alias support.
- livecounts stats API primary source with fallback parser.
- Friendly fallback response on upstream failures.
- Session bypass behavior to avoid reminder-flow interception.

### Access Control
- Permanent env allowlist via `MARKET_UPDATES_ALLOWED_NUMBERS`.
- startup sync into allowlist table.
- invite request flow for non-allowlisted senders.
- approver commands: `PENDING`, `YES <id>`, `NO <id>`.

### Notifications
- Multi-step reminder creation flow.
- Types: `PRICE`, `ONCE`, `DAILY`, `INTERVAL`.
- Runner script for due notification processing.

### Admin and Feedback
- Admin API endpoints for allowlist, invite requests, feedback.
- Admin BEAST debug endpoint: `/api/market-updates/admin/beast-count`.
- Feedback portal ingest + dashboard flow.

## Known Gaps and Hardening Backlog

- Add exchange-licensed market feed if strict real-time guarantees are required.
- Add stronger auth (SSO/JWT) for admin and feedback portal.
- Add retry/queueing for outbound and forwarding failures.
- Expand CI and quality gates beyond current focused unit coverage.
