# src/migrations/002_create_application_notes.py

import sqlite3

DB = 'job_listings.db'

def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == column for r in cur.fetchall())

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Ensure applied column exists
    if not column_exists(cur, 'job_listings', 'applied'):
        cur.execute("ALTER TABLE job_listings ADD COLUMN applied INTEGER DEFAULT 0")

    # Create notes table
    cur.execute('''
      CREATE TABLE IF NOT EXISTS application_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        note TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    ''')

    conn.commit()
    conn.close()
    print("✔️  Migration 002 complete")

if __name__ == "__main__":
    main()
