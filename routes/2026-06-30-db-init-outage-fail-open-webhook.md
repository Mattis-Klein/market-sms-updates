# 2026-06-30 - DB-init outage fail-open webhook behavior

## Summary
- Hardened webhook startup behavior so DB initialization failures do not take down inbound SMS response handling.
- Added explicit DB-unavailable fallback path returning safe TwiML.
- Added regression test coverage for DB-unavailable inbound behavior.

## Files
- backend/market_updates/webhook_api.py
- backend/app/main.py
- backend/tests/test_webhook_resilience.py
- docs/FEATURE_STATUS.md

## Behavior
- If DB cannot initialize at startup or at request time:
  - webhook logs `webhook_db_init_failed` and `inbound_sms_db_unavailable`,
  - inbound route still returns HTTP 200 with fallback TwiML,
  - readiness endpoint reports database failure details.

## Validation
- Targeted tests: `pytest tests/test_webhook_resilience.py tests/test_health_readiness.py -q`
- Full tests: `pytest tests -q`
- Result: 75 passed.
