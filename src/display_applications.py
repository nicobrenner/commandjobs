import curses
import sqlite3
import textwrap

class ApplicationsDisplay:
    def __init__(self, stdscr, db_path):
        self.stdscr   = stdscr
        self.db_path  = db_path
        self.cursor   = 0
        self.applications = []
        self.notes        = []
        self.fetch_apps()

    def fetch_apps(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT jl.id AS job_id, json_extract(gi.answer, '$.company_name') AS company
            FROM gpt_interactions gi
            JOIN job_listings jl ON gi.job_id = jl.id
            WHERE jl.applied = 1
            ORDER BY jl.id DESC
        """)
        self.applications = cur.fetchall()  # list of (job_id, company_name)
        conn.close()

    def fetch_notes(self, job_id):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT note, created_at
            FROM application_notes
            WHERE job_id = ?
            ORDER BY created_at
        """, (job_id,))
        self.notes = cur.fetchall()  # list of (note, timestamp)
        conn.close()

    def add_note(self, job_id):
        curses.echo()
        self.stdscr.addstr(curses.LINES - 2, 0, "New note: ")
        note = self.stdscr.getstr(curses.LINES - 2, len("New note: ")).decode()
        curses.noecho()

        if note.strip():
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("INSERT INTO application_notes (job_id, note) VALUES (?, ?)",
                        (job_id, note))
            conn.commit()
            conn.close()

    def finalize(self, job_id):
        curses.echo()
        self.stdscr.addstr(curses.LINES - 2, 0,
                           "Finalize reason (Hired/Rejected/Abandoned): ")
        reason = self.stdscr.getstr().decode()
        curses.noecho()
        # You can either remove it or leave it—here we just append a final note
        if reason.strip():
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("INSERT INTO application_notes (job_id, note) VALUES (?, ?)",
                        (job_id, f"FINALIZED: {reason}"))
            conn.commit()
            conn.close()

    def draw_board(self):
        self.fetch_apps()
        while True:
            self.stdscr.clear()
            h, w = self.stdscr.getmaxyx()
            mid = w // 3

            # 1️⃣ Left pane: application list
            for idx, (job_id, company) in enumerate(self.applications):
                attr = curses.A_REVERSE if idx == self.cursor else curses.A_NORMAL
                self.stdscr.addnstr(idx, 0, f"• {company}", mid - 1, attr)

            # 2️⃣ Right pane: notes for selected
            if self.applications:
                job_id, company = self.applications[self.cursor]
                self.fetch_notes(job_id)

                # Header
                self.stdscr.addstr(0, mid + 2, f"{company} (Applied)", curses.A_BOLD | curses.A_UNDERLINE)
                # Notes
                y = 2
                for note, ts in self.notes[-(h - 6):]:
                    line = f"{ts.split(' ')[0]}: {note}"
                    for wrapped in textwrap.wrap(line, w - mid - 4):
                        if y < h - 4:
                            self.stdscr.addstr(y, mid + 2, wrapped)
                            y += 1

                # Help line
                help_txt = "[↑↓] Select  [n] Note  [f] Finalize  [q] Back"
                self.stdscr.attron(curses.color_pair(7))
                self.stdscr.addstr(h - 2, mid + 2, help_txt[: w - mid - 4])
                self.stdscr.attroff(curses.color_pair(7))

            # 3️⃣ Footer on left (optional)
            footer = "[q] Back"
            self.stdscr.addstr(h - 2, 0, footer)

            self.stdscr.refresh()

            # 4️⃣ Key handling
            c = self.stdscr.getch()
            if c == curses.KEY_UP and self.cursor > 0:
                self.cursor -= 1
            elif c == curses.KEY_DOWN and self.cursor < len(self.applications) - 1:
                self.cursor += 1
            elif c == ord('n') and self.applications:
                self.add_note(self.applications[self.cursor][0])
            elif c == ord('f') and self.applications:
                self.finalize(self.applications[self.cursor][0])
            elif c in (ord('q'), 27):
                break   # back to main menu
