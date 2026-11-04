"""
UNIFIES CROSS-CHAT TASK AGGREGATOR - FASTAPI BACKEND API
Team Hacknova | Gemma 2B (Ollama Local) + Neonize + SQLite Dashboard
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Literal
import urllib.request
import json
import threading
from datetime import datetime, timezone

from database import get_db, init_db
from listener import (
    HAS_NEONIZE,
    process_inbound_message,
    run_http_server,
    trigger_fresh_qr,
    whatsapp_state,
)

app = FastAPI(
    title="UNIFIES Cross-Chat Task Aggregator API",
    description="Team Hacknova - Local Gemma 2B (Ollama) + Neonize WhatsApp Listener",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()
    if not hasattr(app.state, "daemon_thread") or not app.state.daemon_thread.is_alive():
        app.state.daemon_thread = threading.Thread(target=run_http_server, daemon=True)
        app.state.daemon_thread.start()
    if HAS_NEONIZE:
        trigger_fresh_qr()

# --- Request Models ---
class SimulateMessageRequest(BaseModel):
    group_jid: str
    group_name: str
    sender: str
    message: str
    attachment: Optional[str] = None

class WhitelistGroupRequest(BaseModel):
    jid: str
    name: str
    icon: Optional[str] = "💬"

class TaskStatusUpdate(BaseModel):
    status: Literal["pending", "done"]

# --- API Endpoints ---
@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "UNIFIES Aggregator",
        "team": "Hacknova",
        "ai_engine": "Gemma 2B (Ollama Local)",
        "whatsapp_driver": "Neonize Listener",
        "version": "2.0.0"
    }

@app.get("/api/ollama/status")
def get_ollama_status():
    """
    Checks if Ollama local service is running and if Gemma 2B is pulled
    """
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name") for m in data.get("models", [])]
            return {
                "ollama_running": True,
                "models_available": models,
                "gemma_2b_ready": any("gemma" in m for m in models)
            }
    except Exception as e:
        return {
            "ollama_running": False,
            "error": str(e),
            "fallback": "Using local deterministic Gemma 2B rule engine"
        }

@app.get("/api/tasks")
def get_all_tasks(
    category: Optional[str] = None,
    priority: Optional[str] = None,
    item_type: Optional[str] = None,
    group_jid: Optional[str] = None
):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if category and category != "all":
        query += " AND category = ?"
        params.append(category)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if item_type:
        query += " AND item_type = ?"
        params.append(item_type)
    if group_jid:
        query += " AND group_jid = ?"
        params.append(group_jid)

    query += " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, deadline ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/tasks/by-group")
def get_tasks_grouped_by_columns():
    """
    User Requirement: "show them in separate column of the group chat of the software"
    Returns tasks organized under their respective whitelisted group chats.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM whitelisted_groups WHERE is_active = 1 ORDER BY name ASC")
    groups = [dict(g) for g in cursor.fetchall()]

    result = []
    for g in groups:
        cursor.execute("""
        SELECT * FROM tasks 
        WHERE group_jid = ? 
        ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, deadline ASC
        """, (g["jid"],))
        tasks = [dict(t) for t in cursor.fetchall()]
        result.append({
            "group": g,
            "tasks": tasks,
            "count": len(tasks)
        })

    conn.close()
    return result

