import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx

from market_updates.assistant_mode import ASSIST_LIVE_DATA_FAILURE_REPLY, generate_assistant_reply
from market_updates.config import MarketConfig
from market_updates.db import Database
from market_updates.live_data.cache import CACHE, CacheEntry
from market_updates.live_data import finance as live_finance
from market_updates.live_data import sports as live_sports


class LiveDataBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.tmp.name, "db.sqlite")
        self.db = Database(self.db_path)
        CACHE._store.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def _config(self, **updates):
        base = MarketConfig(
            twilio_account_sid="sid",
            twilio_auth_token="token",
            twilio_from_number="+15550000000",
            market_updates_db_path=self.db_path,
            market_access_approver_number="+18483291230",
            market_updates_allowed_numbers="",
            feedback_portal_ingest_url="",
            feedback_portal_ingest_token="",
            admin_token="change-me",
            public_base_url="https://yeshivachill.com",
            openai_api_key_primary="primary",
            openai_api_key_fallback="fallback",
            openai_model="gpt-4o-mini",
            finance_data_provider="finnhub",
            finnhub_api_key="fh-key",
            sports_data_provider="sportsdataio",
            sportsdataio_api_key="sd-key",
        )
        merged = {**base.__dict__, **updates}
        return MarketConfig(**merged)


class IntentRoutingTests(LiveDataBase):
    async def test_aapl_routes_to_finance_tool(self):
        config = self._config()
        captured = {}

        async def fake_execute(payload, *_):
            captured["tool_choice"] = payload["tool_choice"]
            return type("R", (), {"text": "AAPL is $200", "web_search_used": False, "web_search_failed": False, "called_functions": {"get_live_quote"}})

        with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
            await generate_assistant_reply(config, self.db, "+15550001111", "What is AAPL trading at?", [])

        self.assertEqual(captured["tool_choice"], {"type": "function", "name": "get_live_quote"})

    async def test_apple_routes_to_finance_tool(self):
        config = self._config()
        captured = {}

        async def fake_execute(payload, *_):
            captured["tool_choice"] = payload["tool_choice"]
            return type("R", (), {"text": "AAPL is $200", "web_search_used": False, "web_search_failed": False, "called_functions": {"get_live_quote"}})

        with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
            await generate_assistant_reply(config, self.db, "+15550001111", "Apple stock price now", [])

        self.assertEqual(captured["tool_choice"]["name"], "get_live_quote")

    async def test_dow_routes_to_index_tool(self):
        config = self._config()
        captured = {}

        async def fake_execute(payload, *_):
            captured["tool_choice"] = payload["tool_choice"]
            return type("R", (), {"text": "Dow is up", "web_search_used": False, "web_search_failed": False, "called_functions": {"get_market_index_quote"}})

        with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
            await generate_assistant_reply(config, self.db, "+15550001111", "What's the Dow at?", [])

        self.assertEqual(captured["tool_choice"]["name"], "get_market_index_quote")

    async def test_bitcoin_routes_to_crypto_tool(self):
        config = self._config()
        captured = {}

        async def fake_execute(payload, *_):
            captured["tool_choice"] = payload["tool_choice"]
            return type("R", (), {"text": "BTC is...", "web_search_used": False, "web_search_failed": False, "called_functions": {"get_crypto_quote"}})

        with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
            await generate_assistant_reply(config, self.db, "+15550001111", "Bitcoin price now", [])

        self.assertEqual(captured["tool_choice"]["name"], "get_crypto_quote")

    async def test_yankees_routes_to_sports_tool(self):
        config = self._config()
        captured = {}

        async def fake_execute(payload, *_):
            captured["tool_choice"] = payload["tool_choice"]
            return type("R", (), {"text": "Yankees...", "web_search_used": False, "web_search_failed": False, "called_functions": {"get_live_sports_scores"}})

        with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
            await generate_assistant_reply(config, self.db, "+15550001111", "What's the Yankees score?", [])

        self.assertEqual(captured["tool_choice"]["name"], "get_live_sports_scores")

    async def test_news_routes_to_current_news_tool(self):
        config = self._config()
        captured = {}

        async def fake_execute(payload, *_):
            captured["tool_choice"] = payload["tool_choice"]
            return type("R", (), {"text": "News summary", "web_search_used": False, "web_search_failed": False, "called_functions": {"get_current_news"}})

        with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
            await generate_assistant_reply(config, self.db, "+15550001111", "What is the latest news today?", [])

        self.assertEqual(captured["tool_choice"]["name"], "get_current_news")

    async def test_reminder_does_not_call_live_tools(self):
        config = self._config()
        captured = {}

        async def fake_execute(payload, *_):
            captured["tool_choice"] = payload["tool_choice"]
            return type("R", (), {"text": "Reminder set", "web_search_used": False, "web_search_failed": False, "called_functions": {"schedule_reminder"}})

        with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
            await generate_assistant_reply(config, self.db, "+15550001111", "Remind me in 30 minutes to check AAPL", [])

        self.assertEqual(captured["tool_choice"]["name"], "schedule_reminder")

    async def test_general_question_uses_auto(self):
        config = self._config()
        captured = {}

        async def fake_execute(payload, *_):
            captured["tool_choice"] = payload["tool_choice"]
            return type("R", (), {"text": "Shakespeare", "web_search_used": False, "web_search_failed": False, "called_functions": set()})

        with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
            await generate_assistant_reply(config, self.db, "+15550001111", "Who wrote Hamlet?", [])

        self.assertEqual(captured["tool_choice"], "auto")

    async def test_finance_intent_requires_tool_call(self):
        config = self._config()

        async def fake_execute(*_):
            return type("R", (), {"text": "Maybe around 200", "web_search_used": True, "web_search_failed": False, "called_functions": set()})

        with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
            reply, _ = await generate_assistant_reply(config, self.db, "+15550001111", "Tesla stock price now", [])

        self.assertEqual(reply, ASSIST_LIVE_DATA_FAILURE_REPLY)


