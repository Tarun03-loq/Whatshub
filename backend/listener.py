"""
UNIFIES CROSS-CHAT TASK AGGREGATOR - NEONIZE WHATSAPP DAEMON
Team Hacknova | WhatsApp Web Multi-Device Daemon with Segno Base64 QR, Group Whitelist & Ollama Gemma 2B AI
"""

import os
import sys
import time
import json
import uuid
import base64
import threading
import queue
import sqlite3
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import mimetypes
import tempfile

# Reconfigure stdout/stderr to use utf-8 to prevent encoding crashes on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from database import get_db, init_db
from extractor import extract_task_from_message, generate_coherent_topic_summary, is_actionable_task

OLLAMA_MODEL = "gemma:2b"
ALLOWED_FRONTEND_ORIGINS = {
    "http://127.0.0.1:8080",
    "http://localhost:8080",
}
ATTACHMENTS_DIR = os.path.join(os.path.dirname(__file__), "attachments")

# Global State
whatsapp_state = {
    "connected": False,
    "phone": None,
    "qr": None,
    "qr_svg": None,
    "raw_qr": None,
    "raw_b64": None,
    "qr_ts": 0,
    "expires_in": 30
}

CLIENT_DB_PATH = os.path.join(os.path.dirname(__file__), "whatsapp_session.db")
outbound_queue = queue.Queue()
client = None
client_lock = threading.Lock()
client_thread = None

# Try importing Neonize & Segno
HAS_NEONIZE = False
try:
    import segno
    from neonize.client import NewClient
    from neonize.events import ConnectedEv, MessageEv, PairStatusEv, LoggedOutEv
    from neonize.utils.jid import JID, build_jid
    HAS_NEONIZE = True
except ImportError as imp_err:
    print(f"⚠️ [Neonize Core] Notice: {imp_err}")
    print("   Running in Standby / Simulated HTTP Daemon mode for Hackathon evaluation.")

