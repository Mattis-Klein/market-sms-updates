from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Form, Response

from .allowlist import seed_allowlist
from .config import load_config
from .db import Database
from .keyword_handlers import handle_inbound_sms


router = APIRouter(tags=["market-webhook"])
logger = logging.getLogger(__name__)
config = load_config()
db: Database | None = None
db_init_error: str = ""


def _init_db_if_needed() -> Database | None:
    global db
    global db_init_error

    if db is not None:
        return db

    try:
        db = Database(config.market_updates_db_path, database_url=config.database_url)
        seed_allowlist(db, config.market_updates_allowed_numbers)
        db_init_error = ""
        return db
    except Exception as exc:  # pragma: no cover - defensive startup path
        db = None
        db_init_error = f"{type(exc).__name__}"
        logger.exception("webhook_db_init_failed")
        return None


def get_database_backend_name() -> str:
    if db is not None:
        return db.backend
    if Database.should_use_postgres(config.database_url):
        return "postgres"
    return "sqlite"


def check_database_connectivity() -> tuple[bool, str]:
    live_db = _init_db_if_needed()
    if live_db is None:
        reason = db_init_error or "unknown"
        return False, f"db_init_failed:{reason}"
    try:
        with live_db.connect() as conn:
            conn.execute("SELECT 1")
        return True, "ok"
    except Exception as exc:  # pragma: no cover
        return False, f"db_error:{type(exc).__name__}"


_init_db_if_needed()


def _twiml_message(body: str) -> str:
    escaped = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{escaped}</Message></Response>"


@router.post("/api/market-updates/sms")
async def inbound_sms(
    From: str = Form(default=""),
    Body: str = Form(default=""),
    MessageSid: str = Form(default=""),
):
    sid = (MessageSid or "")[-8:]
    start = time.monotonic()
    logger.info(
        "inbound_sms_received",
        extra={
            "from_suffix": (From or "")[-4:],
            "sid_suffix": sid,
            "body_chars": len(Body or ""),
        },
    )
    live_db = _init_db_if_needed()
    if live_db is None:
        logger.error(
            "inbound_sms_db_unavailable",
            extra={"from_suffix": (From or "")[-4:], "sid_suffix": sid, "db_init_error": db_init_error},
        )
        return Response(
            content=_twiml_message("Service is temporarily unavailable. Please try again shortly."),
            media_type="application/xml",
        )

    try:
        twiml = await handle_inbound_sms(live_db, config, From, Body)
        logger.info(
            "inbound_sms_replied",
            extra={
                "from_suffix": (From or "")[-4:],
                "sid_suffix": sid,
                "elapsed_ms": int((time.monotonic() - start) * 1000),
            },
        )
    except Exception:
        logger.exception("inbound_sms_handler_failed", extra={"from_suffix": (From or "")[-4:], "sid_suffix": sid})
        twiml = _twiml_message("Service is temporarily unavailable. Please try again shortly.")
        logger.info(
            "inbound_sms_fallback_replied",
            extra={
                "from_suffix": (From or "")[-4:],
                "sid_suffix": sid,
                "elapsed_ms": int((time.monotonic() - start) * 1000),
            },
        )
    return Response(content=twiml, media_type="application/xml")
