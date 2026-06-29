# Project Overview

Date: 2026-06-29

## Product Goal

Market SMS Assistant provides fast, text-first access to market and utility workflows without requiring users to install or open a dedicated app.

## Core User Jobs

- Get live quote snapshots by symbol.
- Check historical close data by date.
- Discover symbols from natural-language queries.
- Configure and manage notification/reminder rules.
- Use `@assist` for general AI help and live web-backed answers.
- Submit product feedback from SMS.

## System Components

- SMS backend API (FastAPI + Twilio webhook handling).
- Domain services for symbols, quotes, reminders, and allowlist enforcement.
- Admin API and static admin dashboard.
- Optional feedback portal service.

## Current Interaction Model

- `MENU` is the top-level guidance entry.
- Number replies from top-level menu return command-specific next steps.
- Direct ticker input is supported for quick quote responses.
- Symbol discovery is available through `SYMBOL <query>` and `TICKERS`.
- `@assist` starts a per-phone conversational assistant mode with configurable session expiry.
- While assistant mode is active, normal app keywords are treated as assistant conversation.
- Assistant mode exits only via exact commands `@exit` or `@assist off`.
- Assistant uses Responses API web search for current/live requests and can schedule persistent reminders naturally.

## Deployment Context

- Primary host: `https://yeshivachill.com`
- Primary inbound webhook: `/api/market-updates/sms`

## Persistence

- Local/dev SQLite database controlled by `MARKET_UPDATES_DB_PATH`.
- Production shared PostgreSQL via `DATABASE_URL` for multi-process web+worker deployments.
- Persistent reminder records are stored separately from assistant conversation session state.

## Security Posture

- Admin routes protected by `x-admin-token`.
- Inbound access controlled through DB allowlist and env permanent allowlist.

## Related Docs

- `ARCHITECTURE.md` for technical module-level design.
- `FEATURE_STATUS.md` for implemented behavior and known gaps.
- `COMMAND_REFERENCE.md` for full command-level behavior.
