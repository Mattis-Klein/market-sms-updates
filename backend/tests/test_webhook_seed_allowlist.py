import os
import tempfile
import unittest

from market_updates.allowlist import is_allowlisted
from market_updates.allowlist import seed_allowlist
from market_updates.db import Database


class WebhookSeedAllowlistTests(unittest.TestCase):
    def test_seed_allowlist_syncs_env_allowlist_numbers(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = os.path.join(tmpdir, "market_updates.sqlite")
            db = Database(db_path)
            seed_allowlist(db, "+18483291230,+18458981872,+19145870597")
            self.assertTrue(is_allowlisted(db, "+18483291230"))
            self.assertTrue(is_allowlisted(db, "+18458981872"))
            self.assertTrue(is_allowlisted(db, "+19145870597"))


if __name__ == "__main__":
    unittest.main()
