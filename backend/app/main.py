from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from market_updates.admin_api import router as admin_router
from market_updates.webhook_api import router as webhook_router


app = FastAPI(title="Market SMS Assistant")
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
