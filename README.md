# Market SMS Assistant

Market SMS Assistant is an SMS-first automation service for:
- live market quotes
- historical market checks
- symbol discovery
- reminder and notification workflows
- controlled access via allowlist and invite approvals
- feedback capture and forwarding

The project is built on FastAPI with Twilio inbound/outbound messaging and SQLite persistence.

## Quick Start

1. Create and activate a Python environment.
2. Install backend dependencies.
3. Set required environment variables.
4. Run the backend API.

Backend run:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8787
```

Primary webhook path:

`/api/market-updates/sms`

Production webhook example:

`https://yeshivachill.com/api/market-updates/sms`

## Core SMS Experience

Top-level entry command:
- `MENU`

Command groups:
- Market data: `CHECK`, `DATECHECK`, direct ticker message
- Symbol discovery: `SYMBOL <query>`, `TICKERS`, `TICKER/LOOKUP/FIND <query>`
- Subscriber utility: `BEAST`, `@mrbeast`
- Reminders: `REMIND`, `LIST`, `CANCELREMINDER <index>`
- Feedback: `FEEDBACK <message>`

Numbered menu behavior:
- Replying with top-level numbers after `MENU` returns next-step guidance.
- Reminder-flow numbers remain active inside reminder setup sessions.

## Repository Layout

- `backend/`: FastAPI API, domain modules, tests.
- `frontend/market-admin/`: static admin UI.
- `feedback_service/`: optional feedback portal API/UI.
- `docs/`: canonical project documentation.
- `routes/`: dated change logs and implementation notes.

## Environment

Minimum required for SMS send/receive:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`

Access and admin:
- `MARKET_UPDATES_ALLOWED_NUMBERS`
- `MARKET_ACCESS_APPROVER_NUMBER`
- `MARKET_ADMIN_TOKEN`

Optional integrations:
- `FEEDBACK_PORTAL_INGEST_URL`
- `FEEDBACK_PORTAL_INGEST_TOKEN`

## Admin API Auth

All admin routes require:

`x-admin-token: <MARKET_ADMIN_TOKEN>`

## Documentation Map

- `docs/PROJECT_OVERVIEW.md`
- `docs/ARCHITECTURE.md`
- `docs/FEATURE_STATUS.md`
- `docs/COMMAND_REFERENCE.md`
- `docs/API_REFERENCE.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/CODEBASE_ORGANIZATION.md`
- `docs/TESTING_AND_QUALITY.md`
