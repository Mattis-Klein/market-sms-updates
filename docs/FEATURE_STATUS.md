# Feature Status

Date: 2026-06-16

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

### Powerball-Only Profile
- Profile `powerball_only` mapped to sender `+17184733934` (raw `7184733934` normalizes to same profile).
- Profile keyword access restricted to: `MENU`, `CHECK`, `LOTTO`, `GUIDE`, `POWERBALL`, `PB`, `JACKPOT`, `NUMBERS`.
- Profile menu keywords (`MENU`/`CHECK`/`LOTTO`) return Powerball-only menu.
- Profile fallback blocks unknown/non-profile commands with a restricted-keyword reply.
- Profile responses use short instructional text and include `Next:` guidance on every reply.
- Normal users retain existing stock, Bitcoin, S&P, reminder, and standard menu flows.

### Lottery Data Service
- New `lottery.py` service fetches Powerball data from official Powerball API endpoints.
- In-memory cache with `POWERBALL_CACHE_TTL_SECONDS` (default 900 seconds).
- Friendly fallback response returned when Powerball fetch fails.
- Partial data (missing cash option or power play) is handled gracefully.

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
