# 2026-07-07 - Reliable Live Current Data Tools For @assist

## Summary

Implemented provider-backed live current-data tools for `@assist` with strict intent routing, required tool-call enforcement, freshness metadata, cache controls, and safe fallback behavior.

## Why

Prompt-only instructions are not sufficient for reliable current-data answers. We need deterministic tool usage, provider-backed retrieval, and explicit failure behavior to avoid stale or fabricated responses.

## Scope

- Added `backend/market_updates/live_data/` package:
  - `models.py` (`LiveDataResult`, `utc_now_iso`)
  - `cache.py` (`InMemoryTTLCache` with short error cache behavior)
  - `finance.py` (quote/index/crypto/status/financial-news provider adapters)
  - `sports.py` (league/team resolution, live scores/status/schedule)
  - `news.py` (OpenAI web-search-backed current-news retrieval)
- Extended assistant tool schemas and execution loop in `backend/market_updates/assistant_mode.py`.
- Added strict intent classes and tool choices for finance/sports/current-news.
- Added assistant-level required-tool-call verification and safe fallback replies.
- Extended configuration in `backend/market_updates/config.py` with live-data provider/env settings.
- Added new tests in `backend/tests/test_live_data_tools.py`.
- Updated existing assistant tests in `backend/tests/test_assistant_mode.py` for current-news tool routing behavior.

## Reliability Rules Added

- Finance/sports/current-news intents must route through live-data tools.
- If required live tool evidence is missing, assistant returns safe fallback instead of guessing.
- If required web search fails or is missing when forced, assistant returns web-search failure fallback.
- News tool verifies `web_search_call` presence before accepting output.
- All outbound assistant text is sanitized to plain SMS (no markdown/no links).

## Freshness and Caching

- Finance cache defaults: `FINANCE_CACHE_SECONDS=15`, stale-after `FINANCE_STALE_AFTER_SECONDS=60`.
- Sports cache defaults: `SPORTS_CACHE_SECONDS=10`, stale-after `SPORTS_STALE_AFTER_SECONDS=45`.
- News cache default: `NEWS_CACHE_SECONDS=120`.
- Error results are cached briefly to avoid repeated provider hammering.
- Finance responses label delayed data and include source timestamp metadata.

## Verification

Focused tests:
- `pytest tests/test_live_data_tools.py tests/test_assistant_mode.py -q`
- Result: `58 passed`

Full backend tests:
- `pytest tests -q`
- Result: `106 passed`
