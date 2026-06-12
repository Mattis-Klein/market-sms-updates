# BEAST Keyword Migration: YouTube API → livecounts.io

**Date:** 2026-06-12  
**Commit:** 5501aff  
**Status:** Complete and tested

## Problem
BEAST keyword required YouTube Data API key (`YOUTUBE_API_KEY` env var) which:
- Added a deployment dependency
- Required users to set up Google Cloud credentials
- Could fail if key was misconfigured or quota exhausted

## Solution
Migrated BEAST subscriber count lookup to livecounts.io public web scraper.

### Changes Made

1. **youtube_service.py** (renamed in-place, not functionality)
   - Replaced YouTube API v3 call with HTTP GET to livecounts.io
   - Parse HTML response to extract subscriber count using regex
   - Pattern matches spaces/commas in displayed format: `4 9 9, 8 5 2, 9 0 7`
   - Remove all spaces/commas, convert to int
   - Same exception class name (`YouTubeServiceError` → `LivecountsServiceError`)

2. **keyword_handlers.py**
   - Removed `YOUTUBE_API_KEY` env check
   - Updated BEAST handler to call `get_channel_subscriber_count(MRBEAST_CHANNEL_ID)` (no api_key param)
   - Removed setup error message about missing YouTube API
   - Kept same success message: "MrBeast currently has {count} YouTube subscribers."
   - Kept same failure fallback: "I couldn't check MrBeast subscribers right now. Try again soon."
   - Removed unused `os` import

3. **test_beast_keyword.py**
   - Removed `test_missing_api_key_returns_setup_message()` test
   - Updated `test_beast_keyword_routes_and_replies_with_commas()` to mock without api_key
   - Updated `test_api_failure_returns_friendly_error()` to use `LivecountsServiceError`
   - All 3 tests passing

4. **Documentation**
   - Updated ARCHITECTURE.md to describe livecounts.io scraping
   - Updated MARKET_FEATURE_FULL_REPORT.md sections 3.3.1 and BEAST description

## Trade-offs

### Advantages
- Zero deployment dependencies
- No API keys required
- Real-time subscriber count (livecounts updates every 2 seconds)
- No quota/rate limit concerns

### Disadvantages
- Depends on livecounts.io service availability
- HTML parsing fragile if livecounts.io changes page structure
- Source data still comes from YouTube (not "exact" due to rounding for large channels)

## Data Source
Both YouTube API and livecounts.io pull from same official YouTube API v3, so subscriber counts are identical. YouTube publishes rounded figures for channels with 100M+ subscribers (e.g., MrBeast's 500M count is rounded).

## Rollback Plan
If livecounts.io becomes unreliable, reverting to YouTube API requires:
1. Create new Google Cloud project and YouTube API key
2. Revert youtube_service.py to YouTube API call pattern
3. Add api_key parameter back to BEAST handler
4. Update tests to include api_key check
5. Set YOUTUBE_API_KEY env var on deployment
