import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from market_updates.allowlist import upsert_allowlist_entry
from market_updates.config import MarketConfig
from market_updates.db import Database
from market_updates.keyword_handlers import handle_inbound_sms


class PowerballProfileTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(os.path.join(self.tmp.name, "market_updates.sqlite"))
        self.normal_user = "+15550121212"
        upsert_allowlist_entry(self.db, self.normal_user, "test-user", True)
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

    async def test_menu_check_lotto_all_return_powerball_menu(self):
        for keyword in ("MENU", "CHECK", "LOTTO"):
            twiml = await handle_inbound_sms(self.db, self.config, "+17184733934", keyword)
            self.assertIn("Powerball menu:", twiml)
            self.assertIn("Next:", twiml)
            self.assertNotIn("Market SMS Assistant", twiml)

    async def test_guide_returns_simple_guide_reply(self):
        twiml = await handle_inbound_sms(self.db, self.config, "+17184733934", "GUIDE")
        self.assertIn("How to use this:", twiml)
        self.assertIn("Next:", twiml)

    async def test_powerball_and_pb_return_full_update(self):
        payload = {
            "next_jackpot": "$90M",
            "cash_option": "$42M",
            "next_draw_date": "2026-06-17",
            "latest_draw_date": "2026-06-15",
            "white_numbers": "1 2 3 4 5",
            "powerball": "9",
            "power_play": "2X",
            "source": "Official Powerball",
            "fetched_at": "2026-06-16 10:00 UTC",
        }
        with patch("market_updates.keyword_handlers.get_powerball_summary", new=AsyncMock(return_value=payload)):
            for keyword in ("POWERBALL", "PB"):
                twiml = await handle_inbound_sms(self.db, self.config, "+17184733934", keyword)
                self.assertIn("Powerball update:", twiml)
                self.assertIn("Jackpot: $90M", twiml)
                self.assertIn("Power Play: 2X", twiml)
                self.assertIn("Next:", twiml)

    async def test_jackpot_keyword_returns_jackpot_only_reply(self):
        payload = {
            "next_jackpot": "$120M",
            "cash_option": "$56M",
            "next_draw_date": "2026-06-17",
            "source": "Official Powerball",
            "fetched_at": "2026-06-16 10:00 UTC",
        }
        with patch("market_updates.keyword_handlers.get_powerball_summary", new=AsyncMock(return_value=payload)):
            twiml = await handle_inbound_sms(self.db, self.config, "+17184733934", "JACKPOT")
        self.assertIn("Powerball jackpot:", twiml)
        self.assertIn("Jackpot: $120M", twiml)
        self.assertIn("Next:", twiml)

    async def test_numbers_keyword_returns_numbers_only_reply(self):
        payload = {
            "latest_draw_date": "2026-06-15",
            "white_numbers": "7 14 21 28 35",
            "powerball": "11",
            "power_play": "3X",
            "source": "Official Powerball",
            "fetched_at": "2026-06-16 10:00 UTC",
        }
        with patch("market_updates.keyword_handlers.get_powerball_summary", new=AsyncMock(return_value=payload)):
            twiml = await handle_inbound_sms(self.db, self.config, "+17184733934", "NUMBERS")
        self.assertIn("Last Powerball numbers:", twiml)
        self.assertIn("Numbers: 7 14 21 28 35", twiml)
        self.assertIn("Next:", twiml)

    async def test_unknown_and_blocked_keywords_return_restricted_fallback(self):
        for keyword in ("BEAST", "HELLO"):
            twiml = await handle_inbound_sms(self.db, self.config, "+17184733934", keyword)
            self.assertIn("That word is not available here.", twiml)
            self.assertIn("Next:", twiml)

    async def test_fetch_failure_returns_friendly_profile_fallback(self):
        with patch(
            "market_updates.keyword_handlers.get_powerball_summary",
            new=AsyncMock(side_effect=RuntimeError("upstream down")),
        ):
            twiml = await handle_inbound_sms(self.db, self.config, "+17184733934", "POWERBALL")
        self.assertIn("I could not get the Powerball info right now.", twiml)
        self.assertIn("Next:", twiml)

    async def test_missing_cash_option_and_power_play_do_not_crash(self):
        payload = {
            "next_jackpot": "$95M",
            "next_draw_date": "2026-06-17",
            "latest_draw_date": "2026-06-15",
            "white_numbers": "1 9 16 22 30",
            "powerball": "2",
            "source": "Official Powerball",
            "fetched_at": "2026-06-16 10:00 UTC",
        }
        with patch("market_updates.keyword_handlers.get_powerball_summary", new=AsyncMock(return_value=payload)):
            twiml = await handle_inbound_sms(self.db, self.config, "+17184733934", "POWERBALL")
        self.assertIn("Cash: N/A", twiml)
        self.assertIn("Power Play: N/A", twiml)
        self.assertIn("Next:", twiml)

    async def test_phone_normalization_matches_raw_and_e164_profile_number(self):
        for sender in ("+17184733934", "7184733934"):
            twiml = await handle_inbound_sms(self.db, self.config, sender, "MENU")
            self.assertIn("Powerball menu:", twiml)
            self.assertIn("Next:", twiml)

    async def test_normal_users_keep_normal_menu_and_keywords(self):
        menu_twiml = await handle_inbound_sms(self.db, self.config, self.normal_user, "MENU")
        self.assertIn("Market SMS Assistant", menu_twiml)

        with patch(
            "market_updates.keyword_handlers.get_latest_quote",
            new=AsyncMock(
                return_value={
                    "symbol": "AAPL",
                    "regularMarketPrice": 200.0,
                    "price": 200.0,
                    "change": 1.0,
                    "change_pct": 0.5,
                    "available": True,
                }
            ),
        ):
            check_twiml = await handle_inbound_sms(self.db, self.config, self.normal_user, "CHECK AAPL")
        self.assertIn("AAPL: $200.00 (+1.00, +0.50%)", check_twiml)


if __name__ == "__main__":
    unittest.main()
