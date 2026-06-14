# Market SMS Assistant (Rebuild)

This repository rebuilds the full market SMS assistant product with:
- SMS webhook ingestion and command handling.
- Allowlist and invite approval workflow.
- Market quote and historical lookups from Yahoo endpoints.
- Reminder and alert notifications with runner job.
- Admin API and admin web UI.
- Feedback storage and optional feedback portal forwarding.

Main SMS command:
- MENU (returns assistant description and available safe keywords).
- Includes BEAST for MrBeast subscriber count checks.

## 1) Folder Layout

- `backend/` FastAPI app and market feature modules.
- `frontend/market-admin/` static admin page.
- `feedback_service/` optional feedback portal service.
- `docs/` living architecture and status docs.
- `routes/` dated change history documents.

## 2) Webhook URL (Twilio)

Set Twilio incoming webhook to:

`https://yeshivachill.com/api/market-updates/sms`

## 3) Local Run

Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8787
```

Feedback service:

```bash
cd feedback_service
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8790
```

Notification runner:

```bash
cd backend
python -m market_updates.notification_runner
```

## 4) Required Environment

Copy `.env.example` values into your deployment environment and set real secrets.

Minimum required to send SMS:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`

Permanent env allowlist:
- `MARKET_UPDATES_ALLOWED_NUMBERS=+18483291230,+18458981872,+19145870597`
- Numbers in this env list are always allowed and auto-synced into the allowlist table on startup.

BEAST keyword:
- Uses livecounts.io stats API for exact followerCount when available.
- Falls back to livecounts.io page parsing if stats API access is blocked.
- No API key is required.

## 5) Admin API Auth

Send header:

`x-admin-token: <MARKET_ADMIN_TOKEN>`

## 6) Notes on Credentials

You shared:
- Account SID: `AC1aed9218d8351feca467989909c45414`
- Phone Number: `+18777668030`

Still needed from Twilio Console:
- Auth Token

Use the Auth Token only in environment variables. Do not commit it.
