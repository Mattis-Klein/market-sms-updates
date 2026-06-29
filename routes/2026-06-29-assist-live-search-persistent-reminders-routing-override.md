# 2026-06-29 - @assist Live Search, Persistent Reminders, and Routing Override

## Summary

Implemented a major `@assist` upgrade with:
- OpenAI Responses API integration using `tools: [{"type": "web_search"}]`
- Forced web search for current-information prompts
- Strict reminder function tools in assistant mode
- Persistent assistant reminder storage with worker delivery lifecycle
- Routing priority update so active assistant mode intercepts normal keywords
- New exact assistant exit commands: `@exit`, `@assist off`

## Backend Changes

### `backend/market_updates/assistant_mode.py`
- Replaced Chat Completions path with Responses API (`/responses`).
- Added forced web-search detection for current-information language.
- Added strict function tools:
  - `schedule_reminder`
  - `list_reminders`
  - `cancel_reminder`
  - `update_reminder`
- Added reminder tool execution loop using Twilio webhook-authenticated sender phone number.
- Added exact exit command handling constants.
- Preserved primary/fallback OpenAI key behavior.

### `backend/market_updates/keyword_handlers.py`
- Routing order changed so active assistant mode is checked before normal keyword handlers.
- Active assistant now intercepts words like `menu`, `check`, `powerball`, `beast`, etc.
- Exact exit commands close assistant mode and return close message.

### `backend/market_updates/db.py`
- Added persistent table `market_scheduled_reminders`.
- Added reminder lifecycle methods:
  - create/list/cancel/update
  - atomic due-claiming
  - stuck-processing recovery
  - sent/retry/failed state transitions

### `backend/market_updates/reminders.py` (new)
- Added natural-time parsing helpers for common reminder phrases.
- Added schedule helper that stores UTC/local/timezone and deduplication key.

### `backend/market_updates/reminder_worker.py` (new)
- Added continuous reminder worker with polling loop.
- Atomically claims due reminders, sends SMS, and updates statuses.
- Retries temporary failures and stops on permanent/max-attempt failures.

### `backend/market_updates/sms_sender.py`
- Added Twilio failure classification.
- Added detailed send helper for retry decisions:
  - `send_sms_with_result(...)`

### `backend/app/main.py`
- Added optional in-web worker startup toggle (`REMINDERS_RUN_IN_WEB=true`).

## Config Changes

### `backend/market_updates/config.py`
Added new environment variables:
- `ASSIST_DEFAULT_TIMEZONE`
- `ASSIST_FORCE_WEB_FOR_CURRENT_INFO`
- `REMINDERS_ENABLED`
- `REMINDER_POLL_SECONDS`
- `REMINDER_MAX_ATTEMPTS`
- `REMINDER_RETRY_DELAY_SECONDS`
- `REMINDER_PROCESSING_TIMEOUT_SECONDS`
- `DATABASE_URL`

## Tests

### `backend/tests/test_assistant_mode.py`
Replaced with expanded coverage for:
- forced live web-search behavior
- search-failure guardrail
- reminder persistence across restart
- reminder worker send/retry/fail/de-dup behavior
- reminder ownership boundaries
- assistant routing override for normal keywords
- compliance command precedence
- normal keyword behavior restoration after `@exit`

## Documentation

Updated:
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/COMMAND_REFERENCE.md`
- `docs/FEATURE_STATUS.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/TESTING_AND_QUALITY.md`

## Verification

- Assistant-focused tests: passing
- Full backend test suite: passing
