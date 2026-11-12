import sqlite3
import re

CASUAL_NOISE_REGEX = re.compile(
    r'^(ok|okay|k|mmm|mmmm|doneee|done|yes|no|yeah|yup|nope|cool|nice|super|seriii|da|paa|deii|wait|hi|hello|hey|gm|gn|good morning|good night|thanks|thank you|tc|\?+|!+|\.+)$',
    re.IGNORECASE
)

ACTIONABLE_KEYWORDS = [
    "submission", "submit", "record", "lab", "assignment", "deadline", "due", "due date",
    "exam", "test", "review", "cap review", "presentation", "ppt", "slides", "topic",
    "meeting", "meet", "audi", "project", "prototype", "round", "register", "registration",
    "fee", "fees", "bill", "payment", "pay", "tneb", "cutoff", "urgent", "mandatory",
    "form", "forms.gle", "fill", "linkedin", "sheet", "spreadsheet", "portal", "upload",
    "attend", "attendance", "hall ticket", "schedule", "timing", "interview"
]

def is_actionable_task(task):
    msg = (task.get("raw_message") or "").strip().lower()
    title = (task.get("title") or "").strip().lower()
    full = msg + " " + title
    
    # 1. Pure greetings or celebration notes (Diwali, Birthday, Congrats) are NOT tasks for Priority Queue
    if any(g in full for g in ["happy birthday", "happy diwali", "deepavali", "birthday wishes", "congratulations", "many more happy returns"]):
        return False
        
    # 2. Filter out pure stickers, attachments names without context, or tiny casual chatter
    cleaned = re.sub(r'[\U00010000-\U0010ffff]', '', msg).strip()
    if len(cleaned) < 5 or CASUAL_NOISE_REGEX.match(cleaned):
        return False
        
    # 3. High or medium priority items with substance
    if task.get("priority") in ["high", "medium"]:
        return True
        
    # 4. Contains actionable keywords
    if any(k in full for k in ACTIONABLE_KEYWORDS):
        if len(cleaned) > 8:
            return True
            
    # 5. Has a real specific deadline (not generic "In 2 days")
    dl = task.get("deadline_display")
    if dl and dl not in ["In 2 days", "None", "TBD"]:
        return True
        
    return False

conn = sqlite3.connect(r"C:\Users\tarun\.gemini\antigravity\scratch\Whatshub\backend\tasks.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT * FROM tasks")
all_tasks = [dict(r) for r in cur.fetchall()]
conn.close()

filtered = [t for t in all_tasks if is_actionable_task(t)]
print(f"Total raw tasks: {len(all_tasks)} -> Actionable Priority Tasks: {len(filtered)}")
for t in filtered:
    print(f"[{t['priority'].upper():6}] ({t['item_type']:10}) {t['group_name'][:18]:18} | {t['raw_message'][:50]}")

