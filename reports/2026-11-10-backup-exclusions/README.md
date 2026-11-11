# Market SMS Assistant backup and excluded-file report

Date: 2026-11-10 (America/New_York). Repository: Mattis-Klein/market-sms-updates. Branch: backup.

## What was backed up
Created backup from local HEAD 9572fbbaedab4620fd80cd1c78eb13c0d509a0b6. Live remote main was 1c2ff663f933b1ea78467b1e3b706c224fdbd3de. The local working tree was clean. The backup preserves these two previously unpushed commits:
- 072a3ae: Add reliable live-data tools for @assist with tests/docs
- 9572fbb: Add The Odds API live sports provider for @assist

The additional report commit documents the exclusions. Main is unchanged. No cleanup was performed during the original backup; subsequent authorized cleanup is recorded below. No application tests were run. Credential-pattern matches in the changed files were inspected and were configuration references or test placeholders; this is not a guarantee of a complete historical secret audit.

## Excluded files (inventory before cleanup)
3,056 ignored files totaling 45,383,754 logical bytes (43.28 MiB). Existing Git ignore rules were honored.

| Category | Files | Bytes | MiB |
|---|---:|---:|---:|
| `pytest caches` | 10 | 15285 | 0.015 |
| `.venv/` | 2976 | 44741895 | 42.669 |
| `Python caches` | 69 | 565134 | 0.539 |
| `backend/backend/data/market_updates.sqlite` | 1 | 61440 | 0.059 |

## Database retained locally
`backend/backend/data/market_updates.sqlite` is 61,440 bytes. SQLite was opened in read-only mode; quick_check returned ok. All eight tables contained zero rows at inspection: market_sms_sessions, market_notifications, sqlite_sequence, market_sms_allowlist, market_sms_invite_requests, market_feedback_entries, market_assistant_sessions, market_scheduled_reminders. No database contents were uploaded.

This empty local database is not evidence about server-side or other database copies. The database was retained during the authorized dependency/cache cleanup. If it accumulates data, preserve a consistent private backup before deleting it.

## Approved cleanup candidates (subsequently removed)
- `.venv/`: reinstallable Python dependencies (42.67 MiB). Recreate from project requirements; exact environment reproduction was not tested.
- Python bytecode and pytest caches: regenerable (about 0.55 MiB combined).
- Candidate total: 45,322,314 bytes (43.22 MiB). Stop any running project processes before removing dependencies.

## Restoration and coverage
Clone this repository and check out backup. Recreate the Python environment, install requirements, and provide runtime configuration securely. No ignored .env files were found inside this project; credentials may be supplied externally. This Git snapshot does not back up external services, environment variables, global configuration or Git-ignored contents.

[Full excluded-file inventory](excluded-files.csv) lists every enumerated ignored file and byte size. Restricted pytest cache folders were included using elevated read access. No enumeration warnings or metadata read errors occurred. The inventory is a point-in-time metadata listing, not an atomic data backup.

## Running cleanup total
Before this project cleanup, the total was 1,068,767,116 bytes from Waze Device and AI-SMS-Agent. Updated totals are recorded below. The local running ledger is C:/Users/owner/Documents/storage-cleanup-ledger.json.

## Authorized cleanup: 2026-11-10

Removed 3055 files totaling 45322314 logical bytes (43.22 MiB).

| Removed path | Files | Bytes removed | Bytes remaining |
|---|---:|---:|---:|
| .venv | 2976 | 44741895 | 0 |
| .pytest_cache | 5 | 594 | 0 |
| backend/.pytest_cache | 5 | 14691 | 0 |
| backend/app/__pycache__ | 1 | 3925 | 0 |
| backend/market_updates/__pycache__ | 31 | 256692 | 0 |
| backend/market_updates/live_data/__pycache__ | 6 | 54069 | 0 |
| backend/scripts/__pycache__ | 2 | 7825 | 0 |
| backend/tests/__pycache__ | 29 | 242623 | 0 |

Only the approved .venv, Python bytecode caches and pytest caches were removed. The 61,440-byte backend/backend/data/market_updates.sqlite database, source, requirements, documentation and Git history were retained. No matching project processes were found during the pre-cleanup check. Recreate the environment and reinstall dependencies before running the app again.

Running total across Waze Device, AI-SMS-Agent and Market SMS Assistant: 1114089430 logical bytes (1062.48 MiB). Actual disk allocation recovered may differ.

The original excluded-files.csv remains a historical pre-cleanup inventory, not a list of files still present. No database contents were uploaded. Main remains unchanged.
