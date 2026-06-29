# Testing and Quality

Date: 2026-06-28

## Test Runner

Backend tests use Python unittest.

Run all backend tests:

```bash
cd backend
../.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"
```

## Current Coverage Focus

- inbound SMS routing
- command/session transitions
- direct ticker parsing
- symbol discovery keywords
- BEAST source/fallback logic
- allowlist and invite behavior
- assistant mode entry, active conversation routing, and exits
- assistant session expiration and per-phone isolation
- assistant image-request blocking and explicit-content refusal
- assistant forced web-search behavior for current-information prompts
- assistant search-failure safe response behavior
- assistant-mode routing precedence over normal keyword handlers while active
- natural-language reminder scheduling persistence, worker delivery, retry, and duplicate prevention
- reminder ownership boundaries (users cannot manage reminders owned by other numbers)

## Test Philosophy

- Keep fast unit tests for parser and utility functions.
- Use handler-level tests for command behavior and TwiML outcomes.
- Mock external requests in command tests where practical.

## Quality Gates (Recommended)

Before merge:
1. Run full unittest suite.
2. Run static problems scan in workspace.
3. Confirm docs updates for user-facing behavior changes.
4. Add a dated entry in `routes/` for every functional change.

## Known Quality Gaps

- No CI pipeline committed yet.
- No load/performance test harness.
- No contract tests for Twilio payload variants.

## Next Quality Improvements

- Add GitHub Actions workflow for test execution.
- Add lint/format checks.
- Add API contract tests for admin endpoints.
- Add end-to-end smoke tests for primary SMS flows.