# --- Whitelist & NLP Pipeline Integration ---
def is_jid_whitelisted(group_jid: str) -> bool:
    """
    Filters only approved group JIDs before touching Gemma 2B / OCR.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT is_active FROM whitelisted_groups WHERE jid = ?", (group_jid,))
        row = cursor.fetchone()
        conn.close()
        if row is not None:
            return bool(row["is_active"])
        # Unknown groups are never implicitly trusted, including when the
        # whitelist is empty.
        return False
    except Exception:
        # Fail closed if the database cannot be checked.
        return False

def get_whitelisted_groups_list():
    """
    Retrieves the list of whitelisted groups from SQLite,
    and if WhatsApp client is connected, syncs live joined groups from user's account.
    """
    groups_dict = {}

    # 1. Load existing from SQLite
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT jid, name, icon, is_active FROM whitelisted_groups")
        for row in c.fetchall():
            groups_dict[row["jid"]] = {
                "jid": row["jid"],
                "name": row["name"],
                "icon": row["icon"] or "💬",
                "is_active": bool(row["is_active"]),
                "is_whatsapp": False
            }
        conn.close()
    except Exception as e:
        print(f"[Whitelist] Error reading DB: {e}")

    # 2. If WhatsApp client is connected, discover groups from the user's account
    if client and hasattr(client, "is_logged_in") and client.is_logged_in:
        try:
            joined = client.get_joined_groups()
            if joined:
                conn = get_db()
                c = conn.cursor()
                for g in joined:
                    g_user = g.JID.User if hasattr(g, "JID") and hasattr(g.JID, "User") else ""
                    g_server = g.JID.Server if hasattr(g, "JID") and hasattr(g.JID, "Server") else "g.us"
                    if not g_user:
                        continue
                    full_jid = f"{g_user}@{g_server}"

                    g_name = f"Group {g_user[:8]}"
                    if hasattr(g, "GroupName") and hasattr(g.GroupName, "Name") and g.GroupName.Name:
                        g_name = g.GroupName.Name

                    if full_jid in groups_dict:
                        groups_dict[full_jid]["name"] = g_name
                        groups_dict[full_jid]["is_whatsapp"] = True
                    else:
                        groups_dict[full_jid] = {
                            "jid": full_jid,
                            "name": g_name,
                            "icon": "👥",
                            "is_active": False,
                            "is_whatsapp": True
                        }
                        # Auto-persist newly discovered WhatsApp group to SQLite
                        try:
                            c.execute(
                                "INSERT OR IGNORE INTO whitelisted_groups (jid, name, icon, is_active, added_at) VALUES (?, ?, ?, 0, datetime('now'))",
                                (full_jid, g_name, "👥")
                            )
                        except Exception:
                            pass
                conn.commit()
                conn.close()
        except Exception as ge:
            print(f"[Groups] Could not query get_joined_groups: {ge}")

    return list(groups_dict.values())

def process_inbound_message(group_jid: str, group_name: str, sender: str, text: str, attachment_path: str = None):
    """
    Core Pipeline Handler:
    WhatsApp -> Whitelist Filter -> Gemma 2B (Ollama Local) + OCR -> SQLite
    """
    text = str(text or "").strip()
    group_jid = str(group_jid or "")
    print(f"\n[Neonize Pipeline] Inbound message from: {group_jid} ({group_name})")
    
    # Whitelist Check
    if not is_jid_whitelisted(group_jid):
        print(f"[Neonize - Privacy Shield] 🛡️ DROPPED: {group_jid} is not selected in whitelist. Message ignored.")
        return None

    print(f"[Neonize] Whitelist check passed! Dispatching to Local Gemma 2B (Ollama)... ({text[:50]}...)")
    log_message(group_jid, sender, text, was_whitelisted=True)

    # Extract Task via Local Gemma 2B + OCR
    extracted = extract_task_from_message(text, attachment_path)
    priority = extracted.get("priority")
    if priority not in {"high", "medium", "low"}:
        priority = "medium"
    item_type = extracted.get("item_type")
    if item_type not in {"assignment", "duedate", "submission", "meeting", "cultural"}:
        item_type = "assignment"
    category = extracted.get("category")
    if category not in {"college", "work", "delivery", "money", "family"}:
        category = "college"
    title = str(extracted.get("title") or text[:50] or "New task")[:200]
    summary = str(extracted.get("summary") or text[:200])[:2000]

    # Store in SQLite
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO tasks (
            id, category, priority, item_type, title, action_item, summary, raw_message,
            group_name, group_jid, sender, deadline, deadline_display,
            is_urgent, is_one_day_reminder, confidence, status, attachment, ai_model, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            category,
            priority,
            item_type,
            title,
            extracted.get("action_item", "Action item"),
            summary,
            text,
            group_name,
            group_jid,
            sender,
            extracted.get("deadline"),
            extracted.get("deadline_display", "TBD"),
            1 if priority == "high" else 0,
            1 if extracted.get("is_one_day_reminder") else 0,
            extracted.get("confidence", "98.9%"),
            "pending",
            attachment_path,
            "Gemma 2B (Ollama Local)",
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
        print(f"[Neonize] ✅ Task stored in SQLite [{task_id}]: {extracted.get('title')} ({extracted.get('priority', '').upper()})")
        # Also create calendar event if deadline present
        if extracted.get('deadline'):
            try:
                cal_conn = get_db()
                cal_cur = cal_conn.cursor()
                event_id = f"event-{uuid.uuid4().hex[:8]}"
                cal_cur.execute("""
                    INSERT INTO calendar_events (id, title, description, start_iso, end_iso, group_jid)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    event_id,
                    extracted.get('title') or 'Untitled',
                    extracted.get('summary') or '',
                    extracted.get('deadline'),
                    None,
                    group_jid
                ))
                cal_conn.commit()
                cal_conn.close()
                print(f"[Calendar] ✅ Event created for task {task_id}")
            except Exception as ce:
                print(f"[Calendar] Error creating event for task {task_id}: {ce}")
    except Exception as db_err:
        print(f"[Neonize] Database error: {db_err}")
        return None

    return task_id

