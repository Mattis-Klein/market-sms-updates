import os
import tempfile
import unittest

from market_updates.allowlist import upsert_allowlist_entry
from market_updates.config import MarketConfig
from market_updates.db import Database
from market_updates.keyword_handlers import handle_inbound_sms


class MenuNumberGuidanceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(os.path.join(self.tmp.name, "market_updates.sqlite"))
        self.user_phone = "+15558889999"
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

    async def test_menu_number_three_returns_symbol_guidance(self):
        twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "3")
        self.assertIn("Send: SYMBOL", twiml)
        self.assertIn("Example: SYMBOL S&amp;P", twiml)

    async def test_remind_session_still_accepts_numeric_choice(self):
        first = await handle_inbound_sms(self.db, self.config, self.user_phone, "REMIND")
        self.assertIn("Reminder type.", first)

        second = await handle_inbound_sms(self.db, self.config, self.user_phone, "1")
        self.assertIn("Format: SYMBOL ABOVE|BELOW PRICE.", second)


if __name__ == "__main__":
    unittest.main()
