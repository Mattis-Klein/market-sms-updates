# 2026-06-16 - Powerball-only profile

## Summary
- Added dedicated user profile `powerball_only` for sender `+17184733934`.
- Added profile-based routing layer to keep restrictions centralized.
- Added Powerball service module with official-source fetch and TTL caching.
- Added full test coverage for profile routing, fallback behavior, normalization, and normal-user regression checks.

## Files
- backend/market_updates/profiles.py
- backend/market_updates/lottery.py
- backend/market_updates/keyword_handlers.py
- backend/tests/test_powerball_profile.py
- backend/tests/test_lottery_service.py
- docs/ARCHITECTURE.md
- docs/FEATURE_STATUS.md
- docs/COMMAND_REFERENCE.md
- README.md

## Behavior added
- Profile sender can only use:
  - `MENU`, `CHECK`, `LOTTO`, `GUIDE`, `POWERBALL`, `PB`, `JACKPOT`, `NUMBERS`
- `MENU/CHECK/LOTTO` return Powerball-only menu.
- `GUIDE` returns simple instructions.
- `POWERBALL/PB` return full update.
- `JACKPOT` returns jackpot + next draw.
- `NUMBERS` returns last winning numbers.
- Any blocked/unknown keyword returns restricted fallback.
- All profile replies include a `Next:` line.

## Data source and cache
- Added `POWERBALL_CACHE_TTL_SECONDS` env support (default `900`).
- Powerball data fetch now goes through official Powerball API endpoints and is normalized into one response shape.
- Fetch failures return a friendly profile fallback message.

## Safety
- No `HELP` app keyword added.
- Feature is informational only; no predictive or advisory behavior added.

## Regression protection
- Existing normal-user market/crypto/reminder/menu behavior remains unchanged and covered by tests.
