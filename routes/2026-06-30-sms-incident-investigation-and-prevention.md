# 2026-06-30 - SMS no-response incident investigation and prevention

## Incident Signal
- Users reported inbound SMS requests with no response.
- Live probes to public endpoints timed out during investigation window.

## Investigation Findings
- Core handler logic did not show a deterministic branch returning empty TwiML.
- Existing system had limited readiness/diagnostic signals for isolating whether failures were:
  - upstream routing/network reachability,
  - app runtime errors,
  - dependency/config readiness failures.
- Most likely failure class for the reported symptom: request not reaching app reliably and/or runtime exceptions without enough quick diagnostic context.

## Preventive Changes
- Added webhook fallback guard (previously): unexpected handler exceptions now return safe TwiML instead of silent failures.
- Added inbound telemetry logs:
  - `inbound_sms_received`
  - `inbound_sms_replied`
  - `inbound_sms_handler_failed`
  - `inbound_sms_fallback_replied`
- Added readiness endpoint `/health/ready` with dependency checks:
  - Twilio credentials configured
  - database connectivity
- Added automated tests for readiness and webhook resilience behavior.

## Files
- backend/app/main.py
- backend/market_updates/webhook_api.py
- backend/tests/test_health_readiness.py
- backend/tests/test_webhook_resilience.py
- docs/ARCHITECTURE.md
- docs/OPERATIONS_RUNBOOK.md

## Validation
- Targeted tests passed.
- Full backend suite passed: 74 passed.

## Operational Prevention Plan
- Gate production rollout on `/health/ready == 200`.
- Add alerting on:
  - sustained non-200 webhook responses,
  - repeated `inbound_sms_handler_failed` events,
  - loss of `inbound_sms_received` traffic while Twilio reports sends.
- Keep incident triage checklist in runbook and verify after each deploy.
