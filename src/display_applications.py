import locale
import curses
import base64
import sys
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
        # Pane state
        self.active_pane = 'applications'  # or 'notes'
        self.note_cursor = 0
        # Data
        self.applications = []  # (application_id, job_id, company, applied_date, status)
        self.notes        = []  # (id, note, created_at)
        self.job_detail   = None
        self.show_finalized_only = False

    def fetch_applications(self):
        """
        Load self.applications = [(application_id, job_id, company_name, applied_date, status), ...]
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        base_query = """
            SELECT
                a.id AS application_id,
                a.job_id AS job_id,
                json_extract(gi.answer, '$.company_name') AS company_name,
                a.created_at AS applied_date,
                a.status AS status
            FROM applications AS a
            JOIN gpt_interactions AS gi ON gi.job_id = a.job_id
        """
        if not self.show_finalized_only:
            base_query += " WHERE a.status = 'Open'"
        else:
            base_query += " WHERE a.status <> 'Open'"
        base_query += " ORDER BY a.created_at DESC"
        cur.execute(base_query)
        self.applications = cur.fetchall()
        conn.close()

    def fetch_notes(self, application_id):
        """
        Load self.notes = [(id, note, created_at), ...] for the given application_id.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, note, created_at FROM application_notes WHERE application_id = ? ORDER BY created_at ASC",
            (application_id,)
        )
        self.notes = cur.fetchall()
        conn.close()
        # clamp cursor
        if self.note_cursor >= len(self.notes):
            self.note_cursor = max(0, len(self.notes) - 1)

    def fetch_job_detail(self, job_id):
        """
        Return a dict with positions_list, Summary, How to Apply, and Listing Link.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              json_extract(gi.answer, '$.available_positions'),
              json_extract(gi.answer, '$.small_summary'),
              json_extract(gi.answer, '$.how_to_apply'),
              jl.external_id
            FROM gpt_interactions gi
            JOIN job_listings jl ON gi.job_id = jl.id
            WHERE jl.id = ?
            """, (job_id,)
        )
        row = cur.fetchone()
        conn.close()
        detail = {"positions_list": [], "Summary": "", "How to Apply": "", "Listing Link": ""}
        if not row:
            return detail
        raw_positions, summary, apply, link = row
        try:
            detail["positions_list"] = json.loads(raw_positions) or []
        except Exception:
            detail["positions_list"] = []
        detail["Summary"] = summary or ""
        detail["How to Apply"] = apply or ""
        detail["Listing Link"] = link or ""
        return detail

    def delete_note(self, note_id):
        """
        Prompt for confirmation, delete if confirmed.
        """
        h, w = self.stdscr.getmaxyx()
        prompt = "Delete this note? [y/N]: "
        self.stdscr.attron(curses.color_pair(5))
        self.stdscr.addstr(h - 3, 2, prompt)
        self.stdscr.attroff(curses.color_pair(5))
        self.stdscr.refresh()

        curses.echo()
        choice = self.stdscr.getstr(h - 3, 3 + len(prompt), 1).decode('utf-8').lower()
        curses.noecho()
        # clear prompt line
        self.stdscr.move(h - 3, 0)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()

        if choice == 'y':
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("DELETE FROM application_notes WHERE id = ?", (note_id,))
            conn.commit()
            conn.close()

    def add_note(self, application_id, job_id):
        """
        Multi-line note entry with visible cursor.
        Save with Ctrl-G, cancel with Ctrl-D.
        """
        # show the cursor
        curses.curs_set(1)

        # screen dimensions
        h, w = self.stdscr.getmaxyx()
        box_h = h - 6
        box_w = w - 8
        start_y = 3
        start_x = 4

        # draw border
        win = curses.newwin(box_h, box_w, start_y, start_x)
        win.box()
        win.addstr(0, 2, " Enter note ([Ctrl-G] Save / [Ctrl-D] Cancel) ")
        win.refresh()

        # pad for input (taller than box to allow scrolling)
        pad_h = max(10000, box_h * 20)
        # allow up to 2048 columns before running out of space
        pad_w = max(2048, box_w - 2)
        pad = curses.newpad(pad_h, pad_w)
        pad.scrollok(True)
        pad.idlok(True)

        pad_row = 0
        cur_y, cur_x = 0, 0
        saved = False

        while True:
            # redraw border & title
            win.box()
            win.addstr(0, 2, " Enter note ([Ctrl-G] Save / [Ctrl-D] Cancel) ")
            win.refresh()

            # display the pad window
            pad.refresh(pad_row, 0,
                        start_y + 1, start_x + 1,
                        start_y + box_h - 2, start_x + box_w - 2)

            ch = self.stdscr.getch()
            if ch == 7:            # Ctrl-G = save
                saved = True
                break
            elif ch == 4:          # Ctrl-D = cancel
                saved = False
                break
            elif ch == curses.KEY_UP and pad_row > 0:
                pad_row -= 1
            elif ch == curses.KEY_DOWN and cur_y - pad_row >= box_h - 2:
                pad_row += 1

            elif ch in (curses.KEY_BACKSPACE, 127):
                if cur_x > 0:
                    cur_x -= 1
                    try:
                        pad.delch(cur_y, cur_x)
                    except curses.error:
                        pass
                elif cur_y > 0:
                    # move up one line
                    cur_y -= 1
                    line = pad.instr(cur_y, 0, pad_w).decode('utf-8').rstrip('\x00')
                    cur_x = len(line)

            elif ch in (curses.KEY_ENTER, 10, 13):
                try:
                    pad.addch(cur_y, cur_x, ord('\n'))
                except curses.error:
                    pass
                cur_y += 1
                cur_x = 0

            elif ch == curses.KEY_LEFT and cur_x > 0:
                cur_x -= 1
            elif ch == curses.KEY_RIGHT:
                cur_x += 1

            elif 0 <= ch < 256:
                # any printable character
                try:
                    pad.addch(cur_y, cur_x, ch)
                except curses.error:
                    pass
                cur_x += 1

            # ─── ensure cursor is visible ─────────────────────────────
            # if cur_y is below the bottom of our pad window, scroll down
            if cur_y - pad_row > box_h - 3:
                pad_row = cur_y - (box_h - 3)
            # if cur_y is above the top of our pad window, scroll up
            elif cur_y < pad_row:
                pad_row = cur_y
            # clamp
            pad_row = max(0, min(pad_row, pad_h - (box_h - 2)))

            # reposition the curses cursor onto the pad
            real_y = start_y + 1 + (cur_y - pad_row)
            real_x = start_x + 1 + cur_x
            curses.setsyx(real_y, real_x)
            curses.doupdate()

        # hide the cursor again
        curses.curs_set(0)

        if not saved:
            return  # cancelled

        # extract all lines up to cur_y
        lines = []
        for y in range(cur_y + 1):
            raw = pad.instr(y, 0, pad_w).decode('utf-8').rstrip('\x00')
            lines.append(raw.rstrip())
        note_text = "\n".join(lines).strip()
        if not note_text:
            return  # nothing to save

        # persist to DB
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

    def view_note(self, note_text):
        """
        Display a read-only, scrollable view of a note with wrapping.
        Exit with 'q' or ESC.  Ctrl-K copies full note to clipboard.
        """
        full_text = note_text  # original text for copying

        curses.curs_set(0)
        h, w = self.stdscr.getmaxyx()
        box_h, box_w = h - 6, w - 8
        start_y, start_x = 3, 4

        # outer window
        win = curses.newwin(box_h, box_w, start_y, start_x)
        win.keypad(True)

        # prepare wrapped lines
        pad_w = box_w - 2
        lines = []
        for paragraph in note_text.split('\n'):
            wrapped = textwrap.wrap(paragraph, pad_w)
            lines.extend(wrapped if wrapped else [''])
        pad_h = max(len(lines), box_h - 2)
        pad = curses.newpad(pad_h, pad_w)
        for idx, line in enumerate(lines):
            try:
                pad.addnstr(idx, 0, line, pad_w)
            except curses.error:
                pass

        pad_pos = 0
        title = " View note: [↑↓] Scroll | [q/Esc] Close | [k] Copy to clipboard "

        while True:
            # redraw frame **and** title each time
            win.erase()
            win.box()
            win.addstr(0, 2, title)
            win.refresh()

            # draw pad
            pad.refresh(pad_pos, 0,
                        start_y + 1, start_x + 1,
                        start_y + box_h - 2, start_x + box_w - 2)

            ch = win.getch()
            # debug – show the last key code
            win.refresh()

            if ch in (ord('q'), 27):
                break
            elif ch == curses.KEY_UP and pad_pos > 0:
                pad_pos -= 1
            elif ch == curses.KEY_DOWN and pad_pos < len(lines) - (box_h - 2):
                pad_pos += 1

            elif ch == ord('k'):  # lowercase “k” to copy
                try:
                    # 1) base64-encode the full text
                    b64 = base64.b64encode(full_text.encode('utf-8')).decode('ascii')
                    # 2) build OSC52 sequence (c = clipboard)
                    seq = f"\033]52;c;{b64}\a"

                    # 3) temporarily end curses so we can write raw escapes
                    curses.def_prog_mode()
                    curses.endwin()

                    # 4) send the sequence to the terminal
                    sys.stdout.write(seq)
                    sys.stdout.flush()

                    # 5) resume curses
                    curses.reset_prog_mode()
                    curses.doupdate()
                    curses.curs_set(0)

                    # 6) flash confirmation on the last interior line
                    h, w = self.stdscr.getmaxyx()
                    prompt_row = h - 3
                    msg = "Copied note to clipboard"

                    self.stdscr.attron(curses.color_pair(5))
                    self.stdscr.addstr(prompt_row, 5, msg)
                    self.stdscr.attroff(curses.color_pair(5))
                    self.stdscr.refresh()

                    curses.napms(1000)

                    # clear that prompt line
                    self.stdscr.move(prompt_row, 0)
                    self.stdscr.clrtoeol()
                    self.stdscr.refresh()
                except Exception:
                    # (if something really weird happens)
                    msg = "Copy failed"
                    win.addstr(box_h - 2, 2, msg, curses.A_BOLD)
                    win.refresh()
                    curses.napms(1000)
                    win.addstr(box_h - 2, 2, " " * len(msg))
                    win.refresh()

    # when we break out, draw_board will redraw the main screen

    def finalize(self, application_id, job_id):
        # unchanged
        curses.echo()
        prompt_row = curses.LINES - 4
        self.stdscr.attron(curses.color_pair(5))
        prompt_txt = "  👉  Finalize reason ([h] Hired / [r] Rejected / [a] Abandoned / [k] Keep Open):"
        self.stdscr.addstr(prompt_row, 0, prompt_txt)
        self.stdscr.attroff(curses.color_pair(5))
        choice = self.stdscr.getkey().lower()
        curses.noecho()
        mapping = {'h': 'Hired', 'r': 'Rejected', 'a': 'Abandoned'}
        if choice not in mapping:
            return
        status = mapping[choice]
        now = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        if application_id is not None:
            cur.execute("UPDATE applications SET status=?,updated_at=? WHERE id=?", (status, now, application_id))
        else:
            cur.execute(
                "INSERT INTO applications (job_id,status,created_at,updated_at) VALUES (?,?,?,?)",
                (job_id, status, now, now)
            )
            application_id = cur.lastrowid
        cur.execute(
            "INSERT INTO application_notes (application_id,note) VALUES (?,?)",
            (application_id, f"FINALIZED: {status}")
        )
        conn.commit()
        conn.close()

    def draw_board(self):
        while True:
            self.stdscr.clear()
            h, w = self.stdscr.getmaxyx()
            left_w, mid_w = w // 4, w // 3
            right_w = w - left_w - mid_w - 4
            # Header
            titles = ["Company".center(left_w), "Notes".center(mid_w), "Details".center(right_w)]
            header_line = "  ".join(titles)
            self.stdscr.attron(curses.color_pair(4))
            self.stdscr.addstr(0, 0, header_line[:w])
            self.stdscr.attroff(curses.color_pair(4))
            base_y = 2
            # Load data
            self.fetch_applications()
            # Left pane
            for idx, (app_id, job_id, company, adate, status) in enumerate(self.applications):
                y = base_y + idx
                label = f"  {company} ({adate.split(' ')[0]}) [{status[0]}]  "
                attr = curses.A_REVERSE if self.active_pane == 'applications' and idx == self.cursor else curses.A_NORMAL
                self.stdscr.addnstr(y, 0, label, left_w - 1, attr)
            # Middle pane (Notes)
            if self.applications:
                application_id, job_id, *_ = self.applications[self.cursor]
                self.fetch_notes(application_id)
                note_y = base_y
                for idx, (nid, note, ts) in enumerate(self.notes):
                    display = f"{ts.split(' ')[0]}: {note.replace('\n',' ')[:mid_w-6]}"
                    y = note_y + idx
                    if y < h - 4:
                        attr = curses.A_REVERSE if self.active_pane == 'notes' and idx == self.note_cursor else curses.A_NORMAL
                        self.stdscr.addnstr(y, left_w + 2, display, mid_w - 2, attr)
                hint = "[n] add note"
                if self.active_pane == 'notes':
                    hint += "  [d] delete note  [Enter] view note"
                self.stdscr.addstr(min(h - 5, note_y + len(self.notes) + 1), left_w + 2, hint, curses.A_DIM)
                # Right pane (Details)
                x0, y0 = left_w + mid_w + 4, base_y
                detail = self.fetch_job_detail(job_id)
                # Available Positions
                self.stdscr.addstr(y0, x0, "Available Positions:", curses.A_BOLD)
                y0 += 1
                for p in detail["positions_list"]:
                    for wrapped in textwrap.wrap(f"{p.get('position','')} — {p.get('link','')}", right_w - 1):
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
            # Help line
            help_txt = "[←→ ] Switch pane  [↑↓] Move  [space] Toggle Finalized  [n] Note  [f] Finalize  [q] Back"
            sx = max(0, (w - len(help_txt)) // 2)
            self.stdscr.attron(curses.color_pair(7))
            self.stdscr.addnstr(h - 2, sx, help_txt, len(help_txt))
            self.stdscr.attroff(curses.color_pair(7))
            self.stdscr.refresh()
            # Key handling
            c = self.stdscr.getch()
            # Pane switching
            if c == curses.KEY_RIGHT and self.applications:
                self.active_pane = 'notes' if self.active_pane == 'applications' else 'applications'
            elif c == curses.KEY_LEFT:
                self.active_pane = 'applications'
            # Within applications pane
            elif self.active_pane == 'applications':
                if c == curses.KEY_UP and self.cursor > 0:
                    self.cursor -= 1
                    self.note_cursor = 0
                elif c == curses.KEY_DOWN and self.cursor < len(self.applications) - 1:
                    self.cursor += 1
                    self.note_cursor = 0
                elif c == ord(' '):
                    self.show_finalized_only = not self.show_finalized_only
                    self.cursor = 0
                elif c == ord('n'):
                    self.add_note(*self.applications[self.cursor][:2])
                elif c == ord('f'):
                    self.finalize(*self.applications[self.cursor][:2])
                elif c in (ord('q'), 27):
                    break
            # Within notes pane
            elif self.active_pane == 'notes':
                if c == curses.KEY_UP and self.note_cursor > 0:
                    self.note_cursor -= 1
                elif c == curses.KEY_DOWN and self.note_cursor < len(self.notes) - 1:
                    self.note_cursor += 1
                elif c == ord('d') and self.notes:
                    nid = self.notes[self.note_cursor][0]; self.delete_note(nid)
                elif c in (ord('\n'), curses.KEY_ENTER) and self.notes:
                    note_text = self.notes[self.note_cursor][1]
                    self.view_note(note_text)
                elif c == ord('n'):
                    self.add_note(*self.applications[self.cursor][:2])
                elif c == ord('f'):
                    self.finalize(*self.applications[self.cursor][:2])
                elif c in (ord('q'), 27):
                    self.active_pane = 'applications'
