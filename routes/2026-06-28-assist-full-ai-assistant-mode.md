# 2026-06-28 - @assist full AI assistant mode

## Summary
- Added a new SMS keyword and conversation mode: `@assist`.
- Added per-phone assistant session storage with conversation history and inactivity expiration.
- Added assistant-mode safety/refusal rules for explicit sexual and dangerous requests.
- Added strict image-request handling with a fixed non-image fallback response.
- Added live web-search integration path (provider-configurable, timeout-controlled, URL safety filtered).
- Added routing-priority updates so assistant mode is isolated and non-breaking to existing keywords/workflows.
- Added comprehensive automated tests for assistant mode behavior and safety/search outcomes.

## Files
- backend/market_updates/assistant_mode.py
- backend/market_updates/config.py
- backend/market_updates/db.py
- backend/market_updates/keyword_handlers.py
- backend/tests/test_assistant_mode.py
- docs/ARCHITECTURE.md
- docs/COMMAND_REFERENCE.md
- docs/FEATURE_STATUS.md
- docs/OPERATIONS_RUNBOOK.md
- docs/PROJECT_OVERVIEW.md
- docs/TESTING_AND_QUALITY.md
- README.md

## Routing behavior
- Priority now applies in this order:
  1. carrier compliance commands
  2. administrator commands
  3. dedicated application keywords
  4. active multi-step reminder workflows
  5. active `@assist` conversation
  6. unknown keyword fallback
- `@assist` starts or restarts assistant mode unless a critical confirmation step exists.
- Assistant exit commands: `EXIT`, `EXIT ASSIST`, `MENU`, `MAIN MENU`.
- Exit reply: `Assistant mode closed. Reply MENU to see available options.`

## Assistant session model
- New table: `market_assistant_sessions`
- Stored fields:
  - `phone_number`
  - `assistant_mode_active`
  - `assistant_started_at`
  - `assistant_last_activity_at`
  - `assistant_conversation_history`
- Session expiration uses configurable inactivity window.
- Conversation history is trimmed to configurable max size.

## Safety and privacy
- Explicit sexual content requests are refused with safe redirection.
- Dangerous/criminal requests are refused with safety redirection.
- Image generate/edit requests return fixed unavailable message; no image tool call path exists.
- Assistant logging records event metadata without storing full inbound message content.

## Web search
- Search provider is configurable (current implementation: Tavily).
- Search API key is server-side only and never exposed in SMS responses.
- Result filtering enforces safe URL scheme/host handling.
- Search failures return a required fallback warning before the general answer.

## Configuration added
- `ASSISTANT_AI_MODEL`
- `ASSISTANT_AI_BASE_URL`
- `ASSISTANT_AI_API_KEY`
- `ASSISTANT_AI_TIMEOUT_SECONDS`
- `ASSISTANT_SEARCH_PROVIDER`
- `ASSISTANT_SEARCH_API_KEY`
- `ASSISTANT_SEARCH_TIMEOUT_SECONDS`
- `ASSISTANT_SEARCH_MAX_RESULTS`
- `ASSISTANT_SESSION_EXPIRATION_MINUTES`
- `ASSISTANT_MAX_HISTORY_MESSAGES`
- `ASSISTANT_SMS_MAX_CHARS`

## Tests
- Added: `backend/tests/test_assistant_mode.py`
- Coverage includes:
  - entering assistant mode
  - active assistant-mode conversation routing
  - leaving assistant mode
  - session expiration fallback
  - per-phone isolation
  - dedicated keyword precedence while assist is active
  - image-request blocking and no image tool call
  - explicit-content refusal
  - web-search success context injection
  - web-search failure fallback notice

## Verification
- Ran full backend suite:
  - `python -m unittest discover -s tests -p "test_*.py"`
  - Result: 51 tests passed
