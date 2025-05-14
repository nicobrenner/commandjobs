# src/migrations/004_migrate_applications_table.py

import sqlite3
import os
import sys

DB = 'job_listings.db'

def table_exists(cur, name):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def column_list(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]

def main():
    if not os.path.exists(DB):
        print(f"Error: database file not found at {DB}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # If we've already migrated (i.e. new schema is present), skip
    if table_exists(cur, 'applications') and 'application_id' in column_list(cur, 'application_notes'):
        print("✔️  Migration 004 already applied, skipping.")
        return

    try:
        print("Running Migration 004…")
        conn.executescript("""
        PRAGMA foreign_keys = OFF;

        CREATE TABLE IF NOT EXISTS applications (
          id             INTEGER PRIMARY KEY AUTOINCREMENT,
          job_id         INTEGER NOT NULL,
          status         TEXT    NOT NULL DEFAULT 'Open',
          created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
          updated_at     TEXT    NOT NULL DEFAULT (datetime('now')),
          FOREIGN KEY(job_id) REFERENCES job_listings(id)
        );

        INSERT OR IGNORE INTO applications (job_id, status, created_at, updated_at)
        SELECT id, 'Open', applied_date, applied_date
          FROM job_listings
         WHERE applied = 1
           AND applied_date IS NOT NULL;

        ALTER TABLE application_notes RENAME TO _old_notes;

        CREATE TABLE IF NOT EXISTS application_notes (
          id             INTEGER PRIMARY KEY AUTOINCREMENT,
          application_id INTEGER NOT NULL,
          note           TEXT    NOT NULL,
          created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(application_id) REFERENCES applications(id)
        );

        INSERT INTO application_notes (application_id, note, created_at)
        SELECT a.id, n.note, n.created_at
          FROM _old_notes AS n
          JOIN applications AS a
            ON n.job_id = a.job_id;

        DROP TABLE _old_notes;

        PRAGMA foreign_keys = ON;
        """)
        conn.commit()
        print("✅ Migration 004 complete!")
    except Exception as e:
        conn.rollback()
        print("❌ Migration 004 failed:", e, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
