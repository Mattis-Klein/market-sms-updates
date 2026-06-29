import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from market_updates.allowlist import upsert_allowlist_entry
from market_updates.assistant_mode import (
    ASSIST_WEB_SEARCH_FAILURE_REPLY,
    ASSIST_START_REPLY,
    generate_assistant_reply,
)
from market_updates.config import MarketConfig
from market_updates.db import Database
from market_updates.keyword_handlers import handle_inbound_sms
from market_updates.reminder_worker import process_due_reminders_once
from market_updates.reminders import schedule_reminder


def _base_config(db_path: str) -> MarketConfig:
    return MarketConfig(
        twilio_account_sid="sid",
        twilio_auth_token="token",
        twilio_from_number="+15550000000",
        market_updates_db_path=db_path,
        market_access_approver_number="+18483291230",
        market_updates_allowed_numbers="",
        feedback_portal_ingest_url="",
        feedback_portal_ingest_token="",
        admin_token="change-me",
        public_base_url="https://yeshivachill.com",
        openai_api_key_primary="primary",
        openai_api_key_fallback="fallback",
        openai_model="gpt-4o-mini",
        assist_default_timezone="America/New_York",
        assist_force_web_for_current_info=True,
        reminders_enabled=True,
        reminder_poll_seconds=15,
        reminder_max_attempts=3,
        reminder_retry_delay_seconds=60,
        reminder_processing_timeout_seconds=300,
    )


