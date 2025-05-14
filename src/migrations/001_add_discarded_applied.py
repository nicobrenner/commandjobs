# src/migrations/001_add_discarded_applied.py

import sqlite3

DB_PATH = 'job_listings.db'   # <-- adjust if you use a different path

def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(col[1] == column_name for col in cursor.fetchall())

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if not column_exists(cursor, 'job_listings', 'discarded'):
        print("Adding 'discarded' column...")
        cursor.execute("ALTER TABLE job_listings ADD COLUMN discarded INTEGER DEFAULT 0")

    if not column_exists(cursor, 'job_listings', 'applied'):
        print("Adding 'applied' column...")
        cursor.execute("ALTER TABLE job_listings ADD COLUMN applied INTEGER DEFAULT 0")

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    main()
