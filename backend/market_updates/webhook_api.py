from __future__ import annotations

from fastapi import APIRouter, Form, Response

from .allowlist import seed_allowlist
from .config import load_config
from .db import Database
from .keyword_handlers import handle_inbound_sms


router = APIRouter(tags=["market-webhook"])
config = load_config()
db = Database(config.market_updates_db_path)
seed_allowlist(db, config.market_updates_allowed_numbers)


@router.post("/api/market-updates/sms")
async def inbound_sms(
    From: str = Form(default=""),
    Body: str = Form(default=""),
    MessageSid: str = Form(default=""),
):
    _ = MessageSid
    twiml = await handle_inbound_sms(db, config, From, Body)
    return Response(content=twiml, media_type="application/xml")
