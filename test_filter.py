import sqlite3
import re

conn = sqlite3.connect(r'C:\Users\tarun\.gemini\antigravity\scratch\Whatshub\backend\tasks.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id, priority, item_type, title, raw_message, group_name FROM tasks")
all_tasks = [dict(r) for r in cur.fetchall()]
conn.close()

# Let's test actionable task filter
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

def is_actionable(task):
    msg = (task.get("raw_message") or "").strip().lower()
    title = (task.get("title") or "").strip().lower()
    full = msg + " " + title
    
    # 1. Pure links or pure greetings without task
    if any(g in full for g in ["happy birthday", "happy diwali", "deepavali", "birthday wishes", "congratulations"]):
        return False
        
    # 2. Very short casual conversational chit-chat
    cleaned = re.sub(r'[\U00010000-\U0010ffff]', '', msg).strip()
    if len(cleaned) < 5 or CASUAL_NOISE_REGEX.match(cleaned):
        return False
        
    # 3. High or medium priority with meaningful content
    if task.get("priority") in ["high", "medium"]:
        return True
        
    # 4. Contains actionable keywords or specific action items
    if any(k in full for k in ACTIONABLE_KEYWORDS):
        # exclude pure chit-chat containing one casual word if too short
        if len(cleaned) > 10:
            return True
            
    # 5. Has a real deadline
    dl = task.get("deadline_display")
    if dl and dl not in ["In 2 days", "None", "TBD"]:
        return True
        
    return False

actionable = [t for t in all_tasks if is_actionable(t)]
non_actionable = [t for t in all_tasks if not is_actionable(t)]

print(f"Total: {len(all_tasks)} | Actionable tasks: {len(actionable)} | Filtered out as noise: {len(non_actionable)}")
print("\n--- SAMPLE ACTIONABLE TASKS (Kept in Priority Queue) ---")
for t in actionable[:10]:
    print(f"[{t['priority'].upper():6}] {t['group_name'][:18]:18} | {t['raw_message'][:60]}")

print("\n--- SAMPLE FILTERED OUT CHAT (Removed from Priority Queue) ---")
for t in non_actionable[:15]:
    print(f"  Filtered: [{t['priority'].upper():6}] {t['raw_message'][:60]}")

