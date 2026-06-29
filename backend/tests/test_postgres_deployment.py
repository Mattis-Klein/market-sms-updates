import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from market_updates.db import Database
from scripts import migrate_sqlite_to_postgres as migrator


class DatabaseBackendSelectionTests(unittest.TestCase):
    def test_postgres_config_selected_by_database_url(self):
        self.assertTrue(Database.should_use_postgres("postgres://user:pass@host:5432/db"))
        self.assertTrue(Database.should_use_postgres("postgresql://user:pass@host:5432/db"))

    def test_sqlite_available_for_local_tests(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = os.path.join(tmp, "local.sqlite")
            db = Database(db_path, database_url="")
            self.assertFalse(db.is_postgres)


class AtomicClaimTests(unittest.TestCase):
    def test_two_workers_cannot_claim_same_reminder(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = os.path.join(tmp, "db.sqlite")
            db1 = Database(path)
            db2 = Database(path)
            due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            db1.create_scheduled_reminder("+15550001111", "once", due, due, "America/New_York", "claim-k")

            first = db1.claim_due_scheduled_reminders(datetime.now(timezone.utc).isoformat(), limit=10)
            second = db2.claim_due_scheduled_reminders(datetime.now(timezone.utc).isoformat(), limit=10)

            self.assertEqual(len(first), 1)
            self.assertEqual(len(second), 0)


class MigrationScriptTests(unittest.TestCase):
    def _build_sqlite_source(self, path: str):
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_sms_sessions (
                    phone_number TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    draft_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO market_sms_sessions (phone_number, state, draft_json, updated_at) VALUES (?, ?, ?, ?)",
                ("+15550001111", "state1", "{}", "2026-06-29T00:00:00+00:00"),
            )
            conn.commit()

    def test_copy_table_preserves_ids_and_rows(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            src = os.path.join(tmp, "src.sqlite")
            with sqlite3.connect(src) as conn:
                conn.execute(
                    "CREATE TABLE market_feedback_entries (id INTEGER PRIMARY KEY, phone_number TEXT, message TEXT, source TEXT, created_at TEXT)"
                )
                conn.execute(
                    "INSERT INTO market_feedback_entries (id, phone_number, message, source, created_at) VALUES (42, '+1555', 'hello', 'sms', '2026-06-29T00:00:00+00:00')"
                )
                conn.commit()

            captured = []

            class FakeCursor:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    return False

                def execute(self, query, params=None):
                    captured.append((query, params))

            class FakeConn:
                def cursor(self):
                    return FakeCursor()

            copied = migrator.copy_table(src, FakeConn(), "market_feedback_entries")
            self.assertEqual(copied, 1)
            self.assertTrue(any(params and params[0] == 42 for _, params in captured))

    def test_migration_refuses_when_destination_nonempty(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            src = os.path.join(tmp, "src.sqlite")
            self._build_sqlite_source(src)

            class FakeCursor:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    return False

                def execute(self, *_args, **_kwargs):
                    return None

            class FakeConn:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb):
                    return False

                def cursor(self, **_kwargs):
                    return FakeCursor()

                def commit(self):
                    return None

            with patch.object(migrator, "TABLES", ["market_sms_sessions"]), patch.object(
                migrator, "postgres_has_data", return_value=True
            ), patch.object(migrator, "psycopg") as fake_psycopg:
                fake_psycopg.connect.return_value = FakeConn()
                with self.assertRaises(RuntimeError):
                    migrator.run(
                        sqlite_path=src,
                        database_url="postgres://example",
                        backup_dir=os.path.join(tmp, "backups"),
                        force_if_destination_nonempty=False,
                    )
if __name__ == "__main__":
    unittest.main()
