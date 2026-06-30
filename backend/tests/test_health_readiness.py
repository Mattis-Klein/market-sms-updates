import unittest

from app.main import app, build_readiness_report
from fastapi.testclient import TestClient
from market_updates.config import MarketConfig


def _config_with_twilio(enabled: bool) -> MarketConfig:
    return MarketConfig(
        twilio_account_sid="sid" if enabled else "",
        twilio_auth_token="token" if enabled else "",
        twilio_from_number="+18483291230" if enabled else "",
        market_updates_db_path="backend/data/market_updates.sqlite",
        market_access_approver_number="+18483291230",
        market_updates_allowed_numbers="",
        feedback_portal_ingest_url="",
        feedback_portal_ingest_token="",
        admin_token="change-me",
        public_base_url="https://yeshivachill.com",
    )


class HealthReadinessTests(unittest.TestCase):
    def test_health_ready_reports_not_ready_without_twilio(self):
        payload = build_readiness_report(
            config_override=_config_with_twilio(enabled=False),
            db_backend_override="sqlite",
            db_checker=lambda: (True, "ok"),
        )
        self.assertIn("checks", payload)
        self.assertFalse(payload["checks"]["twilio_configured"])
        self.assertFalse(payload["ok"])

    def test_health_ready_reports_ready_when_dependencies_pass(self):
        payload = build_readiness_report(
            config_override=_config_with_twilio(enabled=True),
            db_backend_override="postgres",
            db_checker=lambda: (True, "ok"),
        )
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["checks"]["twilio_configured"])
        self.assertTrue(payload["checks"]["database_connectivity"])

    def test_health_ready_endpoint_returns_structured_payload(self):
        client = TestClient(app)
        response = client.get("/health/ready")
        self.assertIn(response.status_code, {200, 503})
        payload = response.json()
        self.assertIn("ok", payload)
        self.assertIn("checks", payload)
        self.assertIn("details", payload)


if __name__ == "__main__":
    unittest.main()
