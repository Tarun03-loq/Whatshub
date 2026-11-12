import sqlite3, os, uuid, sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))
DB_PATH = os.path.join(BASE_DIR, 'tasks.db')
if not os.path.isfile(DB_PATH):
    print('Database not found')
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Fetch tasks with a deadline
cur.execute('SELECT id, title, summary, deadline, group_jid FROM tasks WHERE deadline IS NOT NULL')
tasks = cur.fetchall()
print(f'Found {len(tasks)} tasks with deadlines')

# Insert calendar events for each task if not already present
inserted = 0
for task in tasks:
    # Check if an event already exists for this task title and start_iso
    cur.execute('SELECT 1 FROM calendar_events WHERE title = ? AND start_iso = ?', (task['title'], task['deadline']))
    if cur.fetchone():
        continue
    event_id = f"event-{uuid.uuid4().hex[:8]}"
    cur.execute('''
        INSERT INTO calendar_events (id, title, description, start_iso, end_iso, group_jid)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        event_id,
        task['title'],
        task['summary'] or '',
        task['deadline'],
        None,
        task['group_jid']
    ))
    inserted += 1

conn.commit()
print(f'Inserted {inserted} new calendar events')
conn.close()

