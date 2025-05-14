# src/migrations/003_add_applied_date.py
import sqlite3

DB = 'job_listings.db'

def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == column for r in cur.fetchall())

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    if not column_exists(cur, 'job_listings', 'applied_date'):
        print("Adding applied_date column…")
        # store date in ISO YYYY-MM-DD
        cur.execute("ALTER TABLE job_listings ADD COLUMN applied_date TEXT")
    conn.commit()
    conn.close()
    print("✔️  Migration 003 complete")

if __name__ == "__main__":
    main()
