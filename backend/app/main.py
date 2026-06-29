from contextlib import asynccontextmanager, suppress
import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from market_updates.admin_api import router as admin_router
from market_updates.reminder_worker import run_reminder_worker_forever
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


@app.get("/health")
def health():
    return {"ok": True}
