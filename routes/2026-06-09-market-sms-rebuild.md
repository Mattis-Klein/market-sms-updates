# Route History - Market SMS Rebuild

Date: 2026-06-09

Created end-to-end rebuild with these primary HTTP routes:

Backend:
- POST /api/market-updates/sms
- GET /api/market-updates/admin/allowlist
- POST /api/market-updates/admin/allowlist
- DELETE /api/market-updates/admin/allowlist/{phone_number}
- GET /api/market-updates/admin/invite-requests
- POST /api/market-updates/admin/invite-requests
- POST /api/market-updates/admin/invite-requests/{request_id}/approve
- POST /api/market-updates/admin/invite-requests/{request_id}/deny
- GET /api/market-updates/admin/feedback

Feedback service:
- GET /
- POST /ingest
- POST /view
- POST /manual-add

Webhook deployment target:
- https://yeshivachill.com/api/market-updates/sms
