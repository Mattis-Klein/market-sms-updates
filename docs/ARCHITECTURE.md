# Architecture

## Backend

Service: FastAPI
Path: backend/app/main.py

Core module: backend/market_updates

- keyword_handlers.py: inbound SMS orchestration and session state machine.
- keywords.py: command parsing and ticker catalog lookup.
- market_data.py: Yahoo chart fetch paths (intraday-first + fallback).
- allowlist.py: number normalization, allowlist state, invite lifecycle.
- notifications.py: persistence and list/flags logic.
- notification_runner.py: due evaluation and outbound SMS send.
- feedback_store.py: feedback persistence and portal forwarding.
- sms_sender.py: Twilio API send helper.
- webhook_api.py: Twilio inbound route.
- admin_api.py: protected admin API endpoints.

Storage:
- SQLite at MARKET_UPDATES_DB_PATH.

## Frontend Admin

Path: frontend/market-admin

Static admin page for:
- allowlist create/list
- pending invite review
- feedback read

Uses x-admin-token header to call backend admin routes.

## Feedback Portal

Path: feedback_service/app.py

FastAPI app with:
- /ingest endpoint
- password-protected view flow
- manual entry flow
