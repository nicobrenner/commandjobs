import sqlite3
import asyncio

class DatabaseManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.initialize_db()

    def initialize_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_text TEXT,
                original_html TEXT,
                source TEXT,
                external_id TEXT UNIQUE
            )
        ''')
        self.conn.commit()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS gpt_interactions (
                id INTEGER PRIMARY KEY,
                job_id INTEGER,
                prompt TEXT,
                answer TEXT
            )
        ''')
        self.conn.commit()

    def fetch_matching_job_listings(self):
        query = """
            SELECT
                gi.job_id,
                json_extract(gi.answer, '$.fit_for_resume') AS fit_for_resume,
                json_extract(gi.answer, '$.company_name') AS company_name,
                json_extract(gi.answer, '$.how_to_apply') AS how_to_apply,
                json_extract(gi.answer, '$.fit_justification') AS fit_justification,
                json_extract(gi.answer, '$.available_positions') AS available_positions,
                json_extract(gi.answer, '$.remote_positions') AS remote_positions,
                json_extract(gi.answer, '$.hiring_in_us') AS hiring_in_us,
                jl.original_text
            FROM
                gpt_interactions gi
            JOIN
                job_listings jl ON gi.job_id = jl.id
            WHERE
                json_valid(gi.answer) = 1
                AND json_extract(gi.answer, '$.fit_for_resume') = 'Yes'
                AND json_extract(gi.answer, '$.remote_positions') = 'Yes'
                AND json_extract(gi.answer, '$.hiring_in_us') <> 'No'
        """
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def fetch_job_listings(self):
        # The LIMIT here is effectively throttling GPT usage
        # every time the AI processing runs,
        # it only checks 5 listings
        query = """
            SELECT jl.id, jl.original_text, jl.original_html
            FROM job_listings jl
            LEFT JOIN gpt_interactions gi ON jl.id = gi.job_id
            WHERE gi.job_id IS NULL LIMIT 5
        """
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def save_gpt_interaction(self, job_id, prompt, answer):
        self.cursor.execute("INSERT INTO gpt_interactions (job_id, prompt, answer) VALUES (?, ?, ?)", (job_id, prompt, answer))
        self.conn.commit()

    def close(self):
        self.conn.close()