class LiveInformationTests(unittest.IsolatedAsyncioTestCase):
    async def test_news_today_forces_web_search(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = _base_config(os.path.join(tmp, "db.sqlite"))
            db = Database(config.market_updates_db_path)
            captured = {}

            async def fake_execute(payload, _db, _phone, _config):
                captured["tool_choice"] = payload["tool_choice"]
                return type("R", (), {"text": "x", "web_search_used": True, "web_search_failed": False})

            with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
                await generate_assistant_reply(config, db, "+15550001111", "What is the news today?", [])

            self.assertEqual(captured["tool_choice"], "required")

    async def test_powerball_right_now_forces_web_search(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = _base_config(os.path.join(tmp, "db.sqlite"))
            db = Database(config.market_updates_db_path)
            captured = {}

            async def fake_execute(payload, _db, _phone, _config):
                captured["tool_choice"] = payload["tool_choice"]
                return type("R", (), {"text": "x", "web_search_used": True, "web_search_failed": False})

            with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
                await generate_assistant_reply(config, db, "+15550001111", "What is the Powerball jackpot right now?", [])

            self.assertEqual(captured["tool_choice"], "required")

    async def test_stable_question_uses_auto(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = _base_config(os.path.join(tmp, "db.sqlite"))
            db = Database(config.market_updates_db_path)
            captured = {}

            async def fake_execute(payload, _db, _phone, _config):
                captured["tool_choice"] = payload["tool_choice"]
                return type("R", (), {"text": "William Shakespeare.", "web_search_used": False, "web_search_failed": False})

            with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
                await generate_assistant_reply(config, db, "+15550001111", "Who wrote Hamlet?", [])

            self.assertEqual(captured["tool_choice"], "auto")

    async def test_search_failure_never_invents_current_info(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = _base_config(os.path.join(tmp, "db.sqlite"))
            db = Database(config.market_updates_db_path)

            async def fake_execute(_payload, _db, _phone, _config):
                return type("R", (), {"text": "Some stale model guess", "web_search_used": False, "web_search_failed": True})

            with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
                reply, _ = await generate_assistant_reply(config, db, "+15550001111", "Latest news now", [])

            self.assertEqual(reply, ASSIST_WEB_SEARCH_FAILURE_REPLY)

    async def test_search_result_response_can_include_sources(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = _base_config(os.path.join(tmp, "db.sqlite"))
            db = Database(config.market_updates_db_path)

            async def fake_execute(_payload, _db, _phone, _config):
                return type(
                    "R",
                    (),
                    {
                        "text": "As of 2026-06-29, source: weather.gov https://www.weather.gov and nytimes.com",
                        "web_search_used": True,
                        "web_search_failed": False,
                    },
                )

            with patch("market_updates.assistant_mode._execute_responses_loop", new=fake_execute):
                reply, _ = await generate_assistant_reply(config, db, "+15550001111", "Weather today", [])

            self.assertIn("weather.gov", reply)
            self.assertIn("https://", reply)


class ReminderPersistenceAndWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_half_hour_reminder_stores_30_minutes_future(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = Database(os.path.join(tmp, "db.sqlite"))
            now = datetime.now(timezone.utc)
            target = (now + timedelta(minutes=30)).astimezone(timezone.utc)
            target_iso = target.astimezone().isoformat()

            result = schedule_reminder(
                db=db,
                phone_number="+15551112222",
                reminder_text="call my brother",
                scheduled_time_local=target_iso,
                timezone_name="America/New_York",
            )
            self.assertTrue(result["ok"])
            utc_dt = datetime.fromisoformat(result["scheduled_at_utc"])
            delta = abs((utc_dt - target).total_seconds())
            self.assertLessEqual(delta, 120)

    async def test_reminder_survives_restart(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = os.path.join(tmp, "db.sqlite")
            db1 = Database(path)
            schedule_reminder(db1, "+15551112222", "renew", "tomorrow 9 am", "America/New_York")

            db2 = Database(path)
            rows = db2.list_scheduled_reminders("+15551112222", include_inactive=True)
            self.assertEqual(len(rows), 1)

    async def test_due_reminder_sends_through_twilio(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = _base_config(os.path.join(tmp, "db.sqlite"))
            db = Database(config.market_updates_db_path)
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            db.create_scheduled_reminder(
                "+15551112222", "call my brother", past, past, "America/New_York", "k1"
            )

            with patch(
                "market_updates.reminder_worker.send_sms_with_result",
                new=AsyncMock(return_value={"ok": True, "error_type": "none", "error": ""}),
            ) as send_mock:
                out = await process_due_reminders_once(db, config)

            self.assertEqual(out["sent"], 1)
            self.assertEqual(send_mock.await_count, 1)

    async def test_reminder_never_delivered_twice(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = _base_config(os.path.join(tmp, "db.sqlite"))
            db = Database(config.market_updates_db_path)
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            db.create_scheduled_reminder("+15551112222", "once", past, past, "America/New_York", "k2")

            with patch(
                "market_updates.reminder_worker.send_sms_with_result",
                new=AsyncMock(return_value={"ok": True, "error_type": "none", "error": ""}),
            ) as send_mock:
                await process_due_reminders_once(db, config)
                await process_due_reminders_once(db, config)

            self.assertEqual(send_mock.await_count, 1)

    async def test_temporary_twilio_error_retries(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = _base_config(os.path.join(tmp, "db.sqlite"))
            db = Database(config.market_updates_db_path)
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            db.create_scheduled_reminder("+15551112222", "retry", past, past, "America/New_York", "k3")

            with patch(
                "market_updates.reminder_worker.send_sms_with_result",
                new=AsyncMock(return_value={"ok": False, "error_type": "temporary", "error": "timeout"}),
            ):
                out = await process_due_reminders_once(db, config)

            self.assertEqual(out["retried"], 1)

    async def test_permanent_failure_stops_retry(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = _base_config(os.path.join(tmp, "db.sqlite"))
            db = Database(config.market_updates_db_path)
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            reminder_id = db.create_scheduled_reminder("+15551112222", "bad num", past, past, "America/New_York", "k4")

            with patch(
                "market_updates.reminder_worker.send_sms_with_result",
                new=AsyncMock(return_value={"ok": False, "error_type": "permanent", "error": "invalid number"}),
            ):
                out = await process_due_reminders_once(db, config)

            self.assertEqual(out["failed"], 1)
            rows = db.list_scheduled_reminders("+15551112222", include_inactive=True)
            target = [r for r in rows if r["id"] == reminder_id][0]
            self.assertEqual(target["status"], "failed")

    async def test_user_cannot_manage_other_users_reminders(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = Database(os.path.join(tmp, "db.sqlite"))
            now = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            reminder_id = db.create_scheduled_reminder("+15551112222", "mine", now, now, "America/New_York", "k5")

            ok = db.cancel_scheduled_reminder("+15553334444", reminder_id)
            self.assertFalse(ok)

    async def test_cancelled_reminder_not_delivered(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = _base_config(os.path.join(tmp, "db.sqlite"))
            db = Database(config.market_updates_db_path)
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            reminder_id = db.create_scheduled_reminder("+15551112222", "cancel me", past, past, "America/New_York", "k6")
            db.cancel_scheduled_reminder("+15551112222", reminder_id)

            with patch("market_updates.reminder_worker.send_sms_with_result", new=AsyncMock()) as send_mock:
                await process_due_reminders_once(db, config)

            send_mock.assert_not_awaited()

    async def test_conversation_expiration_does_not_delete_reminders(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = Database(os.path.join(tmp, "db.sqlite"))
            old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
            db.upsert_assistant_session("+15551112222", True, old, old, [])

            schedule_reminder(db, "+15551112222", "still active", "tomorrow 9am", "America/New_York")
            _ = db.get_active_assistant_session("+15551112222", expiration_minutes=45)
            rows = db.list_scheduled_reminders("+15551112222", include_inactive=False)
            self.assertEqual(len(rows), 1)


class RoutingPriorityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(os.path.join(self.tmp.name, "db.sqlite"))
        self.config = _base_config(os.path.join(self.tmp.name, "db.sqlite"))
        self.phone = "+15550008888"
        upsert_allowlist_entry(self.db, self.phone, "test", True)

    def tearDown(self):
        self.tmp.cleanup()

    async def _activate(self):
        twiml = await handle_inbound_sms(self.db, self.config, self.phone, "@assist")
        self.assertIn(ASSIST_START_REPLY, twiml)

    async def test_active_assistant_intercepts_menu(self):
        await self._activate()
        with patch("market_updates.keyword_handlers.generate_assistant_reply", new=AsyncMock(return_value=("AI menu answer", []))):
            twiml = await handle_inbound_sms(self.db, self.config, self.phone, "menu")
        self.assertIn("AI menu answer", twiml)

    async def test_active_assistant_intercepts_powerball(self):
        await self._activate()
        with patch("market_updates.keyword_handlers.generate_assistant_reply", new=AsyncMock(return_value=("AI powerball", []))):
            twiml = await handle_inbound_sms(self.db, self.config, self.phone, "powerball")
        self.assertIn("AI powerball", twiml)

    async def test_active_assistant_intercepts_check(self):
        await self._activate()
        with patch("market_updates.keyword_handlers.generate_assistant_reply", new=AsyncMock(return_value=("AI check", []))), patch(
            "market_updates.keyword_handlers.get_latest_quote", new=AsyncMock()
        ) as quote_mock:
            twiml = await handle_inbound_sms(self.db, self.config, self.phone, "check aapl")
        self.assertIn("AI check", twiml)
        quote_mock.assert_not_awaited()

    async def test_active_assistant_intercepts_reminders(self):
        await self._activate()
        with patch("market_updates.keyword_handlers.generate_assistant_reply", new=AsyncMock(return_value=("AI reminders", []))):
            twiml = await handle_inbound_sms(self.db, self.config, self.phone, "reminders")
        self.assertIn("AI reminders", twiml)

    async def test_normal_keyword_behavior_returns_after_exit(self):
        await self._activate()
        await handle_inbound_sms(self.db, self.config, self.phone, "@exit")
        with patch("market_updates.keyword_handlers.get_channel_subscriber_count", new=AsyncMock(return_value=9999)):
            twiml = await handle_inbound_sms(self.db, self.config, self.phone, "BEAST")
        self.assertIn("9,999", twiml)

    async def test_compliance_commands_continue_to_work(self):
        await self._activate()
        twiml = await handle_inbound_sms(self.db, self.config, self.phone, "STOP")
        self.assertIn("unsubscribed", twiml.lower())

    async def test_no_normal_keyword_handler_runs_while_active(self):
        await self._activate()
        with patch("market_updates.keyword_handlers.get_channel_subscriber_count", new=AsyncMock()) as beast_mock, patch(
            "market_updates.keyword_handlers.generate_assistant_reply", new=AsyncMock(return_value=("AI only", []))
        ):
            twiml = await handle_inbound_sms(self.db, self.config, self.phone, "BEAST")
        self.assertIn("AI only", twiml)
        beast_mock.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