@app.get("/api/reminders/24h")
def get_advance_reminders():
    """
    User Requirement: "noticfy the deadline a day before the events"
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE is_one_day_reminder = 1 AND status != 'done' ORDER BY deadline ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/simulate-message")
def simulate_whatsapp_message(req: SimulateMessageRequest):
    """
    Simulates inbound message coming through Neonize -> Whitelist -> Gemma 2B (Ollama) -> SQLite
    """
    task_id = process_inbound_message(
        group_jid=req.group_jid,
        group_name=req.group_name,
        sender=req.sender,
        text=req.message,
        attachment_path=req.attachment
    )
    if not task_id:
        return {
            "success": False,
            "reason": "Group JID is not whitelisted. Message dropped for user privacy."
        }
    return {
        "success": True,
        "task_id": task_id,
        "message": "Extracted with Gemma 2B and stored in SQLite."
    }

@app.patch("/api/tasks/{task_id}")
def update_task_status(task_id: str, req: TaskStatusUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (req.status, task_id))
    changed = cursor.rowcount
    conn.commit()
    conn.close()
    if not changed:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task_id": task_id, "new_status": req.status}

@app.get("/api/groups")
def get_whitelisted_groups():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM whitelisted_groups ORDER BY name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/groups")
def add_whitelisted_group(req: WhitelistGroupRequest):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO whitelisted_groups (jid, name, icon, is_active, added_at) VALUES (?, ?, ?, 1, datetime('now'))",
            (req.jid, req.name, req.icon)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    conn.close()
    return {"success": True, "jid": req.jid, "name": req.name}

@app.get("/api/export/ics/{task_id}")
def export_task_as_ics(task_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    conn.close()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task["deadline"]:
        raise HTTPException(status_code=422, detail="Task has no deadline to export")
    try:
        deadline = datetime.fromisoformat(task["deadline"].replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Task deadline is not a valid ISO datetime")

    def ics_escape(value):
        return (
            str(value or "")
            .replace("\\", "\\\\")
            .replace("\r\n", "\\n")
            .replace("\n", "\\n")
            .replace("\r", "\\n")
            .replace(",", "\\,")
            .replace(";", "\\;")
        )

    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dtstart = deadline.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ics_body = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Hacknova//UNIFIES Aggregator//EN
BEGIN:VEVENT
UID:{task['id']}@hacknova.app
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
SUMMARY:[UNIFIES] {ics_escape(task['title'])}
DESCRIPTION:{ics_escape(task['summary'])} (From: {ics_escape(task['group_name'])})\\nPriority: {ics_escape(task['priority']).upper()}\\nType: {ics_escape(task['item_type']).upper()}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""
    ics_body = ics_body.replace("\r\n", "\n").replace("\n", "\r\n")

    return Response(
        content=ics_body,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={task['id']}.ics"}
    )

# --- WhatsApp Device Pairing & Webhook Endpoints ---
@app.get("/api/whatsapp/status")
def get_whatsapp_status():
    return {
        "is_linked": bool(whatsapp_state.get("connected")),
        "phone": whatsapp_state.get("phone"),
        "protocol": "Neonize" if HAS_NEONIZE else "Unavailable",
        "monitored_groups": sum(1 for g in get_whitelisted_groups() if g["is_active"]),
    }

@app.get("/api/whatsapp/qr")
def get_whatsapp_qr():
    """
    Returns the current pairing QR emitted by Neonize, if one is available.
    """
    qr_state = whatsapp_state
    return {
        "status": "connected" if qr_state.get("connected") else ("ready" if qr_state.get("qr") else "waiting"),
        "source": "Neonize" if HAS_NEONIZE else "unavailable",
        "qr": qr_state.get("qr"),
        "qr_svg": qr_state.get("qr_svg"),
        "timestamp": qr_state.get("qr_ts"),
        "expires_in_seconds": qr_state.get("expires_in", 0),
    }

@app.post("/api/whatsapp/qr/refresh")
def refresh_whatsapp_qr():
    """
    Starts a pairing handshake without deleting the saved WhatsApp session.
    """
    started = trigger_fresh_qr()
    return {
        "status": "started" if started else "not_started",
        "message": "Pairing handshake started" if started else "Pairing is unavailable, already running, or already connected",
    }

@app.post("/api/whatsapp/webhook")
def whatsapp_webhook(payload: dict):
    group_jid = payload.get("group_jid", "120363028192847@g.us")
    group_name = payload.get("group_name", "College CSE Final Year")
    sender = payload.get("sender", "WhatsApp Contact")
    text = payload.get("message", payload.get("text", ""))
    attachment = payload.get("attachment")

    task_id = process_inbound_message(
        group_jid=group_jid,
        group_name=group_name,
        sender=sender,
        text=text,
        attachment_path=attachment
    )
    if not task_id:
        return {"status": "dropped", "reason": "JID not whitelisted"}
    return {"status": "success", "task_id": task_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
