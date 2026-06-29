# Primary/Fallback OpenAI API Keys - 2026-06-28

**Phase:** 2 Enhancement to @assist feature  
**Status:** Complete  
**Test Coverage:** 8 new fallback scenario tests (all passing, 59 total tests pass)

## Overview

Implemented dual OpenAI API key support with intelligent fallback logic for production redundancy. Primary key is always attempted first; fallback is used only on transient, eligible failures. Credentials are never exposed in logs or user responses.

## Key Changes

### Configuration Migration

Updated `backend/market_updates/config.py`:
- **Removed:** `assistant_ai_model`, `assistant_ai_api_key` fields
- **Added:** 
  - `openai_api_key_primary` (required): Primary OpenAI API key
  - `openai_api_key_fallback` (optional): Fallback key for redundancy
  - `openai_model` (default: `gpt-4o-mini`): OpenAI model name
- **Unchanged:** `assistant_ai_base_url`, `assistant_ai_timeout_seconds`, search/session configs
- **New:** `validate_openai_config()` function for startup validation

Environment variables now:
- `OPENAI_API_KEY_PRIMARY` (replaces `ASSISTANT_AI_API_KEY`)
- `OPENAI_API_KEY_FALLBACK` (new)
- `OPENAI_MODEL` (replaces `ASSISTANT_AI_MODEL`)

### Fallback Implementation

Added to `backend/market_updates/assistant_mode.py`:

1. **`_is_eligible_for_fallback(error)`** - Determines whether an error is eligible for fallback:
   - **Eligible:** 401 (invalid/expired key), 429 (rate-limit), 5xx (server error), timeout/connection errors
   - **Not Eligible:** 400 with content policy, invalid params, unsupported model, or other application errors

2. **`_call_ai_chat_completion_with_key()`** - Makes API request with a single key:
   - Accepts primary or fallback key
   - Implements exponential backoff retry (2-3 attempts max)
   - Returns `(response, error)` tuple
   - Handles JSON parsing, content extraction, and error wrapping

3. **Updated `_call_ai_chat_completion()`** - Main entry point:
   - Checks primary key exists; warns if fallback missing
   - Attempts primary with retries
   - On eligible failure and fallback exists: retries with fallback
   - On both fail: returns safe SMS error message
   - Logs safely: "OpenAI primary/fallback request succeeded" or "Both OpenAI providers failed"
   - **Never logs:** Either API key, Authorization headers, full request objects

### Test Coverage

Added `backend/tests/test_assistant_mode.py::OpenAIFallbackTests` (8 tests):

1. `test_primary_succeeds_fallback_not_called` - Primary success path
2. `test_primary_fails_fallback_called_on_401` - Auth failure triggers fallback
3. `test_primary_fails_fallback_called_on_429` - Rate-limit triggers fallback
4. `test_primary_fails_fallback_called_on_timeout` - Connection timeout triggers fallback
5. `test_primary_fails_fallback_not_called_on_content_policy` - Policy errors don't fallback
6. `test_primary_fails_no_fallback_configured` - Graceful fail if no fallback
7. `test_both_providers_fail` - Both fail returns safe error message
8. `test_credentials_never_in_logs` - Validates no keys in log output

All 59 tests pass (51 existing + 8 new).

### Documentation Updates

- **README.md**: Updated assistant environment variables to reflect new `OPENAI_API_KEY_PRIMARY/FALLBACK/MODEL` naming
- **OPERATIONS_RUNBOOK.md**: 
  - Updated env var list
  - Added troubleshooting section for assistant mode with fallback behavior explanation
  - Documented eligible vs non-eligible fallback scenarios
  - Added failure message text and database schema note for `market_assistant_sessions`
- **ARCHITECTURE.md**: 
  - Updated assistant_mode.py description to mention fallback handling
  - Added "OpenAI API Redundancy" section explaining primary/fallback strategy, logging safeguards, and failure modes

## Safety & Logging

**Credentials:** Both API keys are never exposed:
- Not in request/response payloads
- Not in exception messages
- Not in log output
- Only used for HTTP Authorization headers (kept out of logs)

**Logging Statements (Safe):**
- `openai_primary_request_succeeded` - Primary worked
- `openai_primary_failed_attempting_fallback` - Primary failed, trying fallback (with error type only)
- `openai_fallback_request_succeeded` - Fallback worked
- `both_openai_providers_failed` - Both failed (with error types only, no details)
- `openai_primary_key_not_configured` - Warning at startup
- `openai_primary_failed_no_fallback_configured` - Primary failed and no fallback available

**User-Facing Failure Message:**
> The AI assistant is temporarily unavailable. Please try again shortly or reply MENU to return to the main menu.

## Retry Strategy

- **Max retries:** 2 attempts per key (primary, then fallback if eligible)
- **Backoff:** Exponential (1s, 2s, 4s max per attempt)
- **Timeout:** Respects `ASSISTANT_AI_TIMEOUT_SECONDS` (default 20s)
- **Scope:** Only retry temporary/transient errors; skip on application errors

## Eligible Fallback Scenarios

From user specification:

**Use Fallback On:**
- Invalid, expired, disabled, or revoked primary key (401)
- Primary authentication failure (401)
- Primary project rate-limit failure after bounded retries (429)
- Primary project quota or billing failure (implicit 429/403)
- Temporary OpenAI server error (5xx)
- Connection failure or timeout

**Do Not Use Fallback On:**
- Invalid request parameters
- Unsupported models or tools
- Context-length errors
- Content-policy refusals
- Malformed application data
- Programming errors
- User input errors

## Backward Compatibility

- Existing `@assist` sessions continue without change
- Database schema unchanged
- Routing logic unchanged
- Only API credential handling and retry behavior differ

## Future Enhancements

- Monitor fallback usage metrics (success rate, failure types)
- Dashboard view of API key health
- Automated fallback key rotation policies
- Per-region fallback providers (multi-cloud redundancy)
