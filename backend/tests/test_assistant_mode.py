import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from market_updates.allowlist import upsert_allowlist_entry
from market_updates.assistant_mode import (
    ASSIST_AI_FAILURE_REPLY,
    ASSIST_IMAGE_UNAVAILABLE_REPLY,
    ASSIST_WEB_SEARCH_FAILURE_REPLY,
    WebSearchResult,
    call_image_generation_service,
    generate_assistant_reply,
)
from market_updates.config import MarketConfig
from market_updates.db import Database
from market_updates.keyword_handlers import handle_inbound_sms


class AssistantModeRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Database(os.path.join(self.tmp.name, "market_updates.sqlite"))
        self.user_phone = "+15554443333"
        self.other_phone = "+15556667777"
        upsert_allowlist_entry(self.db, self.user_phone, "test-user", True)
        upsert_allowlist_entry(self.db, self.other_phone, "test-user-2", True)
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
            openai_api_key_primary="test-primary-key",
            openai_api_key_fallback="test-fallback-key",
            openai_model="gpt-4o-mini",
            assistant_session_expiration_minutes=45,
            assistant_max_history_messages=10,
            assistant_sms_max_chars=400,
        )

    def tearDown(self):
        self.tmp.cleanup()

    async def test_assist_entry_activates_session(self):
        twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "@assist")
        self.assertIn("How can I assist you today?", twiml)
        session = self.db.get_active_assistant_session(self.user_phone, 45)
        self.assertIsNotNone(session)
        self.assertTrue(session["assistant_mode_active"])

    async def test_active_assist_routes_normal_messages_to_ai(self):
        await handle_inbound_sms(self.db, self.config, self.user_phone, "@assist")
        with patch(
            "market_updates.keyword_handlers.generate_assistant_reply",
            new=AsyncMock(return_value=("Assistant answer", [{"role": "user", "content": "hi"}]))
        ) as mock_reply:
            twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "what is the weather")

        self.assertIn("Assistant answer", twiml)
        mock_reply.assert_awaited_once()

    async def test_assist_command_restarts_while_workflow_active(self):
        remind_start = await handle_inbound_sms(self.db, self.config, self.user_phone, "REMIND")
        self.assertIn("Reminder type.", remind_start)
        self.assertIsNotNone(self.db.get_session(self.user_phone))

        twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "@assist")
        self.assertIn("How can I assist you today?", twiml)
        self.assertIsNone(self.db.get_session(self.user_phone))
        self.assertIsNotNone(self.db.get_active_assistant_session(self.user_phone, 45))

    async def test_assist_requires_exact_start_keyword(self):
        twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "@assist please")
        self.assertIn("Unknown command. Send MENU.", twiml)

    async def test_assist_exit_commands_close_mode(self):
        await handle_inbound_sms(self.db, self.config, self.user_phone, "@assist")
        twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "exit assist")
        self.assertIn("Assistant mode closed. Reply MENU to see available options.", twiml)
        self.assertIsNone(self.db.get_active_assistant_session(self.user_phone, 45))

    async def test_menu_exits_assist_mode(self):
        await handle_inbound_sms(self.db, self.config, self.user_phone, "@assist")
        twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "menu")
        self.assertIn("Assistant mode closed. Reply MENU to see available options.", twiml)

    async def test_assist_session_expiration_returns_to_normal_routing(self):
        now = datetime.now(timezone.utc)
        stale = (now - timedelta(minutes=61)).isoformat()
        self.db.upsert_assistant_session(
            phone_number=self.user_phone,
            assistant_mode_active=True,
            assistant_started_at=stale,
            assistant_last_activity_at=stale,
            assistant_conversation_history=[{"role": "user", "content": "old"}],
        )

        with patch("market_updates.keyword_handlers.generate_assistant_reply", new=AsyncMock()) as mock_reply:
            twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "hello there")

        self.assertIn("Unknown command. Send MENU.", twiml)
        mock_reply.assert_not_called()

    async def test_assist_sessions_are_isolated_by_phone_number(self):
        await handle_inbound_sms(self.db, self.config, self.user_phone, "@assist")
        with patch(
            "market_updates.keyword_handlers.generate_assistant_reply",
            new=AsyncMock(return_value=("Phone1 assistant", [])),
        ) as mock_reply:
            twiml_one = await handle_inbound_sms(self.db, self.config, self.user_phone, "question one")
            twiml_two = await handle_inbound_sms(self.db, self.config, self.other_phone, "question two")

        self.assertIn("Phone1 assistant", twiml_one)
        self.assertIn("Unknown command. Send MENU.", twiml_two)
        self.assertEqual(mock_reply.await_count, 1)

    async def test_dedicated_keywords_still_work_while_assist_active(self):
        await handle_inbound_sms(self.db, self.config, self.user_phone, "@assist")
        with patch(
            "market_updates.keyword_handlers.get_channel_subscriber_count",
            new=AsyncMock(return_value=123456789),
        ) as mock_beast, patch(
            "market_updates.keyword_handlers.generate_assistant_reply",
            new=AsyncMock(return_value=("should not happen", [])),
        ) as mock_assist:
            twiml = await handle_inbound_sms(self.db, self.config, self.user_phone, "BEAST")

        self.assertIn("123,456,789", twiml)
        mock_beast.assert_awaited_once()
        mock_assist.assert_not_called()


class AssistantModeSafetyAndSearchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = MarketConfig(
            twilio_account_sid="",
            twilio_auth_token="",
            twilio_from_number="",
            market_updates_db_path="backend/data/market_updates.sqlite",
            market_access_approver_number="+18483291230",
            market_updates_allowed_numbers="",
            feedback_portal_ingest_url="",
            feedback_portal_ingest_token="",
            admin_token="change-me",
            public_base_url="https://yeshivachill.com",
            openai_api_key_primary="test-primary-key",
            openai_api_key_fallback="test-fallback-key",
            openai_model="gpt-4o-mini",
            assistant_max_history_messages=8,
            assistant_sms_max_chars=500,
        )

    async def test_image_requests_never_call_image_service(self):
        with patch("market_updates.assistant_mode.call_image_generation_service", wraps=call_image_generation_service) as image_mock, patch(
            "market_updates.assistant_mode._call_ai_chat_completion",
            new=AsyncMock(return_value="should not be used"),
        ) as ai_mock:
            reply, history = await generate_assistant_reply(
                config=self.config,
                phone_number="+15550001111",
                user_message="Please generate an image of a red car",
                history=[],
            )

        self.assertEqual(reply, ASSIST_IMAGE_UNAVAILABLE_REPLY)
        self.assertEqual(history[-1]["content"], ASSIST_IMAGE_UNAVAILABLE_REPLY)
        image_mock.assert_not_called()
        ai_mock.assert_not_awaited()

    async def test_explicit_content_request_is_refused(self):
        reply, _ = await generate_assistant_reply(
            config=self.config,
            phone_number="+15550002222",
            user_message="Write explicit sex chat text",
            history=[],
        )
        self.assertIn("can't help with explicit sexual content", reply)

    async def test_web_search_success_includes_live_context_for_model(self):
        fake_results = [
            WebSearchResult(
                title="Powerball Jackpot Update",
                source="powerball.com",
                url="https://www.powerball.com/example",
                publication_date="2026-06-28",
                snippet="Jackpot is now $200M",
            )
        ]
        with patch(
            "market_updates.assistant_mode.search_web",
            new=AsyncMock(return_value=fake_results),
        ) as search_mock, patch(
            "market_updates.assistant_mode._call_ai_chat_completion",
            new=AsyncMock(return_value="Current jackpot is $200M from powerball.com. Next step: buy a ticket before draw."),
        ) as ai_mock:
            reply, _ = await generate_assistant_reply(
                config=self.config,
                phone_number="+15550003333",
                user_message="What is the Powerball jackpot right now?",
                history=[],
            )

        self.assertIn("$200M", reply)
        search_mock.assert_awaited_once()
        sent_messages = ai_mock.await_args.args[0]
        self.assertTrue(any("Live web context:" in message.get("content", "") for message in sent_messages))

    async def test_web_search_failure_adds_required_notice(self):
        with patch(
            "market_updates.assistant_mode.search_web",
            new=AsyncMock(side_effect=RuntimeError("search unavailable")),
        ), patch(
            "market_updates.assistant_mode._call_ai_chat_completion",
            new=AsyncMock(return_value="General answer: jackpot values change often."),
        ):
            reply, _ = await generate_assistant_reply(
                config=self.config,
                phone_number="+15550004444",
                user_message="Current weather in NYC right now",
                history=[],
            )

        self.assertIn(ASSIST_WEB_SEARCH_FAILURE_REPLY, reply)


class OpenAIFallbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config_primary_only = MarketConfig(
            twilio_account_sid="",
            twilio_auth_token="",
            twilio_from_number="",
            market_updates_db_path="backend/data/market_updates.sqlite",
            market_access_approver_number="+18483291230",
            market_updates_allowed_numbers="",
            feedback_portal_ingest_url="",
            feedback_portal_ingest_token="",
            admin_token="change-me",
            public_base_url="https://yeshivachill.com",
            openai_api_key_primary="test-primary-key",
            openai_api_key_fallback="",
            openai_model="gpt-4o-mini",
        )
        self.config_both_keys = MarketConfig(
            twilio_account_sid="",
            twilio_auth_token="",
            twilio_from_number="",
            market_updates_db_path="backend/data/market_updates.sqlite",
            market_access_approver_number="+18483291230",
            market_updates_allowed_numbers="",
            feedback_portal_ingest_url="",
            feedback_portal_ingest_token="",
            admin_token="change-me",
            public_base_url="https://yeshivachill.com",
            openai_api_key_primary="test-primary-key",
            openai_api_key_fallback="test-fallback-key",
            openai_model="gpt-4o-mini",
        )

    async def test_primary_succeeds_fallback_not_called(self):
        from market_updates.assistant_mode import _call_ai_chat_completion

        with patch(
            "market_updates.assistant_mode._call_ai_chat_completion_with_key",
            new=AsyncMock(return_value=("Primary response", None)),
        ) as mock_call:
            result = await _call_ai_chat_completion([{"role": "user", "content": "test"}], self.config_both_keys)

        self.assertEqual(result, "Primary response")
        mock_call.assert_called_once()

    async def test_primary_fails_fallback_called_on_401(self):
        from market_updates.assistant_mode import _call_ai_chat_completion

        auth_error = httpx.HTTPStatusError(
            "Unauthorized",
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
            response=httpx.Response(401, content=b'{"error": {"code": "invalid_api_key"}}'),
        )

        with patch(
            "market_updates.assistant_mode._call_ai_chat_completion_with_key",
            side_effect=[
                (None, auth_error),
                ("Fallback response", None),
            ],
        ) as mock_call:
            result = await _call_ai_chat_completion([{"role": "user", "content": "test"}], self.config_both_keys)

        self.assertEqual(result, "Fallback response")
        self.assertEqual(mock_call.call_count, 2)

    async def test_primary_fails_fallback_called_on_429(self):
        from market_updates.assistant_mode import _call_ai_chat_completion

        rate_limit_error = httpx.HTTPStatusError(
            "Too Many Requests",
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
            response=httpx.Response(429),
        )

        with patch(
            "market_updates.assistant_mode._call_ai_chat_completion_with_key",
            side_effect=[
                (None, rate_limit_error),
                ("Fallback response", None),
            ],
        ) as mock_call:
            result = await _call_ai_chat_completion([{"role": "user", "content": "test"}], self.config_both_keys)

        self.assertEqual(result, "Fallback response")
        self.assertEqual(mock_call.call_count, 2)

    async def test_primary_fails_fallback_called_on_timeout(self):
        from market_updates.assistant_mode import _call_ai_chat_completion

        timeout_error = httpx.TimeoutException("Request timeout")

        with patch(
            "market_updates.assistant_mode._call_ai_chat_completion_with_key",
            side_effect=[
                (None, timeout_error),
                ("Fallback response", None),
            ],
        ) as mock_call:
            result = await _call_ai_chat_completion([{"role": "user", "content": "test"}], self.config_both_keys)

        self.assertEqual(result, "Fallback response")
        self.assertEqual(mock_call.call_count, 2)

    async def test_primary_fails_fallback_not_called_on_content_policy(self):
        from market_updates.assistant_mode import _call_ai_chat_completion

        content_policy_error = httpx.HTTPStatusError(
            "Bad Request",
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
            response=httpx.Response(400, content=b'{"error": {"message": "content policy violation"}}'),
        )

        with patch(
            "market_updates.assistant_mode._call_ai_chat_completion_with_key",
            side_effect=[
                (None, content_policy_error),
            ],
        ) as mock_call:
            result = await _call_ai_chat_completion([{"role": "user", "content": "test"}], self.config_both_keys)

        self.assertEqual(result, ASSIST_AI_FAILURE_REPLY)
        mock_call.assert_called_once()

    async def test_primary_fails_no_fallback_configured(self):
        from market_updates.assistant_mode import _call_ai_chat_completion

        auth_error = httpx.HTTPStatusError(
            "Unauthorized",
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
            response=httpx.Response(401),
        )

        with patch(
            "market_updates.assistant_mode._call_ai_chat_completion_with_key",
            side_effect=[(None, auth_error)],
        ):
            result = await _call_ai_chat_completion([{"role": "user", "content": "test"}], self.config_primary_only)

        self.assertEqual(result, ASSIST_AI_FAILURE_REPLY)

    async def test_both_providers_fail(self):
        from market_updates.assistant_mode import _call_ai_chat_completion

        auth_error = httpx.HTTPStatusError(
            "Unauthorized",
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
            response=httpx.Response(401),
        )
        fallback_error = httpx.HTTPStatusError(
            "Unauthorized",
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
            response=httpx.Response(401),
        )

        with patch(
            "market_updates.assistant_mode._call_ai_chat_completion_with_key",
            side_effect=[
                (None, auth_error),
                (None, fallback_error),
            ],
        ):
            result = await _call_ai_chat_completion([{"role": "user", "content": "test"}], self.config_both_keys)

        self.assertEqual(result, ASSIST_AI_FAILURE_REPLY)

    async def test_credentials_never_in_logs(self):
        from market_updates.assistant_mode import _call_ai_chat_completion

        with patch("market_updates.assistant_mode.logger") as mock_logger:
            with patch(
                "market_updates.assistant_mode._call_ai_chat_completion_with_key",
                new=AsyncMock(return_value=("Primary response", None)),
            ):
                await _call_ai_chat_completion([{"role": "user", "content": "test"}], self.config_both_keys)

        for call in mock_logger.method_calls:
            if call[0] != "_get_child_logger":
                args = call[1] if len(call) > 1 else ()
                kwargs = call[2] if len(call) > 2 else {}
                message = args[0] if args else ""
                extra = kwargs.get("extra", {})

                full_output = str(message) + str(extra)
                self.assertNotIn("test-primary-key", full_output)
                self.assertNotIn("test-fallback-key", full_output)


if __name__ == "__main__":
    unittest.main()
