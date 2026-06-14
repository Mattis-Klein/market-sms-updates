# Architecture

## Backend

Service: FastAPI
Path: backend/app/main.py

Core module: backend/market_updates

- keyword_handlers.py: inbound SMS orchestration and session state machine.
- keyword_handlers.py: includes direct ticker shortcut path for single-symbol messages.
- keywords.py: command parsing and ticker catalog lookup.
- market_data.py: Yahoo chart fetch paths (intraday-first + fallback).
- youtube_service.py: livecounts.io stats API (exact followerCount) with HTML fallback for BEAST command.
- allowlist.py: number normalization, allowlist state, invite lifecycle, permanent env allowlist parsing.
- notifications.py: persistence and list/flags logic.
- notification_runner.py: due evaluation and outbound SMS send.
- feedback_store.py: feedback persistence and portal forwarding.
- sms_sender.py: Twilio API send helper.
- webhook_api.py: Twilio inbound route.
- admin_api.py: protected admin API endpoints.

Storage:
- SQLite at MARKET_UPDATES_DB_PATH.

Permanent env allowlist:
- MARKET_UPDATES_ALLOWED_NUMBERS is parsed as a comma-separated number list.
- Values are normalized to E.164 format.
- Numbers are auto-synced into market_sms_allowlist on startup.
- Inbound access checks always allow numbers from this env list even if the DB is empty.

## Frontend Admin

Path: frontend/market-admin

Static admin page for:
- allowlist create/list
- pending invite review
- feedback read
- BEAST debug API call returning current parsed subscriber count
- MrBeast Livecounts embed for the BEAST keyword source

Uses x-admin-token header to call backend admin routes.

## Feedback Portal

Path: feedback_service/app.py

FastAPI app with:
- /ingest endpoint
- password-protected view flow
- manual entry flow
