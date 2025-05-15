# src/migrations/000_create_initial_tables.py

import sqlite3
import os

# two levels up from this file's folder, then job_listings.db:
DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'job_listings.db')
)

def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None

def main():
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1) job_listings
    if not table_exists(cursor, 'job_listings'):
        print("Creating table job_listings…")
        cursor.execute('''
        CREATE TABLE job_listings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            original_text TEXT,
            original_html TEXT,
            source        TEXT,
            external_id   TEXT UNIQUE
        )
        ''')

    # 2) gpt_interactions
    if not table_exists(cursor, 'gpt_interactions'):
        print("Creating table gpt_interactions…")
        cursor.execute('''
        CREATE TABLE gpt_interactions (
            id      INTEGER PRIMARY KEY,
            job_id  INTEGER,
            prompt  TEXT,
            answer  TEXT
        )
        ''')

    conn.commit()
    conn.close()
    print("000_create_initial_tables.py completed.")

if __name__ == "__main__":
    main()
