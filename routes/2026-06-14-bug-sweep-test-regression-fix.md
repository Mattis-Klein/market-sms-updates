# 2026-06-14 Bug Sweep Test Regression Fix

During a full backend bug sweep, one test failed due to outdated menu text expectations after the numbered-menu guidance update.

Fix applied:
- Updated `backend/tests/test_permanent_allowlist.py` assertion in `test_inbound_allows_env_number_without_db_row`.
- Test now validates the current menu wording:
  - `Market SMS Assistant`
  - `Reply with a number to get the next step:`

Result:
- Test suite aligns with current user-facing menu behavior.