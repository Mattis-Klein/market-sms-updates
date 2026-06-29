# Operations Runbook

Date: 2026-06-28

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

Assistant mode:
- `OPENAI_API_KEY_PRIMARY` (required): Primary OpenAI API key
- `OPENAI_API_KEY_FALLBACK` (optional): Fallback key for redundancy
- `OPENAI_MODEL` (default: `gpt-4o-mini`): OpenAI model
- `ASSISTANT_AI_BASE_URL` (default: OpenAI endpoint)
- `ASSISTANT_AI_TIMEOUT_SECONDS` (default: `20`)
- `ASSISTANT_SEARCH_PROVIDER` (default: `tavily`)
- `ASSISTANT_SEARCH_API_KEY` (required): Search provider API key
- `ASSISTANT_SEARCH_TIMEOUT_SECONDS` (default: `8`)
- `ASSISTANT_SEARCH_MAX_RESULTS` (default: `4`)
- `ASSISTANT_SESSION_EXPIRATION_MINUTES` (default: `45`)
- `ASSISTANT_MAX_HISTORY_MESSAGES` (default: `12`)
- `ASSISTANT_SMS_MAX_CHARS` (default: `1200`)
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
- `@assist` returns: `How can I assist you today?`
- `@assist` then `What is the weather right now?` returns assistant reply (and search failure notice if web search unavailable).
- `menu` while in assistant mode returns close message: `Assistant mode closed. Reply MENU to see available options.`

## Troubleshooting

### No SMS reply

Check in order:
1. Twilio webhook URL and HTTP status.
2. Backend process health and logs.
3. Allowlist status for sender number.
4. Whether sender is stuck in a reminder session (commands should still bypass now).
5. If issue is assistant mode only, verify AI/search API keys and timeout settings.

### BEAST failures

Expected behavior on failure:
- Friendly fallback message should return.

If not:
- Inspect upstream connectivity to livecounts endpoints.
- Verify no unhandled exceptions in logs.

### Symbol lookup misses

- Use `SYMBOL <query>` first.
- For S&P, use `SYMBOL S&P` or symbol `^GSPC`.

### Assistant mode unavailable or slow

Check:
1. `OPENAI_API_KEY_PRIMARY` is set and valid.
2. `ASSISTANT_SEARCH_API_KEY` is set (required for web search context).
3. Timeouts: `ASSISTANT_AI_TIMEOUT_SECONDS` and `ASSISTANT_SEARCH_TIMEOUT_SECONDS`.
4. Logs for: `openai_primary_request_succeeded`, `openai_primary_failed_attempting_fallback`, `both_openai_providers_failed`.

If primary key fails, system automatically retries with `OPENAI_API_KEY_FALLBACK` (if set) on eligible errors:
- Authentication failures (401): Invalid, expired, or disabled primary key.
- Rate-limit errors (429): Primary project rate limit reached.
- Temporary server errors (5xx): Transient OpenAI outage.
- Connection/timeout errors: Network issues.

Primary key failure does NOT use fallback for:
- Invalid parameters or model.
- Content policy violations.
- Malformed request data.

Failure message to user:
> The AI assistant is temporarily unavailable. Please try again shortly or reply MENU to return to the main menu.

## Database Notes

SQLite tables include:
- allowlist
- invite requests
- sessions
- notifications
- feedback
- market_assistant_sessions (per-phone AI conversation state)

Ensure write permissions on DB path.
