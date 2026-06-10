from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from .allowlist import (
    create_invite_request,
    disable_allowlist_entry,
    list_allowlist,
    list_invite_requests,
    set_invite_request_status,
    upsert_allowlist_entry,
)
from .config import load_config
from .db import Database
from .feedback_store import list_feedback


router = APIRouter(prefix="/api/market-updates/admin", tags=["market-admin"])
config = load_config()
db = Database(config.market_updates_db_path)


class AllowlistRequest(BaseModel):
    phone_number: str
    label: str = ""
    enabled: bool = True


class InviteRequestCreate(BaseModel):
    phone_number: str
    request_text: str = "admin-created"


def require_admin(x_admin_token: str = Header(default="")):
    if x_admin_token != config.admin_token:
        raise HTTPException(status_code=403, detail="Admin role required")


@router.get("/allowlist", dependencies=[Depends(require_admin)])
def get_allowlist():
    return {"items": list_allowlist(db)}


@router.post("/allowlist", dependencies=[Depends(require_admin)])
def upsert_allowlist(payload: AllowlistRequest):
    upsert_allowlist_entry(db, payload.phone_number, payload.label, payload.enabled)
    return {"ok": True}


@router.delete("/allowlist/{phone_number}", dependencies=[Depends(require_admin)])
def delete_allowlist(phone_number: str):
    disable_allowlist_entry(db, phone_number)
    return {"ok": True}


@router.get("/invite-requests", dependencies=[Depends(require_admin)])
def get_invite_requests(status: str | None = Query(default=None)):
    return {"items": list_invite_requests(db, status=status)}


@router.post("/invite-requests", dependencies=[Depends(require_admin)])
def post_invite_request(payload: InviteRequestCreate):
    request_id = create_invite_request(db, payload.phone_number, payload.request_text)
    return {"ok": True, "request_id": request_id}


@router.post("/invite-requests/{request_id}/approve", dependencies=[Depends(require_admin)])
def approve_request(request_id: int):
    ok = set_invite_request_status(db, request_id, "approved")
    if not ok:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"ok": True}


@router.post("/invite-requests/{request_id}/deny", dependencies=[Depends(require_admin)])
def deny_request(request_id: int):
    ok = set_invite_request_status(db, request_id, "denied")
    if not ok:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"ok": True}


@router.get("/feedback", dependencies=[Depends(require_admin)])
def get_feedback(limit: int = Query(default=100)):
    return {"items": list_feedback(db, limit)}
