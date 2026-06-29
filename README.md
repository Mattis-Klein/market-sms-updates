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
- AI assistant mode: `@assist` (exit with `EXIT`, `EXIT ASSIST`, `MENU`, or `MAIN MENU`)

Profile-specific behavior:
- `powerball_only` profile exists for `+17184733934`.
- This profile is restricted to: `MENU`, `CHECK`, `LOTTO`, `GUIDE`, `POWERBALL`, `PB`, `JACKPOT`, `NUMBERS`.
- This profile receives a Powerball-only menu and does not have access to normal market/crypto/reminder keywords.

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
- `POWERBALL_CACHE_TTL_SECONDS` (default `900`)

Assistant mode environment:
- `OPENAI_API_KEY_PRIMARY` (required): Primary OpenAI API key for assistant mode
- `OPENAI_API_KEY_FALLBACK` (optional): Fallback OpenAI API key used on eligible failures
- `OPENAI_MODEL` (default: `gpt-4o-mini`): OpenAI model to use
- `ASSISTANT_AI_BASE_URL` (default: `https://api.openai.com/v1`): OpenAI API endpoint
- `ASSISTANT_AI_TIMEOUT_SECONDS` (default: `20`): Request timeout for AI API calls
- `ASSISTANT_SEARCH_PROVIDER` (default: `tavily`): Web search provider for live context
- `ASSISTANT_SEARCH_API_KEY` (required): API key for web search provider
- `ASSISTANT_SEARCH_TIMEOUT_SECONDS` (default: `8`): Request timeout for search API
- `ASSISTANT_SEARCH_MAX_RESULTS` (default: `4`): Maximum web search results to include
- `ASSISTANT_SESSION_EXPIRATION_MINUTES` (default: `45`): How long to keep assistant session active
- `ASSISTANT_MAX_HISTORY_MESSAGES` (default: `12`): Max conversation history messages to retain
- `ASSISTANT_SMS_MAX_CHARS` (default: `1200`): Max characters for SMS responses

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
