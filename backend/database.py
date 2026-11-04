"""
UNIFIES CROSS-CHAT TASK AGGREGATOR - DATABASE LAYER
Team Hacknova | SQLite Persistence with Priority, Types, and 24h Alerts
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "tasks.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Tasks Table with Priority (High/Med/Low), Item Types, and 1-Day Reminder flag
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        priority TEXT NOT NULL DEFAULT 'medium',
        item_type TEXT NOT NULL DEFAULT 'assignment',
        title TEXT NOT NULL,
        action_item TEXT,
        summary TEXT,
        raw_message TEXT,
        group_name TEXT,
        group_jid TEXT,
        sender TEXT,
        deadline TEXT,
        deadline_display TEXT,
        is_urgent INTEGER DEFAULT 0,
        is_one_day_reminder INTEGER DEFAULT 0,
        confidence TEXT,
        status TEXT DEFAULT 'pending',
        attachment TEXT,
        ai_model TEXT DEFAULT 'Gemma 2B (Ollama Local)',
        created_at TEXT
    )
    """)

    # 2. Group Whitelist Table (Slide 7 Whitelist Filter)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS whitelisted_groups (
        jid TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        icon TEXT DEFAULT '💬',
        is_active INTEGER DEFAULT 1,
        added_at TEXT
    )
    """)

    # 3. Raw Messages Audit Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_jid TEXT,
        sender TEXT,
        content TEXT,
        was_whitelisted INTEGER,
        processed_at TEXT
    )
    """)

    # Seed initial whitelisted groups if empty
    cursor.execute("SELECT COUNT(*) FROM whitelisted_groups")
    if cursor.fetchone()[0] == 0:
        initial_groups = [
            # Seed known groups as disabled; the user must explicitly opt in.
            ("120363028192847@g.us", "College CSE Final Year", "🎓", 0),
            ("120363099991234@g.us", "Team Hacknova Hackathon", "🚀", 0),
            ("120363011122334@g.us", "Apartment Residents Association", "🏢", 0),
            ("120363088877665@g.us", "Family Group", "👨‍👩‍👧", 0),
        ]
        cursor.executemany(
            "INSERT INTO whitelisted_groups (jid, name, icon, is_active, added_at) VALUES (?, ?, ?, ?, datetime('now'))",
            initial_groups
        )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully at: {DB_PATH}")
