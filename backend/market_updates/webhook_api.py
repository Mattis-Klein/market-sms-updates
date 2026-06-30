from __future__ import annotations

import logging

from fastapi import APIRouter, Form, Response

from .allowlist import seed_allowlist
from .config import load_config
from .db import Database
from .keyword_handlers import handle_inbound_sms


router = APIRouter(tags=["market-webhook"])
logger = logging.getLogger(__name__)
config = load_config()
db = Database(config.market_updates_db_path, database_url=config.database_url)
seed_allowlist(db, config.market_updates_allowed_numbers)


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
    try:
        twiml = await handle_inbound_sms(db, config, From, Body)
    except Exception:
        logger.exception("inbound_sms_handler_failed", extra={"from_suffix": (From or "")[-4:], "sid_suffix": sid})
        twiml = _twiml_message("Service is temporarily unavailable. Please try again shortly.")
    return Response(content=twiml, media_type="application/xml")
