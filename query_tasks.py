import sqlite3, json, os, sys

db_path = os.path.join(os.path.dirname(__file__), 'backend', 'tasks.db')
if not os.path.isfile(db_path):
    print('DB not found')
    sys.exit(1)
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT * FROM tasks')
rows = cur.fetchall()
print(json.dumps([dict(row) for row in rows], indent=2))
conn.close()

