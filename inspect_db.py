import sqlite3
conn = sqlite3.connect(r"C:\Users\tarun\.gemini\antigravity\scratch\Whatshub\backend\tasks.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", c.fetchall())
for tbl in ["tasks", "messages_log", "whitelisted_groups", "calendar_events"]:
    c.execute(f"PRAGMA table_info({tbl})")
    print(f"Columns in {tbl}:", [r[1] for r in c.fetchall()])
conn.close()

