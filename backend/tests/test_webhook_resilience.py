import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


class WebhookResilienceTests(unittest.TestCase):
    def test_inbound_sms_returns_fallback_twiml_when_handler_raises(self):
        with patch("market_updates.webhook_api.handle_inbound_sms", new=AsyncMock(side_effect=RuntimeError("boom"))):
            client = TestClient(app)
            response = client.post(
                "/api/market-updates/sms",
                data={"From": "+18483291230", "Body": "MENU", "MessageSid": "SM123456789"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("<Response>", response.text)
        self.assertIn("Service is temporarily unavailable.", response.text)


if __name__ == "__main__":
    unittest.main()
