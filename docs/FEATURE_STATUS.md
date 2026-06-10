# Feature Status

Date: 2026-06-09

Implemented in this rebuild:
- Twilio webhook endpoint at /api/market-updates/sms.
- Commands: HELP/MENU, CHECK, DATECHECK, TICKER/LOOKUP/FIND, FEEDBACK, REMIND, LIST, STOP/CANCEL.
- Invite request flow for non-allowlisted users.
- Approver commands: PENDING, YES <id>, NO <id>.
- Notification creation flow for PRICE/ONCE/DAILY/INTERVAL reminder types.
- Notification runner batch execution script.
- Admin API endpoints for allowlist/invite/feedback operations.
- Feedback portal ingest and dashboard.

Known gaps and recommended next hardening:
- Add exchange-licensed market feed if strict real-time guarantees are required.
- Add stronger auth (SSO/JWT) for admin and feedback portal.
- Add retry/queueing for outbound and forwarding failures.
- Add full test suite and CI workflow.
