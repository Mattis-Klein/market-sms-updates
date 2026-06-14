# API Reference

Date: 2026-06-14

## Public API

### POST /api/market-updates/sms

Purpose:
- Twilio inbound webhook endpoint.

Expected form fields:
- `From`
- `Body`
- `MessageSid`

Response:
- TwiML XML with one SMS reply message.

## Health Endpoint

### GET /health

Response:
- `{ "ok": true }`

## Admin API

All admin endpoints require header:
- `x-admin-token: <MARKET_ADMIN_TOKEN>`

Base path:
- `/api/market-updates/admin`

### Allowlist

- `GET /allowlist`
- `POST /allowlist`
  - body: `{ "phone_number": string, "label": string, "enabled": bool }`
- `DELETE /allowlist/{phone_number}`

### Invite Requests

- `GET /invite-requests?status=pending`
- `POST /invite-requests`
  - body: `{ "phone_number": string, "request_text": string }`
- `POST /invite-requests/{request_id}/approve`
- `POST /invite-requests/{request_id}/deny`

### Feedback

- `GET /feedback?limit=100`

### BEAST Debug

- `GET /beast-count`

Response shape:
- `channel_id`
- `subscriber_count`
- `subscriber_count_formatted`

## Feedback Service API (Optional Deployment)

Service path:
- `feedback_service/app.py`

Primary endpoint:
- `POST /ingest`

Used by backend feedback-forward flow when configured.