class FinanceToolTests(LiveDataBase):
    async def test_quote_formats_plain_sms(self):
        config = self._config()
        payload = {"c": 212.45, "pc": 211.25, "t": int(datetime.now(timezone.utc).timestamp())}
        with patch("market_updates.live_data.finance._fetch_quote_from_provider", new=AsyncMock(return_value=payload)):
            result = await live_finance.get_live_quote(config, "AAPL")
        self.assertTrue(result.success)
        self.assertIn("AAPL is", result.human_summary)
        self.assertNotIn("https://", result.human_summary)

    async def test_delayed_quote_is_labeled(self):
        config = self._config()
        old_ts = int((datetime.now(timezone.utc) - timedelta(minutes=20)).timestamp())
        payload = {"c": 100.0, "pc": 99.0, "t": old_ts}
        with patch("market_updates.live_data.finance._fetch_quote_from_provider", new=AsyncMock(return_value=payload)):
            result = await live_finance.get_live_quote(config, "AAPL")
        self.assertTrue(result.success)
        self.assertTrue(result.is_delayed)
        self.assertIn("delayed", result.human_summary.lower())

    async def test_market_closed_is_labeled(self):
        config = self._config()
        ts = int(datetime.now(timezone.utc).timestamp())
        payload = {"c": 100.0, "pc": 100.0, "t": ts}
        with patch("market_updates.live_data.finance._fetch_quote_from_provider", new=AsyncMock(return_value=payload)):
            result = await live_finance.get_live_quote(config, "AAPL")
        self.assertTrue(result.success)
        self.assertIn("latest available quote", result.human_summary.lower())

    async def test_missing_key_returns_safe_error(self):
        config = self._config(finnhub_api_key="")
        result = await live_finance.get_live_quote(config, "AAPL")
        self.assertFalse(result.success)
        self.assertIn("reliable live data", result.human_summary)

    async def test_rate_limit_returns_safe_error(self):
        config = self._config()
        request = httpx.Request("GET", "https://finnhub.io")
        response = httpx.Response(status_code=429, request=request)
        error = httpx.HTTPStatusError("too many", request=request, response=response)
        with patch("market_updates.live_data.finance._fetch_quote_from_provider", new=AsyncMock(side_effect=error)):
            result = await live_finance.get_live_quote(config, "AAPL")
        self.assertFalse(result.success)
        self.assertEqual(result.raw_status, "rate_limited")

    async def test_ambiguous_company_asks_followup(self):
        config = self._config()
        result = await live_finance.get_live_quote(config, "ford")
        self.assertFalse(result.success)
        self.assertIn("Do you mean Ford", result.human_summary)

    async def test_rejects_symbol_url_injection(self):
        config = self._config()
        result = await live_finance.get_live_quote(config, "https://evil.example")
        self.assertFalse(result.success)
        self.assertIn("identify that symbol", result.human_summary)

    async def test_quote_cache_hit_within_window(self):
        config = self._config(finance_cache_seconds=30, finance_stale_after_seconds=30)
        payload = {"c": 210.0, "pc": 209.0, "t": int(datetime.now(timezone.utc).timestamp())}
        fetch = AsyncMock(return_value=payload)
        with patch("market_updates.live_data.finance._fetch_quote_from_provider", new=fetch):
            first = await live_finance.get_live_quote(config, "AAPL")
            second = await live_finance.get_live_quote(config, "AAPL")
        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertEqual(fetch.await_count, 1)


