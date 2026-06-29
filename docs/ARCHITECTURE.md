# Architecture

## Backend

Service: FastAPI
Path: backend/app/main.py

Core module: backend/market_updates

- keyword_handlers.py: primary SMS routing, session transitions, command orchestration, and assistant-mode priority handling.
- assistant_mode.py: AI assistant policy, OpenAI Responses API integration, forced `web_search` for current-information queries, strict reminder tools, SMS response shaping, and dual OpenAI provider fallback handling.
- keywords.py: text normalization, direct-symbol parsing, symbol lookup catalog.
- profiles.py: user-profile assignment and per-profile keyword policy.
- lottery.py: Powerball data fetch, normalization, and in-memory TTL caching.
- market_data.py: Yahoo chart integration for live and historical price data.
- youtube_service.py: livecounts stats API + fallback parsing for BEAST subscriber checks.
- allowlist.py: allowlist matching, invite request lifecycle, permanent env allowlist parsing.
- notifications.py: reminder CRUD, state updates, and list summaries.
- notification_runner.py: legacy market notification batch evaluator.
- reminder_worker.py: persistent reminder delivery worker with atomic claim/send/retry lifecycle.
- reminders.py: natural language reminder time parsing and reminder scheduling helpers.
- feedback_store.py: feedback storage and portal-forward behavior.
- sms_sender.py: Twilio outbound helper.
- webhook_api.py: Twilio webhook entry route.
- admin_api.py: authenticated admin API surface.

Storage:
- SQLite at MARKET_UPDATES_DB_PATH.
- Reminder workflow sessions in `market_sms_sessions`.
- Assistant mode state and conversation history in `market_assistant_sessions` keyed by phone number.
- Persistent assistant reminders in `market_scheduled_reminders` with statuses: pending, processing, sent, failed, cancelled.

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

OpenAI API Redundancy:
- Primary key: `OPENAI_API_KEY_PRIMARY` (required).
- Fallback key: `OPENAI_API_KEY_FALLBACK` (optional, recommended for production).
- Both keys are never logged or exposed in responses.
- Primary is attempted first with exponential backoff retry (2-3 attempts max).
- Fallback is used on eligible failures: authentication (401), rate-limit (429), temporary server errors (5xx), or connection/timeout issues.
- Fallback is NOT used for non-transient errors: content policy violations, invalid parameters, unsupported models, or malformed data.
- Both providers fail: user receives safe fallback message.

## Request Flow (Inbound SMS)

1. Twilio POSTs to `/api/market-updates/sms`.
2. Webhook layer normalizes inputs and calls keyword handler.
3. Handler applies carrier compliance keyword routing (`STOP/START/HELP`) first.
4. Handler applies approver/admin routing.
5. Handler applies allowlist/profile checks.
6. Handler applies exact assistant exit commands (`@exit`, `@assist off`).
7. Handler applies active `@assist` conversation flow before app keywords/workflows.
8. Handler applies existing workflow/keyword routing when assistant mode is not active.
8. TwiML response is returned synchronously.

## Command Routing Notes

- Top-level numeric replies map to guidance prompts after MENU.
- Reminder sessions support numeric choices scoped to reminder setup.
- Direct ticker path handles formatted single-symbol messages.
- Explicit commands always take precedence over direct symbol parsing.
- `@assist` starts or restarts assistant mode for that phone number.
- Assistant mode exits on `EXIT`, `EXIT ASSIST`, `MENU`, or `MAIN MENU`.
- Assistant sessions expire after a configurable inactivity window.
- Active assistant conversation state takes precedence over normal app keywords.
- Reserved assistant exit commands are exact-only: `@exit` and `@assist off`.
- Carrier compliance commands always override assistant mode.

## Reminder Delivery

- Reminder records are persisted before confirmation is sent to the user.
- Worker loop polls due reminders from persistent storage.
- Each reminder is atomically claimed (`pending` -> `processing`) before delivery.
- Twilio success marks `sent`; temporary failures are retried; permanent failures are marked `failed`.
- Stuck `processing` reminders are recovered back to `pending` after timeout.
- Outbound reminder texts are sent directly via Twilio sender and are not routed back through inbound keyword handling.

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
