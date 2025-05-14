# src/migrations/005_replace_notes_table.py

import sqlite3
import sys
import os

DB = 'job_listings.db'

def table_exists(cur, name):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def main():
    if not os.path.exists(DB):
        print(f"Error: database file not found at {DB}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    try:
        # only run if _old_notes exists
        if table_exists(cur, '_old_notes'):
            # drop the empty new notes table
            if table_exists(cur, 'application_notes'):
                print("Dropping empty application_notes…")
                cur.execute("DROP TABLE application_notes")

            # rename the old one into place
            print("Renaming _old_notes → application_notes…")
            cur.execute("ALTER TABLE _old_notes RENAME TO application_notes")

            # make sure the schema is what we expect (you can add more PRAGMAs here)
            conn.commit()
            print("✅ Migration 005 complete")
        else:
            print("⚠️  _old_notes not found, skipping migration 005")
    except Exception as e:
        conn.rollback()
        print("❌ Migration 005 failed:", e, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
