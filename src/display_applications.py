# src/display_applications.py

import curses
import sqlite3
import textwrap
import json

class ApplicationsDisplay:
    def __init__(self, stdscr, db_path):
        self.stdscr   = stdscr
        self.db_path  = db_path
        self.cursor   = 0
        self.applications = []
        self.notes        = []
        self.job_detail   = None
        self.fetch_apps()

    def fetch_apps(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT jl.id AS job_id,
                   json_extract(gi.answer, '$.company_name') AS company
            FROM gpt_interactions gi
            JOIN job_listings jl ON gi.job_id = jl.id
            WHERE jl.applied = 1
            ORDER BY jl.id DESC
        """)
        self.applications = cur.fetchall()  # [(job_id, company), ...]
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
        self.notes = cur.fetchall()  # [(note, ts), ...]
        conn.close()

    def fetch_job_detail(self, job_id):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT
              json_extract(gi.answer, '$.available_positions'),
              json_extract(gi.answer, '$.small_summary'),
              json_extract(gi.answer, '$.how_to_apply'),
              jl.external_id
            FROM gpt_interactions gi
            JOIN job_listings jl ON gi.job_id = jl.id
            WHERE jl.id = ?
        """, (job_id,))
        row = cur.fetchone()
        conn.close()

        detail = {
            "positions_list": [],
            "Summary": "",
            "How to Apply": "",
            "Listing Link": ""
        }

        if not row:
            return detail

        raw_positions, summary, apply, link = row

        # parse positions JSON into a list of dicts
        try:
            detail["positions_list"] = json.loads(raw_positions) or []
        except Exception:
            detail["positions_list"] = []

        detail["Summary"]      = summary or ""
        detail["How to Apply"] = apply or ""
        detail["Listing Link"] = link or ""
        return detail

    def add_note(self, job_id):
        curses.echo()
        prompt_row = curses.LINES - 4
        self.stdscr.addstr(prompt_row, 0, "New note: ")
        note = self.stdscr.getstr(prompt_row, len("New note: ")).decode()
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
        prompt_row = curses.LINES - 4
        self.stdscr.addstr(prompt_row, 0,
                           "Finalize reason (Hired/Rejected/Abandoned): ")
        reason = self.stdscr.getstr().decode()
        curses.noecho()
        if reason.strip():
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("INSERT INTO application_notes (job_id, note) VALUES (?, ?)",
                        (job_id, f"FINALIZED: {reason}"))
            conn.commit()
            conn.close()

    def fetch_application_date(self, job_id):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT applied_date
            FROM job_listings
            WHERE id = ?
        """, (job_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] or ""  # will be "" if null

    def draw_board(self):
        import json

        self.fetch_apps()
        while True:
            self.stdscr.clear()
            h, w = self.stdscr.getmaxyx()

            # Pane widths
            left_w  = w // 4
            mid_w   = w // 3
            right_w = w - left_w - mid_w - 4

            # ─── Header row (row 0) ─────────────────────────────────────────
            titles = [
                "Company".center(left_w),
                "Notes".center(mid_w),
                "Details".center(right_w),
            ]
            header_line = "  ".join(titles)
            self.stdscr.attron(curses.color_pair(4))
            self.stdscr.addstr(0, 0, header_line[:w])
            self.stdscr.attroff(curses.color_pair(4))

            base_y = 2  # content starts here

            # ─── Left pane: applications list ──────────────────────────────
            for idx, (job_id, company) in enumerate(self.applications):
                y = base_y + idx
                date = self.fetch_application_date(job_id)
                label = f"  {company} ({date})" if date else f"  {company}"
                attr = curses.A_REVERSE if idx == self.cursor else curses.A_NORMAL
                self.stdscr.addnstr(y, 0, label, left_w - 1, attr)

            # ─── Middle & Right panes (only if there are applications) ─────
            if self.applications:
                job_id, company = self.applications[self.cursor]

                # ─── Notes pane ────────────────────────────────────────────
                self.fetch_notes(job_id)
                if not self.notes:
                    hint = "Press [n] to add a note"
                    self.stdscr.addstr(y, left_w + 2, hint, curses.A_DIM)
                else:
                    for note, ts in self.notes[-(h - base_y - 6):]:
                        line = f"{ts.split(' ')[0]}: {note}"
                        for wrapped in textwrap.wrap(line, mid_w - 2):
                            if y < h - 4:
                                self.stdscr.addstr(y, left_w + 2, wrapped)
                                y += 1

                # ─── Details pane ─────────────────────────────────────────
                detail = self.fetch_job_detail(job_id)
                x0 = left_w + mid_w + 4
                y0 = base_y

                # 1️⃣ Available Positions
                self.stdscr.addstr(y0, x0, "Available Positions:", curses.A_BOLD)
                y0 += 1
                for p in detail["positions_list"]:
                    line = f"{p.get('position','')} —  {p.get('link','')}"
                    for wrapped in textwrap.wrap(line, right_w - 1):
                        if y0 < h - 4:
                            self.stdscr.addstr(y0, x0, wrapped)
                            y0 += 1
                    # y0 += 1
                y0 += 1

                # 2️⃣ Summary
                self.stdscr.addstr(y0, x0, "Summary:", curses.A_BOLD)
                y0 += 1
                for wrapped in textwrap.wrap(detail["Summary"], right_w - 1):
                    if y0 < h - 4:
                        self.stdscr.addstr(y0, x0, wrapped)
                        y0 += 1
                y0 += 1

                # 3️⃣ How to Apply
                self.stdscr.addstr(y0, x0, "How to Apply:", curses.A_BOLD)
                y0 += 1
                for wrapped in textwrap.wrap(detail["How to Apply"], right_w - 1):
                    if y0 < h - 4:
                        self.stdscr.addstr(y0, x0, wrapped)
                        y0 += 1
                y0 += 1

                # ─── Listing Link ─────────────────────────────────────────────
                self.stdscr.addstr(y0, x0, "Listing Link:", curses.A_BOLD)
                y0 += 1
                for wrapped in textwrap.wrap(detail["Listing Link"], right_w - 1):
                    if y0 < h - 4:
                        self.stdscr.addstr(y0, x0, wrapped)
                        y0 += 1
                y0 += 1

                # Help line for this view
                help_txt = "[↑↓] Select  [n] Note  [f] Finalize  [q] Back"
                self.stdscr.attron(curses.color_pair(7))
                self.stdscr.addnstr(h - 2, left_w + 2, help_txt, mid_w - 1)
                self.stdscr.attroff(curses.color_pair(7))

            # ─── Footer on left ───────────────────────────────────────────
            self.stdscr.addstr(h - 2, 0, "[q] Back")

            self.stdscr.refresh()

            # ─── Key handling ────────────────────────────────────────────
            c = self.stdscr.getch()
            if c == curses.KEY_UP and self.cursor > 0:
                self.cursor -= 1
            elif c == curses.KEY_DOWN and self.cursor < len(self.applications) - 1:
                self.cursor += 1
            elif c == ord('n') and self.applications:
                self.add_note(job_id)
            elif c == ord('f') and self.applications:
                self.finalize(job_id)
            elif c in (ord('q'), 27):
                break

