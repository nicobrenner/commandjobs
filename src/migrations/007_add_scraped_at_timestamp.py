# src/migrations/007_add_scraped_at_timestamp.py

import sqlite3
import sys
import os

DB_PATH = 'job_listings.db'

def main(db_path):
    if not os.path.exists(db_path):
        print(f"Error: database file not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        
        # Check if the column already exists
        cur.execute("PRAGMA table_info(job_listings)")
        columns = [column[1] for column in cur.fetchall()]
        
        if 'scraped_at' not in columns:
            # Add the scraped_at column
            cur.execute("ALTER TABLE job_listings ADD COLUMN scraped_at TEXT")
            
            # Set a default timestamp for existing entries (Jan 1 2025)
            default_timestamp = "2025-01-01T00:00:00"
            cur.execute("UPDATE job_listings SET scraped_at = ? WHERE scraped_at IS NULL", (default_timestamp,))
            
            conn.commit()
            print("✔️  Migration 007 complete: added scraped_at timestamp column")
        else:
            print("✔️  Migration 007 already applied, skipping.")
            
    except Exception as e:
        conn.rollback()
        print("❌ Migration 007 failed:", e, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main(DB_PATH)