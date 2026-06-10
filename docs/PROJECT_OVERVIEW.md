# Project Overview

Date: 2026-06-09

This rebuild provides a complete market SMS assistant system centered around Twilio SMS + FastAPI.

Primary capabilities:
- SMS commands for live checks, date checks, ticker lookup, reminders, and feedback.
- Allowlist enforcement and invite request lifecycle.
- Admin API for allowlist/invites/feedback.
- Notification runner for due reminders and price alerts.
- Optional feedback portal with ingest endpoint.

Target host:
- https://yeshivachill.com

Primary webhook:
- /api/market-updates/sms
