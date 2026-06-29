# 2026-06-29 - @assist reminders production deployment hardening

## Summary
- Implemented true dual-database backend support (SQLite fallback + PostgreSQL production path).
- Wired both webhook web process and reminder worker to shared `DATABASE_URL` configuration.
- Added Render Blueprint topology for separate web and worker services sharing one PostgreSQL resource.
- Added one-time SQLite to PostgreSQL migration script with backup-first and destination safety checks.
- Fixed reminder-vs-current-info intent routing conflicts in assistant mode.
- Expanded tests to cover deployment/backend selection, migration guardrails, and reminder routing safety.

## Files
- backend/market_updates/db.py
- backend/market_updates/assistant_mode.py
- backend/market_updates/webhook_api.py
- backend/market_updates/reminder_worker.py
- backend/market_updates/notification_runner.py
- backend/scripts/migrate_sqlite_to_postgres.py
- backend/tests/test_assistant_mode.py
- backend/tests/test_postgres_deployment.py
- backend/requirements.txt
- render.yaml
- docs/ARCHITECTURE.md
- docs/FEATURE_STATUS.md
- docs/OPERATIONS_RUNBOOK.md
- docs/PROJECT_OVERVIEW.md
- docs/TESTING_AND_QUALITY.md

## Behavior Added
- Database backend selection now uses `DATABASE_URL` for PostgreSQL and falls back to SQLite when absent.
- Reminder claim/send path now supports shared multi-process safety required by web+worker deployments.
- Assistant intent classification prioritizes reminder intent over current-info forcing logic.
- Migration script now:
  - creates a SQLite backup before any copy,
  - initializes destination schema,
  - refuses migration when destination is non-empty unless force flag is provided,
  - preserves rollback path through SQLite backup retention.

## Deployment Topology
- `render.yaml` now defines:
  - web service: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - worker service: `python -m market_updates.reminder_worker`
  - shared managed PostgreSQL database bound to `DATABASE_URL` in both services.

## Validation
- Targeted tests:
  - `pytest tests/test_assistant_mode.py tests/test_postgres_deployment.py -v`
- Full backend suite:
  - `pytest tests -v --tb=short`
- Result at implementation time: all tests passed.

## Production Readiness Gate
- This change set enables production architecture and migration safety.
- Final production-ready declaration remains gated on live deployed proof that:
  - the web service stores a reminder,
  - the separate worker service delivers it,
  - both use the same persistent PostgreSQL database.
