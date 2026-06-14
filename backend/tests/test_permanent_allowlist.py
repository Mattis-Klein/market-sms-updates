import os
import tempfile
import unittest

from market_updates.allowlist import is_permanent_allowlisted, parse_allowed_numbers
from market_updates.config import MarketConfig
from market_updates.db import Database
from market_updates.keyword_handlers import handle_inbound_sms


class PermanentAllowlistTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.tmp.name, "market_updates.sqlite")
        self.db = Database(self.db_path)
        self.permanent_csv = "+18483291230,+18458981872,+19145870597"
        self.config = MarketConfig(
            twilio_account_sid="",
            twilio_auth_token="",
            twilio_from_number="",
            market_updates_db_path=self.db_path,
            market_access_approver_number="+18483291230",
            market_updates_allowed_numbers=self.permanent_csv,
            feedback_portal_ingest_url="",
            feedback_portal_ingest_token="",
            admin_token="change-me",
            public_base_url="https://yeshivachill.com",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_allowed_numbers_normalizes_to_e164(self):
        parsed = parse_allowed_numbers("8483291230,+1 (845) 898-1872, 19145870597")
        self.assertEqual(parsed, {"+18483291230", "+18458981872", "+19145870597"})

    def test_env_allowlist_check_matches_normalized_number(self):
        self.assertTrue(is_permanent_allowlisted(self.permanent_csv, "8458981872"))
        self.assertTrue(is_permanent_allowlisted(self.permanent_csv, "+19145870597"))
        self.assertFalse(is_permanent_allowlisted(self.permanent_csv, "+15551230000"))

    async def test_inbound_allows_env_number_without_db_row(self):
        twiml = await handle_inbound_sms(self.db, self.config, "+18458981872", "MENU")
        self.assertIn("Market SMS Assistant", twiml)
        self.assertIn("Reply with a number to get the next step:", twiml)

    async def test_inbound_keeps_approval_flow_for_other_numbers(self):
        twiml = await handle_inbound_sms(self.db, self.config, "+15551230000", "MENU")
        self.assertIn("Access blocked. Reply REQUEST ACCESS to request approval.", twiml)


if __name__ == "__main__":
    unittest.main()
