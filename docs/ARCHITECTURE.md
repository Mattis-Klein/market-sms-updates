# Architecture

## Backend

Service: FastAPI
Path: backend/app/main.py

Core module: backend/market_updates

- keyword_handlers.py: primary SMS routing, session transitions, and command orchestration.
- keywords.py: text normalization, direct-symbol parsing, symbol lookup catalog.
- profiles.py: user-profile assignment and per-profile keyword policy.
- lottery.py: Powerball data fetch, normalization, and in-memory TTL caching.
- market_data.py: Yahoo chart integration for live and historical price data.
- youtube_service.py: livecounts stats API + fallback parsing for BEAST subscriber checks.
- allowlist.py: allowlist matching, invite request lifecycle, permanent env allowlist parsing.
- notifications.py: reminder CRUD, state updates, and list summaries.
- notification_runner.py: due notification evaluation and outbound send execution.
- feedback_store.py: feedback storage and portal-forward behavior.
- sms_sender.py: Twilio outbound helper.
- webhook_api.py: Twilio webhook entry route.
- admin_api.py: authenticated admin API surface.

Storage:
- SQLite at MARKET_UPDATES_DB_PATH.

Permanent env allowlist:
- MARKET_UPDATES_ALLOWED_NUMBERS is parsed as a comma-separated number list.
- Values are normalized to E.164 format.
- Numbers are auto-synced into market_sms_allowlist on startup.
- Inbound access checks always allow numbers from this env list even if the DB is empty.

Profile routing:
- Special profile `powerball_only` is assigned by normalized phone number.
- Profile sender `+17184733934` is routed through Powerball-only logic.
- Both `+17184733934` and `7184733934` normalize to the same profile sender.
- Profile replies are constrained to Powerball menu/update keywords and always include a `Next:` line.

Powerball cache:
- `POWERBALL_CACHE_TTL_SECONDS` controls in-memory cache TTL for Powerball responses.
- Default cache TTL is 900 seconds.

## Request Flow (Inbound SMS)

1. Twilio POSTs to `/api/market-updates/sms`.
2. Webhook layer normalizes inputs and calls keyword handler.
3. Handler applies allowlist checks and approver routing.
4. Handler resolves user profile.
5. Profile sender routes through profile-restricted command handling.
6. Non-profile sender uses normal command, session, or direct-ticker path.
7. TwiML response is returned synchronously.

## Command Routing Notes

- Top-level numeric replies map to guidance prompts after MENU.
- Reminder sessions support numeric choices scoped to reminder setup.
- Direct ticker path handles formatted single-symbol messages.
- Explicit commands always take precedence over direct symbol parsing.

## Frontend Admin

Path: frontend/market-admin

Static admin page for:
- allowlist create/list
- pending invite review
- feedback read
- BEAST debug API call returning current parsed subscriber count
- MrBeast Livecounts embed for the BEAST keyword source

API usage model:
- static frontend calls backend admin endpoints with `x-admin-token`.

Uses x-admin-token header to call backend admin routes.

## Feedback Portal

Path: feedback_service/app.py

FastAPI app with:
- /ingest endpoint
- password-protected view flow
- manual entry flow

## Test Topology

Location: `backend/tests`

Coverage areas:
- BEAST and alias behavior.
- direct ticker parsing and session bypass.
- menu number guidance behavior.
- ticker discovery keywords.
- permanent/env allowlist behavior.
