import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
    openai_api_key_primary: str = ""
    openai_api_key_fallback: str = ""
    openai_model: str = "gpt-4o-mini"
    assistant_ai_base_url: str = "https://api.openai.com/v1"
    assistant_ai_timeout_seconds: int = 20
    assist_default_timezone: str = "America/New_York"
    assist_force_web_for_current_info: bool = True
    assistant_search_provider: str = "tavily"
    assistant_search_api_key: str = ""
    assistant_search_timeout_seconds: int = 8
    assistant_search_max_results: int = 4
    assistant_session_expiration_minutes: int = 45
    assistant_max_history_messages: int = 12
    assistant_sms_max_chars: int = 1200
    reminders_enabled: bool = True
    reminder_poll_seconds: int = 15
    reminder_max_attempts: int = 3
    reminder_retry_delay_seconds: int = 60
    reminder_processing_timeout_seconds: int = 300
    database_url: str = ""


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
        openai_api_key_primary=os.getenv("OPENAI_API_KEY_PRIMARY", ""),
        openai_api_key_fallback=os.getenv("OPENAI_API_KEY_FALLBACK", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        assistant_ai_base_url=os.getenv("ASSISTANT_AI_BASE_URL", "https://api.openai.com/v1"),
        assistant_ai_timeout_seconds=int(os.getenv("ASSISTANT_AI_TIMEOUT_SECONDS", "20")),
        assist_default_timezone=os.getenv("ASSIST_DEFAULT_TIMEZONE", "America/New_York"),
        assist_force_web_for_current_info=os.getenv("ASSIST_FORCE_WEB_FOR_CURRENT_INFO", "true").lower() == "true",
        assistant_search_provider=os.getenv("ASSISTANT_SEARCH_PROVIDER", "tavily"),
        assistant_search_api_key=os.getenv("ASSISTANT_SEARCH_API_KEY", ""),
        assistant_search_timeout_seconds=int(os.getenv("ASSISTANT_SEARCH_TIMEOUT_SECONDS", "8")),
        assistant_search_max_results=int(os.getenv("ASSISTANT_SEARCH_MAX_RESULTS", "4")),
        assistant_session_expiration_minutes=int(os.getenv("ASSISTANT_SESSION_EXPIRATION_MINUTES", "45")),
        assistant_max_history_messages=int(os.getenv("ASSISTANT_MAX_HISTORY_MESSAGES", "12")),
        assistant_sms_max_chars=int(os.getenv("ASSISTANT_SMS_MAX_CHARS", "1200")),
        reminders_enabled=os.getenv("REMINDERS_ENABLED", "true").lower() == "true",
        reminder_poll_seconds=int(os.getenv("REMINDER_POLL_SECONDS", "15")),
        reminder_max_attempts=int(os.getenv("REMINDER_MAX_ATTEMPTS", "3")),
        reminder_retry_delay_seconds=int(os.getenv("REMINDER_RETRY_DELAY_SECONDS", "60")),
        reminder_processing_timeout_seconds=int(os.getenv("REMINDER_PROCESSING_TIMEOUT_SECONDS", "300")),
        database_url=os.getenv("DATABASE_URL", ""),
    )


def validate_openai_config(config: MarketConfig) -> str | None:
    """Validate OpenAI configuration at startup.
    
    Returns error message if validation fails, None if successful.
    """
    if not config.openai_api_key_primary:
        return "OPENAI_API_KEY_PRIMARY is required for assistant mode."
    if not config.openai_api_key_fallback:
        logger.warning(
            "openai_fallback_key_not_configured",
            extra={"note": "Assistant mode will use primary key only; no fallback available."},
        )
    return None