class SportsToolTests(LiveDataBase):
    async def test_live_scores_plain_sms(self):
        config = self._config()
        games = [{"AwayTeam": "BOS", "HomeTeam": "NYK", "AwayScore": 88, "HomeScore": 91, "Status": "InProgress", "Quarter": 4, "Clock": "4:12", "DateTimeUTC": datetime.now(timezone.utc).isoformat()}]
        with patch("market_updates.live_data.sports._fetch_games_sportsdataio", new=AsyncMock(return_value=games)):
            result = await live_sports.get_live_sports_scores(config, "NBA", "2026-07-06")
        self.assertTrue(result.success)
        self.assertIn("NBA scores", result.human_summary)
        self.assertNotIn("https://", result.human_summary)

    async def test_final_game_labeled_final(self):
        config = self._config()
        games = [{"AwayTeam": "NYY", "HomeTeam": "BOS", "AwayScore": 4, "HomeScore": 3, "Status": "Final", "DateTimeUTC": datetime.now(timezone.utc).isoformat()}]
        with patch("market_updates.live_data.sports._fetch_games_sportsdataio", new=AsyncMock(return_value=games)):
            result = await live_sports.get_live_sports_scores(config, "MLB", "2026-07-06")
        self.assertTrue(result.success)
        self.assertIn("final", result.human_summary.lower())

    async def test_no_live_game_returns_safe_message(self):
        config = self._config()
        with patch("market_updates.live_data.sports._fetch_games_sportsdataio", new=AsyncMock(return_value=[])):
            result = await live_sports.get_live_sports_scores(config, "NBA", "2026-07-06")
        self.assertFalse(result.success)
        self.assertIn("don't see a live", result.human_summary.lower())

    async def test_ambiguous_team_asks_followup(self):
        config = self._config()
        result = await live_sports.get_game_status(config, "NFL", "Giants", "", "2026-07-06")
        self.assertFalse(result.success)
        self.assertIn("Do you mean", result.human_summary)

    async def test_unsupported_league_safe_message(self):
        config = self._config()
        result = await live_sports.get_live_sports_scores(config, "EPL", "2026-07-06")
        self.assertFalse(result.success)
        self.assertIn("Unsupported league", result.human_summary)

    async def test_missing_timestamp_rejected_when_required(self):
        config = self._config(sports_require_provider_timestamp=True)
        games = [{"AwayTeam": "BOS", "HomeTeam": "NYK", "AwayScore": 88, "HomeScore": 91, "Status": "InProgress"}]
        with patch("market_updates.live_data.sports._fetch_games_sportsdataio", new=AsyncMock(return_value=games)):
            result = await live_sports.get_live_sports_scores(config, "NBA", "2026-07-06")
        self.assertFalse(result.success)
        self.assertEqual(result.raw_status, "missing_timestamp")

    async def test_sports_cache_hit_within_window(self):
        config = self._config(sports_cache_seconds=30, sports_stale_after_seconds=30)
        games = [{"AwayTeam": "BOS", "HomeTeam": "NYK", "AwayScore": 88, "HomeScore": 91, "Status": "InProgress", "DateTimeUTC": datetime.now(timezone.utc).isoformat()}]
        fetch = AsyncMock(return_value=games)
        with patch("market_updates.live_data.sports._fetch_games_sportsdataio", new=fetch):
            await live_sports.get_live_sports_scores(config, "NBA", "2026-07-06")
            await live_sports.get_live_sports_scores(config, "NBA", "2026-07-06")
        self.assertEqual(fetch.await_count, 1)


class CacheBehaviorTests(LiveDataBase):
    async def test_failed_responses_cache_short_ttl(self):
        now = datetime.now().timestamp()
        CACHE.set("k", "v", ttl_seconds=120, stale_after_seconds=120, is_error=True)
        entry = CACHE._store["k"]
        self.assertLessEqual(entry.expires_at - now, 11)

    async def test_stale_cache_forces_refetch(self):
        config = self._config(finance_cache_seconds=100, finance_stale_after_seconds=100)
        key = "finance:quote:finnhub:AAPL"
        now = datetime.now().timestamp()
        stale_result = live_finance._safe_error("finnhub", "stale", "stale")
        CACHE._store[key] = CacheEntry(value=stale_result, expires_at=now + 100, stale_after=now - 1)
        payload = {"c": 210.0, "pc": 209.0, "t": int(datetime.now(timezone.utc).timestamp())}
        fetch = AsyncMock(return_value=payload)
        with patch("market_updates.live_data.finance._fetch_quote_from_provider", new=fetch):
            await live_finance.get_live_quote(config, "AAPL")
        self.assertEqual(fetch.await_count, 1)


if __name__ == "__main__":
    unittest.main()
