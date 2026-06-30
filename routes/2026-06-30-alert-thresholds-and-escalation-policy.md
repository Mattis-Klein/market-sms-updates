# 2026-06-30 - alert thresholds and escalation policy

## Summary
- Added concrete production alert thresholds for Render health/readiness/latency/error rates.
- Added concrete Twilio webhook and message-failure thresholds.
- Added log-derived thresholds for inbound handler failures, fallback spikes, and reply latency degradation.
- Added immediate response policy with strict acknowledgment and escalation expectations.

## Files
- docs/OPERATIONS_RUNBOOK.md
- docs/FEATURE_STATUS.md

## New Monitoring Policy
- Critical alerts now include:
  - health endpoint downtime,
  - Twilio webhook timeout/error spikes,
  - inbound-traffic silence anomaly.
- High-severity alerts now include:
  - readiness failures,
  - message-failure spikes,
  - inbound handler exception/fallback spikes.

## Operational Impact
- Future SMS no-response incidents should be detected faster and triaged with clear priority order.
- Rollback/mitigation decision threshold is now explicit when fallback mode persists.
