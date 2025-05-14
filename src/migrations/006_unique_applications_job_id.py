# src/migrations/006_unique_applications_job_id.py

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
        cur.executescript("""
PRAGMA foreign_keys = OFF;
BEGIN;

/*
  1) Create a fresh table with the exact same schema as `applications`,
     except named `applications_new`. We explicitly include the `id` column
     so we can re-insert with the same primary keys.
*/
CREATE TABLE IF NOT EXISTS applications_new (
  id         INTEGER PRIMARY KEY,              -- we'll preserve the old PK
  job_id     INTEGER NOT NULL UNIQUE,
  status     TEXT    NOT NULL DEFAULT 'Open',
  created_at TEXT    NOT NULL,
  updated_at TEXT    NOT NULL,
  FOREIGN KEY(job_id) REFERENCES job_listings(id)
);

/*
  2) Copy in exactly one row per job_id, picking the *earliest* created_at.
     By selecting MIN(id) per job_id, we also pick its original PK.
*/
INSERT OR IGNORE INTO applications_new (id, job_id, status, created_at, updated_at)
  SELECT
    id,
    job_id,
    status,
    created_at,
    updated_at
  FROM applications
 WHERE id IN (
   SELECT MIN(id)   -- pick the very first row inserted for each job_id
     FROM applications
    GROUP BY job_id
 );

/*
  3) Drop the old table and swap in the new one
*/
DROP TABLE applications;
ALTER TABLE applications_new RENAME TO applications;

COMMIT;
PRAGMA foreign_keys = ON;
""")
        conn.commit()
        print("✔️  Migration 006 complete: duplicates removed, original IDs preserved")
    except Exception as e:
        conn.rollback()
        print("❌ Migration 006 failed:", e, file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main(DB_PATH)
