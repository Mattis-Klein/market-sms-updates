# Operations Runbook

Date: 2026-06-14

## Runtime Targets

- Backend API: FastAPI on port 8787 (typical).
- Feedback portal: FastAPI on port 8790 (optional).

## Environment Checklist

Required for SMS:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`

Routing and auth:
- `MARKET_ADMIN_TOKEN`
- `MARKET_ACCESS_APPROVER_NUMBER`
- `MARKET_UPDATES_ALLOWED_NUMBERS`

Storage:
- `MARKET_UPDATES_DB_PATH`

Optional feedback forward:
- `FEEDBACK_PORTAL_INGEST_URL`
- `FEEDBACK_PORTAL_INGEST_TOKEN`

## Startup Sequence

1. Start backend API.
2. Confirm `/health` responds with `{ "ok": true }`.
3. Verify Twilio webhook points to `/api/market-updates/sms`.
4. Send test SMS: `MENU`.

## Post-Deploy Smoke Tests

- `MENU` returns numbered guidance list.
- `3` returns symbol lookup instructions.
- `SYMBOL S&P` includes `^GSPC`.
- `TICKERS` returns supported symbols.
- Direct ticker like `$AAPL?` returns quote.
- `BEAST` and `@mrbeast` return subscriber count or fallback message.

## Troubleshooting

### No SMS reply

Check in order:
1. Twilio webhook URL and HTTP status.
2. Backend process health and logs.
3. Allowlist status for sender number.
4. Whether sender is stuck in a reminder session (commands should still bypass now).

### BEAST failures

Expected behavior on failure:
- Friendly fallback message should return.

If not:
- Inspect upstream connectivity to livecounts endpoints.
- Verify no unhandled exceptions in logs.

### Symbol lookup misses

- Use `SYMBOL <query>` first.
- For S&P, use `SYMBOL S&P` or symbol `^GSPC`.

## Database Notes

SQLite tables include:
- allowlist
- invite requests
- sessions
- notifications
- feedback

Ensure write permissions on DB path.
