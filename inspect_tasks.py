import sqlite3

conn = sqlite3.connect(r'C:\Users\tarun\.gemini\antigravity\scratch\Whatshub\backend\tasks.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
    SELECT id, priority, item_type, title, raw_message, group_name
    FROM tasks
    ORDER BY 
      CASE priority 
        WHEN 'high' THEN 1 
        WHEN 'medium' THEN 2 
        WHEN 'low' THEN 3 
        ELSE 4 
      END ASC,
      created_at DESC
    LIMIT 30
""")

print("--- CURRENT TASKS IN PRIORITY QUEUE ---")
for r in cur.fetchall():
    print(f"[{r['priority'].upper():6}] ({r['item_type']:10}) {r['group_name'][:18]:18} | {r['title'][:40]} | Msg: {r['raw_message'][:50]}")

conn.close()

