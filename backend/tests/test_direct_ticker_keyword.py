import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from market_updates.allowlist import upsert_allowlist_entry
from market_updates.config import MarketConfig
from market_updates.db import Database
from market_updates.keyword_handlers import handle_inbound_sms


class DirectTickerKeywordTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(os.path.join(self.tmp.name, "market_updates.sqlite"))
        self.user_phone = "+15557654321"
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

    async def test_plain_ticker_returns_quote(self):
        with patch(
            "market_updates.keyword_handlers.get_latest_quote",
            new=AsyncMock(
                return_value={
                    "symbol": "AAPL",
                    "price": 214.32,
                    "change": 1.11,
                    "change_pct": 0.52,
                    "available": True,
                }
            ),
        ) as mock_get:
            twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "AAPL")

        self.assertIn("AAPL: $214.32 (+1.11, +0.52%)", twiml)
        mock_get.assert_awaited_once_with("AAPL")

    async def test_plain_ticker_unavailable(self):
        with patch(
            "market_updates.keyword_handlers.get_latest_quote",
            new=AsyncMock(return_value={"symbol": "ABC", "available": False}),
        ):
            twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "ABC")

        self.assertIn("ABC: unavailable", twiml)

    async def test_plain_ticker_bypasses_active_session(self):
        await handle_inbound_sms(self.db, self.config, self.user_phone, "REMIND")
        self.assertIsNotNone(self.db.get_session(self.user_phone))

        with patch(
            "market_updates.keyword_handlers.get_latest_quote",
            new=AsyncMock(
                return_value={
                    "symbol": "TSLA",
                    "price": 201.5,
                    "change": -2.3,
                    "change_pct": -1.13,
                    "available": True,
                }
            ),
        ):
            twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "TSLA")

        self.assertIn("TSLA: $201.50 (-2.30, -1.13%)", twiml)
        self.assertIsNone(self.db.get_session(self.user_phone))

    async def test_ticker_with_dollar_prefix_and_punctuation(self):
        with patch(
            "market_updates.keyword_handlers.get_latest_quote",
            new=AsyncMock(
                return_value={
                    "symbol": "AAPL",
                    "price": 214.32,
                    "change": 1.11,
                    "change_pct": 0.52,
                    "available": True,
                }
            ),
        ) as mock_get:
            twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "$aapl?")

        self.assertIn("AAPL: $214.32 (+1.11, +0.52%)", twiml)
        mock_get.assert_awaited_once_with("AAPL")


if __name__ == "__main__":
    unittest.main()
