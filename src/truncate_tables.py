import sqlite3

# Replace 'job_listings.db' with the correct path to your database file
db_path = 'job_listings.db'

def truncate_tables(database_path):
    # Connect to the SQLite database
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    # SQL commands to truncate tables
    truncate_gpt_interactions = "DELETE FROM gpt_interactions;"
    # truncate_job_listings = "DELETE FROM job_listings;"

    try:
        # Execute the SQL commands
        cursor.execute(truncate_gpt_interactions)
        # cursor.execute(truncate_job_listings)

        # Commit the changes
        conn.commit()
        print("Tables truncated successfully.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        # Close the connection
        conn.close()

# Call the function to truncate tables
truncate_tables(db_path)
