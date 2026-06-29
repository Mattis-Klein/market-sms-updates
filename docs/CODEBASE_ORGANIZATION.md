# Codebase Organization

Date: 2026-06-28

## Guiding Principles

- Keep SMS routing logic centralized in one orchestrator (`keyword_handlers.py`).
- Keep parsing/normalization logic in `keywords.py`.
- Keep external API adapters isolated (`market_data.py`, `youtube_service.py`, `sms_sender.py`, `assistant_mode.py`).
- Keep docs authoritative in `docs/` and change logs in `routes/`.

## Directory Roles

### backend/

- `app/main.py`: FastAPI app composition and router registration.
- `market_updates/`: domain modules.
- `tests/`: behavior-first unit tests by feature slices.

### frontend/market-admin/

- Static admin control panel.
- Intended for low-complexity operational tools.

### feedback_service/

- Optional independently runnable feedback UI/API service.

### docs/

- Source-of-truth documentation for operators and developers.

### routes/

- Dated change history. Append-only practice.

## Module Ownership Map

- Inbound routing/state: `keyword_handlers.py`
- AI assistant mode orchestration/safety/search: `assistant_mode.py`
- Parsing/lookup catalog: `keywords.py`
- Market data retrieval: `market_data.py`
- Subscriber utility (BEAST): `youtube_service.py`
- Access and invite controls: `allowlist.py`
- Reminder persistence and state: `notifications.py`
- Reminder execution job: `notification_runner.py`
- Feedback pipeline: `feedback_store.py`
- Admin routes: `admin_api.py`
- Webhook route: `webhook_api.py`

## Testing Organization

Current test slices:
- `test_assistant_mode.py`
- `test_beast_keyword.py`
- `test_direct_ticker_keyword.py`
- `test_ticker_keywords.py`
- `test_menu_number_guidance.py`
- `test_permanent_allowlist.py`
- `test_webhook_seed_allowlist.py`
- `test_youtube_service.py`

Recommendation:
- Keep tests grouped by behavior area.
- Prefer integration-like handler tests for SMS flows.
- Keep network dependencies mocked in unit tests.
