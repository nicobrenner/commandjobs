import sqlite3

DB_PATH = 'job_listings.db'
OLD_APP_ID = 22   # the application_id you want to change
NEW_APP_ID = 46   # the application_id you want the notes to point to

def reassign_notes(db_path, old_app_id, new_app_id):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1) Update the notes
    cur.execute("""
        UPDATE application_notes
           SET application_id = ?
         WHERE application_id = ?
    """, (new_app_id, old_app_id))
    conn.commit()

    # 2) Fetch and return them to verify
    cur.execute("""
        SELECT note, created_at, application_id
          FROM application_notes
         WHERE application_id = ?
         ORDER BY created_at ASC
    """, (new_app_id,))
    notes = cur.fetchall()
    conn.close()
    return notes

if __name__ == "__main__":
    notes = reassign_notes(DB_PATH, OLD_APP_ID, NEW_APP_ID)
    print(f"Notes now pointing at application_id={NEW_APP_ID}:")
    for note, created_at, app_id in notes:
        print(f"- [{app_id} @ {created_at}] {note}")
