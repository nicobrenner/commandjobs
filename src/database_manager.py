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

    def fetch_job_listings(self, listings_per_batch):
        # The LIMIT here is effectively throttling GPT usage
        # every time the AI processing runs,
        # it only checks {listings_per_batch} listings
        # 10 by default
        listings_per_batch = listings_per_batch or 10
        query = f"""
            SELECT jl.id, jl.original_text, jl.original_html
            FROM job_listings jl
            LEFT JOIN gpt_interactions gi ON jl.id = gi.job_id
            WHERE gi.job_id IS NULL LIMIT {listings_per_batch}
        """
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def save_gpt_interaction(self, job_id, prompt, answer):
        self.cursor.execute("INSERT INTO gpt_interactions (job_id, prompt, answer) VALUES (?, ?, ?)", (job_id, prompt, answer))
        self.conn.commit()

    def close(self):
        self.conn.close()
