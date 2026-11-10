# Market SMS Assistant backup and excluded-file report

Date: 2026-11-10 (America/New_York). Repository: Mattis-Klein/market-sms-updates. Branch: backup.

## What was backed up
Created backup from local HEAD 9572fbbaedab4620fd80cd1c78eb13c0d509a0b6. Live remote main was 1c2ff663f933b1ea78467b1e3b706c224fdbd3de. The local working tree was clean. The backup preserves these two previously unpushed commits:
- 072a3ae: Add reliable live-data tools for @assist with tests/docs
- 9572fbb: Add The Odds API live sports provider for @assist

The additional report commit documents the exclusions. Main is unchanged. No cleanup or application tests were performed. Credential-pattern matches in the changed files were inspected and were configuration references or test placeholders; this is not a guarantee of a complete historical secret audit.

## Excluded files
3,056 ignored files totaling 45,383,754 logical bytes (43.28 MiB). Existing Git ignore rules were honored.

| Category | Files | Bytes | MiB |
|---|---:|---:|---:|
| `pytest caches` | 10 | 15285 | 0.015 |
| `.venv/` | 2976 | 44741895 | 42.669 |
| `Python caches` | 69 | 565134 | 0.539 |
| `backend/backend/data/market_updates.sqlite` | 1 | 61440 | 0.059 |

## Database retained locally
`backend/backend/data/market_updates.sqlite` is 61,440 bytes. SQLite was opened in read-only mode; quick_check returned ok. All eight tables contained zero rows at inspection: market_sms_sessions, market_notifications, sqlite_sequence, market_sms_allowlist, market_sms_invite_requests, market_feedback_entries, market_assistant_sessions, market_scheduled_reminders. No database contents were uploaded.

This empty local database is not evidence about server-side or other database copies. Retain it pending explicit cleanup approval. If it accumulates data, preserve a consistent private backup before deleting it.

## Cleanup candidates — not yet deleted
- `.venv/`: reinstallable Python dependencies (42.67 MiB). Recreate from project requirements; exact environment reproduction was not tested.
- Python bytecode and pytest caches: regenerable (about 0.55 MiB combined).
- Candidate total: 45,322,314 bytes (43.22 MiB). Stop any running project processes before removing dependencies.

## Restoration and coverage
Clone this repository and check out backup. Recreate the Python environment, install requirements, and provide runtime configuration securely. No ignored .env files were found inside this project; credentials may be supplied externally. This Git snapshot does not back up external services, environment variables, global configuration or Git-ignored contents.

[Full excluded-file inventory](excluded-files.csv) lists every enumerated ignored file and byte size. Restricted pytest cache folders were included using elevated read access. No enumeration warnings or metadata read errors occurred. The inventory is a point-in-time metadata listing, not an atomic data backup.

## Running cleanup total
No files deleted from Market SMS Assistant. Prior cleanup total: 1,068,767,116 bytes (1,019.26 MiB), from Waze Device and AI-SMS-Agent. The local running ledger is C:/Users/owner/Documents/storage-cleanup-ledger.json.
