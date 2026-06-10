# Tech Restore Market Feature - Full System Report

Date: 2026-06-09
Scope: End-to-end report of the market updates feature set, architecture, workflows, data model, APIs, operations, and known constraints.

## 1) Feature Purpose

The market feature provides a dedicated SMS assistant and admin control surface for:
- Live market quote checks.
- Historical date-based quote lookups.
- Symbol/ticker discovery by company or keyword.
- User-managed alert/reminder flows.
- Number access control through allowlist and invite approval workflow.
- Feedback intake from SMS and forwarding to a dedicated feedback portal.

Primary user channel is SMS via Twilio webhook ingestion.
Primary control plane is owner/admin-protected API and UI.

## 2) High-Level Architecture

Core module location:
- backend/market_updates

Primary integration points:
- Public inbound webhook route: POST /api/market-updates/sms
- Admin API routes: /api/market-updates/admin/*
- Frontend admin page: Market Updates Admin
- Optional feedback service deployment: feedback_service

Data storage:
- Dedicated SQLite database for market feature state.
- Default path: backend/data/market_updates.sqlite
- Overridable using MARKET_UPDATES_DB_PATH

External dependencies:
- Twilio for SMS send/receive.
- Yahoo finance chart endpoints (plus yfinance fallback path) for market data.
- Optional feedback portal ingest endpoint for forwarded feedback.

## 3) Module Breakdown

### 3.1 Orchestration and State Machine

File: keyword_handlers.py
Responsibilities:
- Parses inbound SMS messages and routes by keyword or state.
- Maintains per-sender finite state machine for multi-step flows.
- Enforces allowlist gating before feature access.
- Handles approver commands for invite approvals.
- Creates and persists notifications.

Key user-visible commands:
- HELP, MENU
- CHECK
- DATECHECK
- TICKER, LOOKUP, FIND
- FEEDBACK
- REMIND
- LIST
- STOP, CANCEL

### 3.2 Keyword and Symbol Parsing

File: keywords.py
Responsibilities:
- Normalizes inbound text.
- Parses symbol aliases and direct tickers.
- Parses CHECK ticker lists.
- Parses DATECHECK requests.
- Parses LIST actions: DELETE n, PAUSE n, RESUME n.
- Provides ticker profile catalog and keyword search.

Ticker profile includes:
- Symbol
- Display name
- Description
- Search keywords/aliases

### 3.3 Market Data Provider Layer

File: market_data.py
Responsibilities:
- Fetches latest quotes and daily change data.
- Fetches historical close for target dates.
- Marks symbol result unavailable on provider errors.

Current accuracy behavior:
- Latest quote path now prefers Yahoo intraday chart data (1d range, 1m interval).
- Falls back to daily chart path when intraday data is unavailable.
- Historical date fetch uses Yahoo chart period window and closest close on or before target date.

Important note:
- This improves practical accuracy and freshness for SMS usage.
- It is not an exchange-licensed, guaranteed real-time market data feed.

### 3.4 Notification Persistence and Summaries

File: notifications.py
Responsibilities:
- Create, list, delete, pause/resume notifications.
- Duplicate guard for active equivalent notifications.
- Update trigger timestamps and completion status.
- Build concise summary labels for LIST output.

Supported notification types:
- price_alert
- one_time_reminder
- daily_reminder
- interval_reminder

### 3.5 Notification Runner

File: notification_runner.py
Responsibilities:
- Evaluates due notifications in batch.
- Sends outbound SMS for due items.
- Applies type-specific completion/last-triggered rules.

Due logic:
- price_alert: triggers on threshold cross from current quote.
- one_time_reminder: triggers when due datetime is reached.
- daily_reminder: triggers once per day after configured time.
- interval_reminder: triggers every N minutes between start and stop windows.

Interval safeguards:
- Minimum supported interval is 30 minutes.
- Stop datetime handling marks completed after window ends.

### 3.6 Allowlist and Invite Workflow

File: allowlist.py
Responsibilities:
- Normalize phone numbers.
- Evaluate number allowlist status.
- Upsert/disable allowlist entries.
- Create/list/approve/deny invite requests.
- Seed allowlist from environment.

Normalization behavior:
- Canonicalizes US 10-digit to +1XXXXXXXXXX.
- Supports legacy compatibility candidates during allowlist match.
- Prevents approved numbers from false negative checks due to old formatting.

Approval workflow support:
- Approver number from MARKET_ACCESS_APPROVER_NUMBER.
- Fallback approver: 8483291230.
- Approver commands:
  - PENDING
  - YES <id>

### 3.7 Feedback Intake and Forwarding

File: feedback_store.py
Responsibilities:
- Persist FEEDBACK entries in market DB.
- Forward feedback payload to optional portal ingest endpoint.

Forwarding env vars:
- FEEDBACK_PORTAL_INGEST_URL
- FEEDBACK_PORTAL_INGEST_TOKEN

### 3.8 Config and Sending Utilities

Files:
- config.py
- sms_sender.py
- send_market_update.py
- formatter.py

Responsibilities:
- Parse required Twilio and recipient config.
- Build and send outbound SMS payloads.
- Support CLI dry-run and send-at operation.
- Format outbound update message lines.

## 4) Inbound SMS Flow (Detailed)

### 4.1 Entry Route

Route:
- POST /api/market-updates/sms

Input fields expected from Twilio form payload:
- From
- Body
- MessageSid

Output:
- TwiML XML with single Message body response.

### 4.2 Access Gate

Before command processing:
- Sender is normalized.
- Approver path checked first.
- If sender is not allowlisted:
  - @MARKET creates/updates invite request and notifies approver.
  - REQUEST/INVITE/ACCESS messages create pending request.
  - Generic blocked fallback response returned otherwise.

### 4.3 Top-Level Allowed User Commands

HELP / MENU:
- Returns primary command menu.

CHECK:
- Single-keyword flow with menus, or direct list mode: CHECK BTC AAPL TSLA.
- Supports aliases and custom ticker symbols.

DATECHECK:
- Syntax: DATECHECK YYYY-MM-DD <ticker list>
- Returns historical close data for one or more symbols.

TICKER / LOOKUP / FIND:
- Searches ticker profile catalog by query terms.
- Returns matching symbols with descriptive labels.

FEEDBACK:
- FEEDBACK <text> persists feedback and queues portal forwarding.

REMIND:
- Opens reminder type menu and stateful setup.

LIST / NOTIFICATIONS / ALERTS:
- Shows user notifications with status and human-formatted datetime.
- Supports DELETE n, PAUSE n, RESUME n.

STOP / CANCEL:
- Cancels in-progress setup state.

## 5) Reminder Types and Setup Behavior

### 5.1 Price Alerts

Flow:
- Choose symbol.
- Choose ABOVE or BELOW.
- Enter threshold.
- Confirm SAVE/EDIT/DELETE.

Triggering:
- Compares latest quote against threshold in runner.

### 5.2 One-Time Reminder

Flow:
- Choose template/status/symbol/custom message.
- Must provide date and time (not time-only).
- Confirm SAVE/EDIT/DELETE.

### 5.3 Daily Reminder

Flow:
- Choose message type.
- Enter daily time.
- Confirm SAVE/EDIT/DELETE.

### 5.4 Interval Reminder

Flow:
- Choose message type.
- Enter interval minutes (minimum 30).
- Enter start datetime.
- Enter stop datetime.
- Confirm SAVE/EDIT/DELETE.

## 6) Data Model (Market SQLite)

Primary tables:
- market_sms_sessions
- market_notifications
- market_sms_allowlist
- market_sms_invite_requests
- market_feedback_entries

Key design details:
- Sessions keyed by phone_number to store current state and draft payload.
- Notifications include recurrence, interval_minutes, stop_time, and last_triggered_at.
- Allowlist has enabled flag and optional label.
- Invite requests support status lifecycle: pending, approved, denied.
- Feedback table stores source and timestamp.

## 7) Admin API Surface

Base prefix:
- /api/market-updates/admin

Endpoints:
- GET /allowlist
- POST /allowlist
- DELETE /allowlist/{phone_number}
- GET /invite-requests?status=
- POST /invite-requests
- POST /invite-requests/{request_id}/approve
- POST /invite-requests/{request_id}/deny
- GET /feedback?limit=

Authorization:
- Protected with require_role("admin") dependency path.

## 8) Frontend Admin Experience

UI page:
- MarketUpdatesAdminPage

Features:
- Add/disable allowlist entries.
- Filter and process invite requests.
- View feedback feed.

Host behavior:
- Market admin exposure is host-gated for market host usage pattern.
- Routing supports market host root behavior and market-specific auth messaging.

## 9) Feedback Portal Service

Location:
- feedback_service

Capabilities:
- Password-protected web dashboard.
- Session-based auth.
- Manual add entries.
- Ingest endpoint for backend forwarding.

Key env vars:
- FEEDBACK_PORTAL_PASSWORD
- FEEDBACK_PORTAL_SESSION_SECRET
- FEEDBACK_PORTAL_INGEST_TOKEN
- FEEDBACK_PORTAL_DB_PATH (optional)

## 10) Environment Variables

### 10.1 Core Twilio and Market Send
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_FROM_NUMBER or TWILIO_PHONE_NUMBER
- MARKET_UPDATE_TO_NUMBERS or MARKET_UPDATE_TO_NUMBER
- MARKET_UPDATE_SYMBOLS (optional)
- MARKET_UPDATE_PROVIDER (optional, default yfinance)

### 10.2 Access and Storage
- MARKET_ACCESS_APPROVER_NUMBER (optional)
- MARKET_UPDATES_ALLOWED_NUMBERS (optional env seed)
- MARKET_UPDATES_DB_PATH (recommended in production)

### 10.3 Feedback Integration
- FEEDBACK_PORTAL_INGEST_URL (optional)
- FEEDBACK_PORTAL_INGEST_TOKEN (optional)

## 11) Deployment and Persistence Notes

Critical operational recommendation:
- Set MARKET_UPDATES_DB_PATH to a persistent disk path in production.

Reason:
- Default SQLite path inside ephemeral container can reset between deploys.
- This impacts allowlist, invite, notification, and feedback persistence.

Recommended production pattern:
- Persistent disk mount, for example /var/data
- MARKET_UPDATES_DB_PATH=/var/data/market_updates.sqlite
- Also set MARKET_UPDATES_ALLOWED_NUMBERS as a seed safety baseline for approved numbers.

## 12) Reliability and Accuracy Notes

Market quote reliability improvements in current system:
- Intraday-first latest quote fetch strategy.
- Daily fallback strategy when intraday data not available.
- Per-symbol graceful unavailable handling instead of full-flow failure.

Accuracy boundary:
- Yahoo-based sources do not provide contractual exchange-grade guarantees.
- For strict real-time guaranteed pricing, integrate a licensed market data provider.

## 13) Security and Access Controls

Implemented controls:
- Admin API protected by role checks.
- Non-allowlisted SMS numbers blocked from feature actions.
- Invite approval requires approver-controlled action.
- Feedback portal uses password auth and optional ingest token validation.

Residual concerns:
- Shared-password portal model is practical but weaker than per-user auth.
- Consider migrating to SSO or integrated owner/admin auth for portal.

## 14) Operational Runbook (Quick)

SMS ingress sanity:
- Verify Twilio webhook URL points to /api/market-updates/sms.

Allowlist sanity:
- Verify production allowlist has enabled entries for expected numbers.
- Confirm normalization matches inbound format.

Reminder sanity:
- Run notification runner dry-run to inspect due items.

Feedback sanity:
- Submit FEEDBACK from SMS and verify both DB persistence and portal ingest.

## 15) Test Coverage Snapshot

Focused test areas currently covered in backend tests include:
- Keyword command parsing and state transitions.
- Allowlist blocking and request/approval flows.
- CHECK list and DATECHECK behavior.
- Feedback persistence path.
- Notification runner due logic and idempotent trigger handling.
- Market data partial-failure behavior.

## 16) Current System Status Summary

What the feature currently delivers:
- Full SMS assistant for market operations.
- Ticker discovery and historical date checks.
- Detailed reminder system including interval windows.
- Access governance through allowlist and invite approvals.
- Feedback capture and portal forwarding.
- Admin APIs and UI for operational control.

What remains optional future enhancement:
- Exchange-licensed real-time feed integration for strict market-data guarantees.
- Stronger portal auth model.
- Additional observability dashboards and alerting around inbound/outbound message failures.