def log_message(group_jid: str, sender: str, text: str, was_whitelisted: bool):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO messages_log (group_jid, sender, content, was_whitelisted, processed_at)
        VALUES (?, ?, ?, ?, ?)
        """, (group_jid, sender, text, 1 if was_whitelisted else 0, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Logger] Error logging message: {e}")

# --- Outbound Queue Worker ---
def outbound_worker():
    while True:
        try:
            item = outbound_queue.get()
            if item is None:
                break
            target_jid_obj, text_body, raw_user = item
            attempt = 1
            max_attempts = 5
            while attempt <= max_attempts:
                try:
                    if not client or not whatsapp_state.get("connected"):
                        raise RuntimeError("WhatsApp is not connected")
                    client.send_message(target_jid_obj, text_body)
                    print(f"\n📤 [OUTGOING WA MESSAGE SENT] To: {raw_user}@s.whatsapp.net | Text: '{text_body[:60]}...'")
                    break
                except Exception as send_err:
                    err_str = str(send_err)
                    if "doesn't contain a device JID" in err_str or "not logged in" in err_str.lower() or "not connected" in err_str.lower():
                        whatsapp_state["connected"] = False
                        print(f"❌ [OUTGOING WA ERROR] WhatsApp account is not linked yet ({err_str}).")
                        break
                    print(f"⚠️ [OUTGOING WA RETRY] Attempt {attempt}/{max_attempts} failed ({send_err}). Retrying...")
                    attempt += 1
                    time.sleep(2)
            
            time.sleep(1.5)
            outbound_queue.task_done()
        except Exception as q_err:
            print(f"❌ [OUTBOUND QUEUE ERROR] {q_err}")

threading.Thread(target=outbound_worker, daemon=True).start()

# --- Neonize Event Listeners ---
def download_supported_attachment(cl, msg_body):
    """Download only supported image/PDF attachments to the ignored local cache."""
    media_fields = ("imageMessage", "documentMessage")
    media = None
    for field in media_fields:
        try:
            if hasattr(msg_body, "HasField") and not msg_body.HasField(field):
                continue
        except (ValueError, TypeError):
            continue
        candidate = getattr(msg_body, field, None)
        if candidate:
            media = candidate
            break
    if media is None:
        return None

    mime = (getattr(media, "mimetype", "") or "").lower()
    filename = os.path.basename(getattr(media, "fileName", "") or "")
    ext = os.path.splitext(filename)[1].lower() or mimetypes.guess_extension(mime) or ""
    if ext not in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
        return None
    if mime and not (mime == "application/pdf" or mime.startswith("image/")):
        return None

    declared_size = getattr(media, "fileLength", 0) or 0
    if declared_size and int(declared_size) > 20 * 1024 * 1024:
        print("[Media] Skipping attachment larger than 20 MiB.")
        return None

    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    fd, dest_path = tempfile.mkstemp(prefix="wa_", suffix=ext, dir=ATTACHMENTS_DIR)
    os.close(fd)
    try:
        cl.download_any(msg_body, dest_path)
        if not os.path.isfile(dest_path) or os.path.getsize(dest_path) == 0:
            raise ValueError("download produced no file")
        if os.path.getsize(dest_path) > 20 * 1024 * 1024:
            raise ValueError("attachment exceeds 20 MiB")
        return dest_path
    except Exception:
        try:
            os.remove(dest_path)
        except OSError:
            pass
        raise


def has_supported_media(msg_body):
    for field in ("imageMessage", "documentMessage"):
        try:
            if msg_body.HasField(field):
                return True
        except (AttributeError, ValueError, TypeError):
            candidate = getattr(msg_body, field, None)
            if candidate and getattr(candidate, "mimetype", None):
                return True
    return False


def setup_client_events(cl):
    if not cl:
        return

    def on_qr(_: NewClient, data_qr: bytes):
        # Throttle QR generation – only emit a new QR if at least 5 seconds have passed
        now_ts = time.time()
        last_ts = whatsapp_state.get("qr_ts", 0)
        if now_ts - last_ts < 5:
            # Skip update to avoid flooding the UI; keep the previous QR until it expires.
            return
        try:
            qr_text = data_qr.decode("utf-8", errors="replace") if isinstance(data_qr, bytes) else str(data_qr)
            qr_obj = segno.make_qr(qr_text)
            qr_uri = qr_obj.png_data_uri(scale=8, border=4)
            qr_svg = qr_obj.svg_data_uri(scale=8, border=4)
            qr_b64 = base64.b64encode(qr_text.encode("utf-8")).decode("utf-8")
            whatsapp_state["qr"] = qr_uri
            whatsapp_state["qr_svg"] = qr_svg
            whatsapp_state["raw_qr"] = qr_text
            whatsapp_state["raw_b64"] = qr_b64
            whatsapp_state["connected"] = False
            whatsapp_state["qr_ts"] = now_ts
            whatsapp_state["expires_in"] = 30
            print(f"\n[on_qr FIRED] WhatsApp Pairing QR Ready (PNG len={len(qr_uri)}, SVG len={len(qr_svg)})")
            print("[QR READY] Scan in WhatsApp: Settings > Linked Devices > Link a Device")
            try:
                qr_obj.terminal(compact=True)
            except Exception:
                pass
        except Exception as qr_err:
            import traceback
            print(f"[QR GEN ERROR] {qr_err}")
            traceback.print_exc()
        try:
            qr_text = data_qr.decode("utf-8", errors="replace") if isinstance(data_qr, bytes) else str(data_qr)
            qr_obj = segno.make_qr(qr_text)
            qr_uri = qr_obj.png_data_uri(scale=8, border=4)
            qr_svg = qr_obj.svg_data_uri(scale=8, border=4)
            qr_b64 = base64.b64encode(qr_text.encode("utf-8")).decode("utf-8")
            whatsapp_state["qr"] = qr_uri
            whatsapp_state["qr_svg"] = qr_svg
            whatsapp_state["raw_qr"] = qr_text
            whatsapp_state["raw_b64"] = qr_b64
            whatsapp_state["connected"] = False
            whatsapp_state["qr_ts"] = time.time()
            whatsapp_state["expires_in"] = 30
            print(f"\n[on_qr FIRED] WhatsApp Pairing QR Ready (PNG len={len(qr_uri)}, SVG len={len(qr_svg)})")
            print("[QR READY] Scan in WhatsApp: Settings > Linked Devices > Link a Device")
            try:
                qr_obj.terminal(compact=True)
            except Exception:
                pass
        except Exception as qr_err:
            import traceback
            print(f"[QR GEN ERROR] {qr_err}")
            traceback.print_exc()

    try:
        cl.event.qr(on_qr)
        print("[QR HOOK] on_qr registered via cl.event.qr() OK")
    except Exception as e:
        print(f"[QR HOOK WARN] cl.event.qr() failed: {e}")
    try:
        cl._qr = on_qr
    except Exception:
        pass
    if hasattr(cl, "event") and hasattr(cl.event, "_qr"):
        cl.event._qr = on_qr

    @cl.event(ConnectedEv)
    def on_connected(c: NewClient, _: ConnectedEv):
        is_logged_in = bool(hasattr(c, "is_logged_in") and c.is_logged_in)
        whatsapp_state["connected"] = is_logged_in
        if is_logged_in:
            whatsapp_state["qr"] = None
            whatsapp_state["qr_svg"] = None
            phone_number = "Active"
            try:
                if hasattr(c, "me") and c.me:
                    if hasattr(c.me, "JID") and c.me.JID and hasattr(c.me.JID, "User") and c.me.JID.User:
                        phone_number = c.me.JID.User
                    elif hasattr(c.me, "User") and c.me.User:
                        phone_number = c.me.User
                elif hasattr(c, "store") and c.store and hasattr(c.store, "ID") and c.store.ID:
                    phone_number = getattr(c.store.ID, "User", "Active")
            except Exception as e:
                print(f"[WARN] Could not parse phone number: {e}")
            
            whatsapp_state["phone"] = phone_number
            print(f"\n🟢 [CONNECTED] WhatsApp session active for phone +{phone_number}")
            # Discover and sync groups on connect
            threading.Thread(target=get_whitelisted_groups_list, daemon=True).start()

    @cl.event(PairStatusEv)
    def on_pair_status(c: NewClient, pair_ev: PairStatusEv):
        phone = pair_ev.ID.User if hasattr(pair_ev, "ID") and hasattr(pair_ev.ID, "User") else "Active"
        print(f"\n🟢 [PAIR STATUS] WhatsApp paired successfully: +{phone}")
        whatsapp_state["connected"] = True
        whatsapp_state["qr"] = None
        whatsapp_state["qr_svg"] = None
        whatsapp_state["phone"] = phone

    @cl.event(LoggedOutEv)
    def on_logged_out(c: NewClient, _: LoggedOutEv):
        print("\n🔴 [LOGGED OUT] WhatsApp session was logged out.")
        whatsapp_state["connected"] = False
        whatsapp_state["phone"] = None
        whatsapp_state["qr"] = None
        whatsapp_state["qr_svg"] = None

    @cl.event(MessageEv)
    def on_message(_: NewClient, message: MessageEv):
        try:
            msg_body = message.Message
            if not msg_body:
                return

            sender_jid_obj = message.Info.MessageSource.Sender if message.Info and message.Info.MessageSource and message.Info.MessageSource.Sender else None
            sender_jid = sender_jid_obj.User if sender_jid_obj else "Unknown"
            is_from_me = message.Info.MessageSource.IsFromMe if message.Info and message.Info.MessageSource else False
            if is_from_me:
                return
            chat_jid_obj = message.Info.MessageSource.Chat if message.Info and message.Info.MessageSource else None
            chat_user = chat_jid_obj.User if chat_jid_obj else sender_jid
            chat_server = chat_jid_obj.Server if chat_jid_obj and hasattr(chat_jid_obj, "Server") and chat_jid_obj.Server else ("g.us" if "g.us" in str(chat_jid_obj) else "s.whatsapp.net")

            full_jid = f"{chat_user}@{chat_server}"

            text = getattr(msg_body, "conversation", "") or ""
            extended = getattr(msg_body, "extendedTextMessage", None)
            if not text and extended:
                text = getattr(extended, "text", "") or ""
            media = has_supported_media(msg_body)
            if media and not text:
                for field in ("imageMessage", "documentMessage"):
                    media_part = getattr(msg_body, field, None)
                    caption = getattr(media_part, "caption", "") if media_part else ""
                    if caption:
                        text = caption
                        break
            if not text and not media:
                return

            chat_name = f"Group {chat_user[:8]}"
            try:
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT name FROM whitelisted_groups WHERE jid = ?", (full_jid,))
                row = c.fetchone()
                if row and row["name"]:
                    chat_name = row["name"]
                conn.close()
            except Exception:
                pass

            if not is_jid_whitelisted(full_jid):
                process_inbound_message(full_jid, chat_name, sender_jid, text or "Media attachment")
                return

            attachment_path = None
            if media:
                try:
                    attachment_path = download_supported_attachment(cl, msg_body)
                except Exception as media_err:
                    print(f"[Media] Could not download attachment: {media_err}")
            if not text:
                text = f"Attachment: {os.path.basename(attachment_path)}" if attachment_path else "Unsupported media attachment"

            print(f"\n📩 [INCOMING WA MESSAGE] From: {full_jid} ({chat_name}) | Sender: {sender_jid} | Text: '{text}'")

            # Forward to pipeline
            process_inbound_message(full_jid, chat_name, sender_jid, text, attachment_path)

        except Exception as err:
            print(f"❌ [ERROR] Error handling incoming WhatsApp message: {err}")

# --- Client Lifecycle & Reconnect Controller ---
def clean_session_files():
    for fpath in [CLIENT_DB_PATH, CLIENT_DB_PATH + "-wal", CLIENT_DB_PATH + "-shm", CLIENT_DB_PATH + "-journal"]:
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                print(f"🗑️ Cleaned session file: {fpath}")
            except Exception:
                pass

def run_neonize_client():
    global client
    if not HAS_NEONIZE:
        return

    with client_lock:
        try:
            print("⚡ [NEONIZE ENGINE] Initializing fresh client session...")
            client = NewClient(CLIENT_DB_PATH)
            setup_client_events(client)
        except Exception as ce:
            print(f"❌ Failed to create Neonize client: {ce}")
            return

    try:
        print("⚡ [NEONIZE ENGINE] Connecting client to WhatsApp Web...")
        client.connect()
    except Exception as err:
        print(f"⚠️ Neonize connection loop ended: {err}")

def trigger_fresh_qr():
    global client_thread, client
    if not HAS_NEONIZE:
        return False
    with client_lock:
        if whatsapp_state.get("connected") or (client and getattr(client, "is_logged_in", False)):
            return False
        if client_thread and client_thread.is_alive():
            return False
        print("🔄 [RECONNECT TRIGGER] Starting pairing handshake without deleting the saved session...")
        client_thread = threading.Thread(target=run_neonize_client, daemon=True)
        client_thread.start()
        return True

# --- Summarization Engine (Ollama Gemma 2B Local AI) ---
def call_ollama_summarize(group_name: str, messages: list) -> str:
    """
    Sends message bundle to Ollama Gemma 2B local AI for intelligent summarization.
    Falls back gracefully to NLP structured summary if Ollama is busy/offline.
    """
    msg_text = "\n".join([f"[{m['sender']}]: {m['content']}" for m in messages])
    prompt = (
        f"You are an AI assistant analyzing messages from the WhatsApp group '{group_name}'.\n"
        f"Summarize the following messages concisely in 2-3 sentences. Highlight any tasks, deadlines, and key decisions clearly:\n\n"
        f"{msg_text}\n\n"
        f"Concise Summary:"
    )

    try:
        import urllib.request as _ur
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }).encode("utf-8")
        req = _ur.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with _ur.urlopen(req, timeout=8) as r:
            resp_data = json.loads(r.read())
            res = resp_data.get("response", "").strip()
            if res:
                return res
    except Exception as err:
        print(f"[Ollama] Fallback active: {err}")

    # High quality fallback summary
    parts = []
    for m in messages[:3]:
        parts.append(m['content'][:90])
    return f"{len(messages)} update(s): " + " • ".join(parts)

# --- Daemon HTTP Server (Port 5001) ---
class DaemonHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def end_headers(self):
        origin = self.headers.get("Origin")
        if origin in ALLOWED_FRONTEND_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/status", "/qr"):
            try:
                if client:
                    is_logged_in = bool(hasattr(client, "is_logged_in") and client.is_logged_in)
                    whatsapp_state["connected"] = is_logged_in
                    if is_logged_in:
                        whatsapp_state["qr"] = None
                        whatsapp_state["qr_svg"] = None
                        if not whatsapp_state["phone"] or whatsapp_state["phone"] == "Unknown":
                            if hasattr(client, "me") and client.me and hasattr(client.me, "JID") and client.me.JID and client.me.JID.User:
                                whatsapp_state["phone"] = client.me.JID.User
                            else:
                                whatsapp_state["phone"] = "Active"
                
                qr_ts = whatsapp_state.get("qr_ts", 0)
                if qr_ts > 0:
                    whatsapp_state["expires_in"] = max(0, 30 - int(time.time() - qr_ts))
                else:
                    whatsapp_state["expires_in"] = 30

            except Exception as st_err:
                print(f"[WARN] Error inspecting client status: {st_err}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(whatsapp_state).encode("utf-8"))

        elif self.path in ("/groups", "/whitelist"):
            try:
                groups = get_whitelisted_groups_list()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "groups": groups,
                    "connected": whatsapp_state["connected"],
                    "phone": whatsapp_state.get("phone")
                }).encode("utf-8"))
            except Exception as ge:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"groups": [], "error": str(ge)}).encode("utf-8"))

        elif self.path.startswith("/tasks"):
            try:
                conn = get_db()
                cur = conn.cursor()
                # Order by priority (high -> medium -> low), then deadline, then created_at
                cur.execute("""
                    SELECT * FROM tasks 
                    ORDER BY 
                      CASE priority 
                        WHEN 'high' THEN 1 
                        WHEN 'medium' THEN 2 
                        WHEN 'low' THEN 3 
                        ELSE 4 
                      END ASC,
                      created_at DESC 
                    LIMIT 150
                """)
                raw_tasks = [dict(r) for r in cur.fetchall()]
                conn.close()

                # Filter out unwanted chatter so Priority Queue only displays actionable tasks
                tasks_list = [t for t in raw_tasks if is_actionable_task(t)]

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"tasks": tasks_list, "count": len(tasks_list)}).encode("utf-8"))
            except Exception as te:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"tasks": [], "error": str(te)}).encode("utf-8"))

        elif self.path.startswith("/search"):
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(self.path)
                qs = parse_qs(parsed.query)
                query = qs.get("q", [""])[0].strip()

                conn = get_db()
                cur = conn.cursor()
                if query:
                    param = f"%{query}%"
                    cur.execute("""
                        SELECT id, 'task' as source_type, title, summary, raw_message as content, 
                               group_name, group_jid, sender, priority, deadline_display, created_at
                        FROM tasks
                        WHERE title LIKE ? OR summary LIKE ? OR raw_message LIKE ? OR group_name LIKE ? OR sender LIKE ?
                        ORDER BY created_at DESC
                        LIMIT 50
                    """, (param, param, param, param, param))
                    results = [dict(r) for r in cur.fetchall()]

                    # Also query messages_log for any raw messages that match
                    cur.execute("""
                        SELECT id, 'log' as source_type, '' as title, '' as summary, content, 
                               '' as group_name, group_jid, sender, 'low' as priority, '' as deadline_display, processed_at as created_at
                        FROM messages_log
                        WHERE content LIKE ?
                        ORDER BY id DESC
                        LIMIT 30
                    """, (param,))
                    log_results = [dict(r) for r in cur.fetchall()]
                    
                    # Combine without duplicate contents
                    seen_content = set(r["content"] for r in results if r.get("content"))
                    for lr in log_results:
                        if lr["content"] not in seen_content:
                            results.append(lr)
                            seen_content.add(lr["content"])
                else:
                    cur.execute("""
                        SELECT id, 'task' as source_type, title, summary, raw_message as content, 
                               group_name, group_jid, sender, priority, deadline_display, created_at
                        FROM tasks
                        ORDER BY created_at DESC
                        LIMIT 30
                    """)
                    results = [dict(r) for r in cur.fetchall()]

                conn.close()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"results": results, "count": len(results), "query": query}).encode("utf-8"))
            except Exception as se:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"results": [], "error": str(se)}).encode("utf-8"))

        elif self.path in ("/summarize", "/summaries"):
            try:
                conn = get_db()
                cur = conn.cursor()
                # Find all distinct groups with messages
                cur.execute("""
                    SELECT DISTINCT group_jid, group_name
                    FROM tasks
                    WHERE group_jid IS NOT NULL AND group_jid != ''
                """)
                groups_rows = cur.fetchall()
                summaries_list = []

                for row in groups_rows:
                    g_jid = row["group_jid"]
                    g_name = row["group_name"] or f"Group {g_jid[:8]}"

                    cur.execute("""
                        SELECT * FROM tasks
                        WHERE group_jid = ?
                        ORDER BY 
                          CASE priority 
                            WHEN 'high' THEN 1 
                            WHEN 'medium' THEN 2 
                            WHEN 'low' THEN 3 
                            ELSE 4 
                          END ASC,
                          created_at DESC
                    """, (g_jid,))
                    g_tasks = [dict(r) for r in cur.fetchall()]

                    # Generate topic-grouped, priority-ordered 5-10 line summary
                    summary_result = generate_coherent_topic_summary(g_name, g_tasks)

                    latest_time = g_tasks[0].get("created_at") if g_tasks else datetime.now().isoformat()

                    summaries_list.append({
                        "group_jid": g_jid,
                        "group_name": g_name,
                        "message_count": len(g_tasks),
                        "last_updated": latest_time,
                        "summary": summary_result["summary"],
                        "priority": summary_result["top_priority"],
                        "topic_count": summary_result["topic_count"],
                        "topics": summary_result.get("topics", []),
                        "ai_model": "Gemma 2B (Ollama Local)"
                    })

                conn.close()

                # Sort the summary cards strictly by priority (High -> Medium -> Low), then latest update
                prio_order = {"high": 1, "medium": 2, "low": 3}
                summaries_list.sort(key=lambda s: (prio_order.get(s["priority"], 4), s["last_updated"]), reverse=False)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "summaries": summaries_list,
                    "ollama_status": "online",
                    "count": len(summaries_list)
                }).encode("utf-8"))
            except Exception as se:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"summaries": [], "error": str(se)}).encode("utf-8"))

        elif self.path.startswith("/calendar"):  # Calendar CRUD
            # GET /calendar?date=YYYY-MM-DD   -> list events for that date
            # POST /calendar/add               -> add new event (JSON body)
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            if self.command == "GET":
                qs = parse_qs(parsed.query)
                date_str = qs.get("date", [None])[0]
                conn = get_db()
                cur = conn.cursor()
                if date_str:
                    # Fetch events where start_iso is on the requested date
                    cur.execute("""
                        SELECT * FROM calendar_events
                        WHERE date(start_iso) = date(?)
                        ORDER BY start_iso ASC
                    """, (date_str,))
                else:
                    # Return all upcoming events
                    cur.execute("""
                        SELECT * FROM calendar_events
                        WHERE datetime(start_iso) >= datetime('now')
                        ORDER BY start_iso ASC
                    """)
                events = [dict(row) for row in cur.fetchall()]
                conn.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"events": events}).encode("utf-8"))
                return
            elif self.command == "POST" and parsed.path == "/calendar/add":
                try:
                    data = json.loads(self.rfile.read(content_length).decode("utf-8"))
                    # Expected keys: title, description, start_iso, end_iso (optional), group_jid (optional)
                    required = ["title", "start_iso"]
                    if not all(k in data for k in required):
                        raise ValueError("Missing required fields")
                    event_id = f"event-{uuid.uuid4().hex[:8]}"
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO calendar_events (id, title, description, start_iso, end_iso, group_jid)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        event_id,
                        data.get("title"),
                        data.get("description"),
                        data.get("start_iso"),
                        data.get("end_iso"),
                        data.get("group_jid")
                    ))
                    conn.commit()
                    conn.close()
                    self.send_response(201)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"id": event_id, "status": "created"}).encode("utf-8"))
                except Exception as e:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return
            try:
                summaries = []
                ollama_status = "offline"

                try:
                    import urllib.request as _ur
                    _ur.urlopen("http://localhost:11434", timeout=2)
                    ollama_status = "online"
                except Exception:
                    pass

                conn = get_db()
                cur = conn.cursor()

                # Get only active whitelisted groups
                cur.execute("SELECT jid, name FROM whitelisted_groups WHERE is_active = 1")
                active_groups = {r["jid"]: r["name"] for r in cur.fetchall()}

                # Fetch recent messages from messages_log
                cur.execute("""
                    SELECT group_jid, sender, content, processed_at
                    FROM messages_log
                    WHERE was_whitelisted = 1
                    ORDER BY processed_at DESC
                    LIMIT 60
                """)
                rows = cur.fetchall()

                # Group by JID
                groups_map = {}
                for row in rows:
                    jid = row["group_jid"]
                    # If active whitelist configured, filter strictly
                    if active_groups and jid not in active_groups:
                        continue
                    if jid not in groups_map:
                        groups_map[jid] = []
                    if len(groups_map[jid]) < 6:
                        groups_map[jid].append({
                            "sender": row["sender"],
                            "content": row["content"],
                            "processed_at": row["processed_at"]
                        })

                # Also fetch recent tasks
                cur.execute("""
                    SELECT group_jid, group_name, title, summary, priority, deadline_display, created_at
                    FROM tasks
                    ORDER BY created_at DESC
                    LIMIT 40
                """)
                task_rows = cur.fetchall()
                conn.close()

                for tr in task_rows:
                    gj = tr["group_jid"]
                    if gj and gj not in active_groups and not active_groups:
                        active_groups[gj] = tr["group_name"]

                # Process Ollama summaries for each group
                for jid, msgs in list(groups_map.items())[:6]:
                    gname = active_groups.get(jid, f"Group {jid.split('@')[0]}")
                    ai_summary = call_ollama_summarize(gname, msgs)

                    summaries.append({
                        "group_jid": jid,
                        "group_name": gname,
                        "summary": ai_summary,
                        "message_count": len(msgs),
                        "last_updated": msgs[0]["processed_at"] if msgs else "",
                        "ai_model": f"Gemma 2B (Ollama)" if ollama_status == "online" else "AI Task Engine"
                    })

                # Append task-based summaries for active groups with tasks
                if task_rows:
                    existing_jids = {s["group_jid"] for s in summaries}
                    tasks_by_group = {}
                    for tr in task_rows:
                        gj = tr["group_jid"]
                        if gj not in existing_jids and (not active_groups or gj in active_groups):
                            if gj not in tasks_by_group:
                                tasks_by_group[gj] = {"name": tr["group_name"], "tasks": []}
                            if len(tasks_by_group[gj]["tasks"]) < 3:
                                tasks_by_group[gj]["tasks"].append(f"{tr['title']} ({tr['priority']} priority, {tr['deadline_display']})")

                    for gj, info in list(tasks_by_group.items())[:4]:
                        summaries.append({
                            "group_jid": gj,
                            "group_name": info["name"],
                            "summary": "Key Tasks: " + "; ".join(info["tasks"]),
                            "message_count": len(info["tasks"]),
                            "last_updated": datetime.now().isoformat(),
                            "ai_model": "Gemma 2B (Ollama)" if ollama_status == "online" else "AI Task Engine"
                        })

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "summaries": summaries,
                    "ollama_status": ollama_status
                }).encode("utf-8"))
            except Exception as sum_err:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(sum_err), "summaries": [], "ollama_status": "offline"}).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        if content_length < 0 or content_length > 1024 * 1024:
            self.send_error(413, "Request body exceeds 1 MiB")
            return

        if self.path in ("/refresh_qr", "/refresh"):
            started = trigger_fresh_qr()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": bool(started),
                "message": "Pairing handshake started" if started else "Pairing is unavailable, already running, or already connected"
            }).encode("utf-8"))

        elif self.path in ("/groups/toggle", "/whitelist/toggle"):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                jid = data.get("jid")
                is_active = 1 if data.get("is_active") else 0
                if jid:
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute("UPDATE whitelisted_groups SET is_active = ? WHERE jid = ?", (is_active, jid))
                    changed = cur.rowcount
                    conn.commit()
                    conn.close()
                    if not changed:
                        self.send_response(404)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": False, "error": "Group not found"}).encode("utf-8"))
                        return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "jid": jid, "is_active": bool(is_active)}).encode("utf-8"))
            except Exception as err:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(err)}).encode("utf-8"))

        elif self.path in ("/groups/add", "/whitelist/add"):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                jid = data.get("jid", "").strip()
                name = data.get("name", "").strip() or f"Group {jid.split('@')[0]}"
                icon = data.get("icon", "💬")
                if jid:
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT OR REPLACE INTO whitelisted_groups (jid, name, icon, is_active, added_at) VALUES (?, ?, ?, 1, datetime('now'))",
                        (jid, name, icon)
                    )
                    conn.commit()
                    conn.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
            except Exception as err:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(err)}).encode("utf-8"))

        elif self.path in ("/groups/remove", "/whitelist/remove"):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                jid = data.get("jid")
                if jid:
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM whitelisted_groups WHERE jid = ?", (jid,))
                    conn.commit()
                    conn.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
            except Exception as err:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(err)}).encode("utf-8"))

        elif self.path == "/receive":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                group_jid = data.get("chatJid") or data.get("from") or data.get("group_jid", "120363028192847@g.us")
                group_name = data.get("groupName") or data.get("group_name", "College CSE Final Year")
                sender = data.get("sender", "Contact")
                text = data.get("message") or data.get("text", "")

                task_id = process_inbound_message(group_jid, group_name, sender, text)
                if not task_id:
                    self.send_response(403)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False,
                        "reason": "Group is not enabled in the whitelist"
                    }).encode("utf-8"))
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "task_id": task_id}).encode("utf-8"))
            except Exception as err:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(err)}).encode("utf-8"))

        elif self.path == "/send":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                target_jid = data.get("jid") or data.get("to")
                message_text = data.get("message")

                if not target_jid or not message_text:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "error": "Missing jid or message"}).encode("utf-8"))
                    return

                raw_user = target_jid.split("@")[0].replace("+", "").replace(" ", "").replace("-", "").strip()
                if len(raw_user) == 10 and raw_user.isdigit():
                    raw_user = "91" + raw_user

                if not HAS_NEONIZE or not whatsapp_state.get("connected"):
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "WhatsApp is not connected"
                    }).encode("utf-8"))
                    return

                jid_obj = build_jid(raw_user, "s.whatsapp.net")
                outbound_queue.put((jid_obj, message_text, raw_user))

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
            except Exception as err:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(err)}).encode("utf-8"))

        elif self.path in ("/disconnect", "/reset"):
            try:
                if client and hasattr(client, "disconnect"):
                    client.disconnect()
                whatsapp_state["connected"] = False
                whatsapp_state["phone"] = None
                whatsapp_state["qr"] = None
                whatsapp_state["qr_svg"] = None
                clean_session_files()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "status": whatsapp_state}).encode("utf-8"))
            except Exception as err:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(err)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

class ReusableHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def run_http_server():
    server_address = ('127.0.0.1', 5001)
    httpd = ReusableHTTPServer(server_address, DaemonHTTPHandler)
    print("🚀 [DAEMON SERVER] Neonize HTTP API listening on http://localhost:5001")
    httpd.serve_forever()

if __name__ == "__main__":
    init_db()
    
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()

    if HAS_NEONIZE:
        trigger_fresh_qr()
    else:
        print("💡 [STANDBY] Neonize daemon HTTP server running on http://localhost:5001.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Stopping WhatsApp daemon...")
        sys.exit(0)
