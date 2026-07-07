# 2026-07-06 - The Odds API Live Sports Support For @assist

## Summary

Added The Odds API support as a sports provider for `@assist` live/current sports requests, with strict routing, safe fallbacks, plain-SMS output, freshness labels, and expanded tests.

## Environment

Added/used:
- `SPORTS_DATA_PROVIDER=theoddsapi`
- `THE_ODDS_API_KEY`
- `SPORTS_CACHE_SECONDS`
- `SPORTS_STALE_AFTER_SECONDS`
- `SPORTS_REQUIRE_PROVIDER_TIMESTAMP`

API key handling:
- Read only from environment variable `THE_ODDS_API_KEY`.
- Never logged, printed, or returned in responses.

## Implementation Details

- Sports provider selection now supports `theoddsapi` in `live_data/sports.py`.
- Sports discovery endpoint call:
  - `GET https://api.the-odds-api.com/v4/sports`
- Scores endpoint call:
  - `GET https://api.the-odds-api.com/v4/sports/{sport_key}/scores`
- Assistant sports intent remains tool-driven and does not rely on OpenAI web search.
- Reminder intent still has higher priority than sports intent.

## User-Facing Behavior

- Live/final/upcoming game responses include:
  - `Updated: <time> ET`
  - `Source: The Odds API`
- No links in live sports output.
- No Markdown in live sports output.
- Unsupported league reply:
  - `I don't have reliable live scores for that league right now.`
- Provider/key failure reply:
  - `I couldn't get reliable live sports data right now. Please try again shortly.`

## Tests

Added/updated tests for:
- missing API key
- provider failure
- live game response
- final game response
- upcoming game response
- unsupported league response
- no links in output
- no Markdown in output
- sports routing using sports tool path (not required web search)
- sports reminder intent stays reminder-first
- API key never appears in logs or responses

Validation run:
- Targeted: `pytest tests/test_live_data_tools.py tests/test_assistant_mode.py -q` -> `65 passed`
- Full backend: `pytest tests -q` -> `113 passed`
