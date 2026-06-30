from contextlib import asynccontextmanager, suppress
import asyncio
import os

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from market_updates.admin_api import router as admin_router
from market_updates.reminder_worker import run_reminder_worker_forever
from market_updates.webhook_api import config as webhook_config
from market_updates.webhook_api import db as webhook_db
from market_updates.webhook_api import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    worker_task = None
    if os.getenv("REMINDERS_RUN_IN_WEB", "false").lower() == "true":
        worker_task = asyncio.create_task(run_reminder_worker_forever())
    try:
        yield
    finally:
        if worker_task:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task


app = FastAPI(title="Market SMS Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(admin_router)


def _check_database_connectivity() -> tuple[bool, str]:
    try:
        with webhook_db.connect() as conn:
            conn.execute("SELECT 1")
        return True, "ok"
    except Exception as exc:  # pragma: no cover - defensive readiness path
        return False, f"db_error:{type(exc).__name__}"


def build_readiness_report(
    config_override=None,
    db_backend_override: str | None = None,
    db_checker=None,
) -> dict:
    cfg = config_override or webhook_config
    backend = db_backend_override or webhook_db.backend
    checker = db_checker or _check_database_connectivity
    twilio_ready = bool(
        cfg.twilio_account_sid
        and cfg.twilio_auth_token
        and cfg.twilio_from_number
    )
    db_ready, db_detail = checker()
    overall_ready = twilio_ready and db_ready
    return {
        "ok": overall_ready,
        "checks": {
            "twilio_configured": twilio_ready,
            "database_connectivity": db_ready,
        },
        "details": {
            "database_backend": backend,
            "database": db_detail,
        },
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/health/ready")
def health_ready():
    report = build_readiness_report()
    status_code = status.HTTP_200_OK if report["ok"] else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=report)
