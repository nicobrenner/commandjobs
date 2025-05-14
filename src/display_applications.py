# src/display_applications.py

import locale
import curses
import curses.textpad
import sqlite3
import textwrap
import json
import datetime

# make sure we’re in a UTF-8 locale so curses can handle wide chars:
locale.setlocale(locale.LC_ALL, '')

class ApplicationsDisplay:
    def __init__(self, stdscr, db_path):
        self.stdscr   = stdscr
        self.db_path  = db_path
        self.cursor   = 0
        self.applications = []
        self.notes        = []
        self.job_detail   = None
        self.show_finalized_only = False

    def fetch_notes(self, application_id):
        """
        Load self.notes = [(note, created_at), ...] for the given application_id.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("""
            SELECT note, created_at 
            FROM application_notes
            WHERE application_id = ?
            ORDER BY created_at ASC
        """, (application_id,))
        self.notes = cur.fetchall()
        conn.close()

    def fetch_job_detail(self, job_id):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
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

    def add_note(self, application_id, job_id):
        """
        Multi-line note entry with visible cursor.
        Save with Ctrl-G, cancel with Ctrl-D.
        """
        # ─── show cursor ────────────────────────────────────────────
        curses.curs_set(1)

        # ─── compute box dims ───────────────────────────────────────
        h, w = self.stdscr.getmaxyx()
        box_h, box_w = h - 6, w - 8
        start_y, start_x = 3, 4

        # ─── draw outer border & title ─────────────────────────────
        win = curses.newwin(box_h, box_w, start_y, start_x)
        win.keypad(True)
        win.box()
        win.addstr(0, 2, " Enter note (Ctrl-G save   Ctrl-D cancel) ")
        win.refresh()

        # ─── create a pad big enough for huge pastes ───────────────
        pad_h = max(10000, box_h * 20)
        pad_w = box_w - 2
        pad = curses.newpad(pad_h, pad_w)
        pad.scrollok(True)
        pad.idlok(True)
        pad.keypad(True)

        pad_row = 0
        cur_y, cur_x = 0, 0
        saved = False

        # ─── edit loop ─────────────────────────────────────────────
        while True:
            # redraw border & title
            win.box()
            win.addstr(0, 2, " Enter note (Ctrl-G save   Ctrl-D cancel) ")
            win.refresh()

            # show the pad slice
            pad.refresh(
                pad_row, 0,
                start_y + 1, start_x + 1,
                start_y + box_h - 2, start_x + box_w - 2
            )

            # use get_wch to receive wide characters properly:
            try:
                ch = pad.get_wch()
            except curses.error:
                continue

            # Ctrl-G → save, Ctrl-D → cancel
            if ch == '\x07':
                saved = True
                break
            if ch == '\x04':
                saved = False
                break

            # ── printable wide‐char (string) ─────────────────────────
            if isinstance(ch, str):
                if ch == '\n':
                    cur_y += 1
                    cur_x = 0
                else:
                    try:
                        pad.addstr(cur_y, cur_x, ch)
                    except curses.error:
                        pass
                    cur_x += 1
            else:
                # it's an integer key‐code: arrows, backspace, etc.
                if ch == curses.KEY_UP and pad_row > 0:
                    pad_row -= 1
                elif ch == curses.KEY_DOWN and cur_y - pad_row >= box_h - 2:
                    pad_row += 1
                elif ch == curses.KEY_LEFT and cur_x > 0:
                    cur_x -= 1
                elif ch == curses.KEY_RIGHT:
                    cur_x += 1
                elif ch in (curses.KEY_BACKSPACE, 127):
                    if cur_x > 0:
                        cur_x -= 1
                        try: pad.delch(cur_y, cur_x)
                        except curses.error: pass
                    elif cur_y > 0:
                        cur_y -= 1
                        line = pad.instr(cur_y, 0, pad_w).decode('utf-8').rstrip('\x00')
                        cur_x = len(line)
                # ignore other int‐codes

            # ─── auto-scroll vertically ───────────────────────────────
            if cur_y - pad_row > box_h - 3:
                pad_row = cur_y - (box_h - 3)
            elif cur_y < pad_row:
                pad_row = cur_y
            pad_row = max(0, min(pad_row, pad_h - (box_h - 2)))

            # ─── move the hardware cursor ─────────────────────────────
            real_y = start_y + 1 + (cur_y - pad_row)
            real_x = start_x + 1 + cur_x
            curses.setsyx(real_y, real_x)
            curses.doupdate()

        # ─── hide cursor & clear any leftover input ────────────────
        curses.curs_set(0)
        # try the built-in flush…
        curses.flushinp()
        # …and as a fallback, nodelay‐drain stdscr
        self.stdscr.nodelay(True)
        while True:
            if self.stdscr.getch() == curses.ERR:
                break
        self.stdscr.nodelay(False)

        if not saved:
            return   # cancelled

        # ─── grab all lines from the pad ───────────────────────────
        lines = []
        for y in range(cur_y + 1):
            raw = pad.instr(y, 0, pad_w).decode('utf-8').rstrip('\x00')
            lines.append(raw.rstrip())
        note_text = "\n".join(lines).strip()
        if not note_text:
            return

        # ─── persist to DB ────────────────────────────────────────
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()

        if application_id is None:
            now = datetime.datetime.utcnow().isoformat()
            cur.execute(
                "INSERT INTO applications (job_id, status, created_at, updated_at) "
                "VALUES (?, 'Open', ?, ?)",
                (job_id, now, now),
            )
            application_id = cur.lastrowid

        cur.execute(
            "INSERT INTO application_notes (application_id, note) VALUES (?, ?)",
            (application_id, note_text)
        )
        conn.commit()
        conn.close()


    def finalize(self, application_id, job_id):
        # 1) prompt
        curses.echo()
        prompt_row = curses.LINES - 4
        self.stdscr.attron(curses.color_pair(5))
        prompt_txt = "  👉  Finalize reason ([h] Hired / [r] Rejected / [a] Abandoned / [k] Keep Open):"
        self.stdscr.addstr(prompt_row, 0, prompt_txt)
        self.stdscr.attroff(curses.color_pair(5))
        self.stdscr.addstr(prompt_row, len(prompt_txt), "  ")
        choice = self.stdscr.getkey().lower()
        curses.noecho()

        # 2) validate
        mapping = {'h': 'Hired', 'r': 'Rejected', 'a': 'Abandoned'}
        # Don't have 'k': 'Keep Open' on purpose so it wont' change the status of the application
        if choice not in mapping:
            # invalid entry, just return without touching the DB
            return

        status = mapping[choice]
        now = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')

        # 3) upsert into applications
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()

        # if they’ve already got an app row, update it; otherwise insert it
        if application_id is not None:
            cur.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, application_id),
            )
        else:
            cur.execute(
                "INSERT INTO applications (job_id, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (job_id, status, now, now),
            )
            application_id = cur.lastrowid

        # 4) insert the finalize note
        cur.execute(
            "INSERT INTO application_notes (application_id, note) VALUES (?, ?)",
            (application_id, f"FINALIZED: {status}")
        )

        conn.commit()
        conn.close()

    def fetch_applications(self):
        """
        Return all user applications, with their status and real company_name.
        If self.show_finalized_only is True, only return non-Open statuses.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()

        base_query = """
            SELECT
                a.id                 AS application_id,
                a.job_id             AS job_id,
                json_extract(gi.answer, '$.company_name') AS company_name,
                a.created_at         AS applied_date,
                a.status             AS status
            FROM applications AS a
            JOIN gpt_interactions AS gi
              ON gi.job_id = a.job_id
        """
        if not self.show_finalized_only:
            base_query += " WHERE a.status = 'Open'"
        else:
            base_query += " WHERE a.status <> 'Open'"

        base_query += " ORDER BY a.created_at DESC"

        cur.execute(base_query)
        rows = cur.fetchall()
        conn.close()
        return rows

    def draw_board(self):
        import json

        while True:
            self.stdscr.clear()
            h, w = self.stdscr.getmaxyx()

            # Pane widths
            left_w  = w // 4
            mid_w   = w // 3
            right_w = w - left_w - mid_w - 4

            # ─── Header row ──────────────────────────────────────────────
            titles = [
                "Company".center(left_w),
                "Notes".center(mid_w),
                "Details".center(right_w),
            ]
            header_line = "  ".join(titles)
            self.stdscr.attron(curses.color_pair(4))
            self.stdscr.addstr(0, 0, header_line[:w])
            self.stdscr.attroff(curses.color_pair(4))

            base_y = 2

            # ─── Left pane: applications list ───────────────────────────
            apps = self.fetch_applications()
            self.applications = apps

            for idx, (application_id, job_id, company, applied_date, status) in enumerate(apps):
                y = base_y + idx
                # show status initial in the label too
                label = f"  {company} ({applied_date.split(' ')[0]}) [{status[0]}]  "
                attr  = curses.A_REVERSE if idx == self.cursor else curses.A_NORMAL
                self.stdscr.addnstr(y, 0, label, left_w - 1, attr)

            # ─── Middle & Right panes ──────────────────────────────────
            if apps:
                application_id, job_id, company, applied_date, status = apps[self.cursor]

                # ─── Notes pane ────────────────────────────────────────────
                y = base_y
                self.fetch_notes(application_id)
                
                # show as many recent notes as will fit vertically
                notes_to_show = self.notes[-(h - base_y - 6):]
                for note, ts in notes_to_show:
                    # build one logical line per note
                    full_line = f"{ts.split(' ')[0]}: {note}"
                    wrapped = textwrap.wrap(full_line, mid_w - 2)

                    # truncate to 2 lines + ellipsis if necessary
                    if len(wrapped) > 2:
                        wrapped = wrapped[:2] + ['…']

                    for line in wrapped:
                        if y < h - 4:
                            self.stdscr.addstr(y, left_w + 2, line)
                            y += 1

                # Display notes hint
                y += 1
                hint = "Press [n] to add a note"
                self.stdscr.addstr(y, left_w + 2, hint, curses.A_DIM)

                # Details pane
                detail = self.fetch_job_detail(job_id)
                x0, y0 = left_w + mid_w + 4, base_y

                # Available Positions
                self.stdscr.addstr(y0, x0, "Available Positions:", curses.A_BOLD)
                y0 += 1
                for p in detail["positions_list"]:
                    line = f"{p.get('position','')} — {p.get('link','')}"
                    for wrapped in textwrap.wrap(line, right_w - 1):
                        if y0 < h - 4:
                            self.stdscr.addstr(y0, x0, wrapped)
                            y0 += 1
                y0 += 1

                # Summary
                self.stdscr.addstr(y0, x0, "Summary:", curses.A_BOLD)
                y0 += 1
                for wrapped in textwrap.wrap(detail["Summary"], right_w - 1):
                    if y0 < h - 4:
                        self.stdscr.addstr(y0, x0, wrapped)
                        y0 += 1
                y0 += 1

                # How to Apply
                self.stdscr.addstr(y0, x0, "How to Apply:", curses.A_BOLD)
                y0 += 1
                for wrapped in textwrap.wrap(detail["How to Apply"], right_w - 1):
                    if y0 < h - 4:
                        self.stdscr.addstr(y0, x0, wrapped)
                        y0 += 1
                y0 += 1

                # Listing Link
                self.stdscr.addstr(y0, x0, "Listing Link:", curses.A_BOLD)
                y0 += 1
                for wrapped in textwrap.wrap(detail["Listing Link"], right_w - 1):
                    if y0 < h - 4:
                        self.stdscr.addstr(y0, x0, wrapped)
                        y0 += 1

            # ─── Help line ───────────────────────────────────────────────
            help_txt = "[↑↓] Select  [space] Toggle Finalized  [n] Note  [f] Finalize  [q] Back"
            # compute centered X position
            start_x = max(0, (w - len(help_txt)) // 2)

            self.stdscr.attron(curses.color_pair(7))
            # draw the entire help text, ensuring enough width
            self.stdscr.addnstr(h - 2, start_x, help_txt, len(help_txt))
            self.stdscr.attroff(curses.color_pair(7))

            self.stdscr.refresh()

            # ─── Key handling ───────────────────────────────────────────
            c = self.stdscr.getch()
            if c == curses.KEY_UP and self.cursor > 0:
                self.cursor -= 1
            elif c == curses.KEY_DOWN and self.cursor < len(self.applications) - 1:
                self.cursor += 1
            elif c == ord(' '):  # Toggle finalized filter
                self.show_finalized_only = not self.show_finalized_only
                self.cursor = 0
            elif c == ord('n') and self.applications:
                self.add_note(application_id, job_id)
            elif c == ord('f') and self.applications:
                self.finalize(application_id, job_id)
            elif c in (ord('q'), 27):
                break


