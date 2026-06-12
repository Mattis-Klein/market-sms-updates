import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from market_updates.allowlist import upsert_allowlist_entry
from market_updates.config import MarketConfig
from market_updates.db import Database
from market_updates.keyword_handlers import handle_inbound_sms
from market_updates.youtube_service import MRBEAST_CHANNEL_ID, YouTubeServiceError, format_subscriber_count


class BeastKeywordTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(os.path.join(self.tmp.name, "market_updates.sqlite"))
        self.user_phone = "+15551234567"
        upsert_allowlist_entry(self.db, self.user_phone, "test-user", True)
        self.config = MarketConfig(
            twilio_account_sid="",
            twilio_auth_token="",
            twilio_from_number="",
            market_updates_db_path=os.path.join(self.tmp.name, "market_updates.sqlite"),
            market_access_approver_number="+18483291230",
            market_updates_allowed_numbers="",
            feedback_portal_ingest_url="",
            feedback_portal_ingest_token="",
            admin_token="change-me",
            public_base_url="https://yeshivachill.com",
        )

    def tearDown(self):
        self.tmp.cleanup()

    async def test_beast_keyword_routes_and_replies_with_commas(self):
        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-key"}, clear=False):
            with patch(
                "market_updates.keyword_handlers.get_channel_subscriber_count",
                new=AsyncMock(return_value=123456789),
            ) as mock_get:
                twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "BEAST")

        self.assertIn("MrBeast currently has about 123,456,789 YouTube subscribers.", twiml)
        mock_get.assert_awaited_once_with(MRBEAST_CHANNEL_ID, "test-key")

    def test_subscriber_count_formats_with_commas(self):
        self.assertEqual(format_subscriber_count(123456789), "123,456,789")

    async def test_missing_api_key_returns_setup_message(self):
        with patch.dict(os.environ, {"YOUTUBE_API_KEY": ""}, clear=False):
            twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "BEAST")

        self.assertIn("BEAST check is not set up yet. Missing YouTube API key.", twiml)

    async def test_api_failure_returns_friendly_error(self):
        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-key"}, clear=False):
            with patch(
                "market_updates.keyword_handlers.get_channel_subscriber_count",
                new=AsyncMock(side_effect=YouTubeServiceError("boom")),
            ):
                twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "BEAST")

        self.assertIn("I couldn't check MrBeast subscribers right now. Try again soon.", twiml)


if __name__ == "__main__":
    unittest.main()
