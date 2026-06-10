import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MarketConfig:
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    market_updates_db_path: str
    market_access_approver_number: str
    market_updates_allowed_numbers: str
    feedback_portal_ingest_url: str
    feedback_portal_ingest_token: str
    admin_token: str
    public_base_url: str


def load_config() -> MarketConfig:
    return MarketConfig(
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
        twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", os.getenv("TWILIO_PHONE_NUMBER", "")),
        market_updates_db_path=os.getenv("MARKET_UPDATES_DB_PATH", "backend/data/market_updates.sqlite"),
        market_access_approver_number=os.getenv("MARKET_ACCESS_APPROVER_NUMBER", "+18483291230"),
        market_updates_allowed_numbers=os.getenv("MARKET_UPDATES_ALLOWED_NUMBERS", ""),
        feedback_portal_ingest_url=os.getenv("FEEDBACK_PORTAL_INGEST_URL", ""),
        feedback_portal_ingest_token=os.getenv("FEEDBACK_PORTAL_INGEST_TOKEN", ""),
        admin_token=os.getenv("MARKET_ADMIN_TOKEN", "change-me"),
        public_base_url=os.getenv("MARKET_PUBLIC_BASE_URL", "https://yeshivachill.com"),
    )
