import os
import sqlite3
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Form, Header, HTTPException
from fastapi.responses import HTMLResponse


DB_PATH = os.getenv("FEEDBACK_PORTAL_DB_PATH", "feedback_service/feedback_portal.sqlite")
PORTAL_PASSWORD = os.getenv("FEEDBACK_PORTAL_PASSWORD", "change-me")
INGEST_TOKEN = os.getenv("FEEDBACK_PORTAL_INGEST_TOKEN", "")

app = FastAPI(title="Feedback Portal")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT,
            message TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


def add_entry(phone_number: str, message: str, source: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO entries (phone_number, message, source, created_at) VALUES (?, ?, ?, ?)",
        (phone_number, message, source, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_entries(limit: int = 200):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM entries ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows


def require_password(password: str = Form(default="")):
    if password != PORTAL_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid password")


@app.post("/ingest")
def ingest(
    phone_number: str = Form(default=""),
    message: str = Form(default=""),
    source: str = Form(default="sms"),
    authorization: str = Header(default=""),
):
    if INGEST_TOKEN and authorization != f"Bearer {INGEST_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    add_entry(phone_number, message, source)
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def home():
    html = """
    <html><body style='font-family:sans-serif;max-width:920px;margin:30px auto;'>
    <h1>Feedback Portal</h1>
    <form method='post' action='/view'>
      <input type='password' name='password' placeholder='Portal password' />
      <button type='submit'>View Entries</button>
    </form>
    <hr/>
    <form method='post' action='/manual-add'>
      <input name='password' type='password' placeholder='Portal password' required />
      <input name='phone_number' placeholder='+1877...' />
      <input name='message' placeholder='Feedback message' required />
      <button type='submit'>Add Entry</button>
    </form>
    </body></html>
    """
    return HTMLResponse(html)


@app.post("/view", response_class=HTMLResponse)
def view_entries(password: str = Form(default="")):
    if password != PORTAL_PASSWORD:
        return HTMLResponse("<h2>Invalid password</h2>", status_code=403)
    rows = get_entries()
    list_html = "".join(
        f"<li><b>{r[1] or 'unknown'}</b> [{r[3]}] {r[2]} <small>{r[4]}</small></li>" for r in rows
    )
    return HTMLResponse(f"<h1>Entries</h1><ul>{list_html}</ul><a href='/'>Back</a>")


@app.post("/manual-add")
def manual_add(
    password: str = Form(default=""),
    phone_number: str = Form(default=""),
    message: str = Form(default=""),
):
    if password != PORTAL_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid password")
    add_entry(phone_number, message, "manual")
    return {"ok": True}
