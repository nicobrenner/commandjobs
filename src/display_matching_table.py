import locale
import sqlite3
import curses
import textwrap
import logging
import json
from datetime import date, datetime
from display_applications import ApplicationsDisplay

locale.setlocale(locale.LC_ALL, '')

class MatchingTableDisplay:
    def __init__(self, stdscr, db_path):
        self.stdscr = stdscr
        self.db_path = db_path
        self.highlighted_row_index = 0
        self.current_page = 1
        self.total_pages = 0
        self.rows_per_page = 3
        logging.basicConfig(filename='matching_table_display.log', level=logging.DEBUG)
        
        self.good_match_filters = '''
            json_valid(gi.answer) = 1
            AND json_extract(gi.answer, '$.fit_for_resume') = 'Yes'
            AND json_extract(gi.answer, '$.remote_positions') = 'Yes'
            AND json_extract(gi.answer, '$.hiring_in_us') <> 'No'
            AND (jl.discarded IS NULL OR jl.discarded = 0)
            AND (jl.applied IS NULL OR jl.applied = 0)
        '''

    def log(self, message):
        """Log a message for debugging."""
        logging.debug(message)
    
    def format_scraped_date(self, scraped_at):
        """Format scraped_at timestamp for display."""
        try:
            if scraped_at:
                # Parse the ISO timestamp and format for display
                dt = datetime.fromisoformat(scraped_at)
                return dt.strftime("%Y-%m-%d")
            return "Unknown"
        except (ValueError, TypeError):
            return "Unknown"

    def fetch_total_entries(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(f"""
                SELECT COUNT(gi.job_id)
                FROM gpt_interactions gi
                JOIN job_listings jl ON gi.job_id = jl.id
                WHERE {self.good_match_filters}
            """)
            total_entries = cur.fetchone()[0]
            conn.close()
            return total_entries
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return 0

    def fetch_job(self, offset=None):
        if offset is None:
            offset = (self.current_page - 1) * self.rows_per_page + self.highlighted_row_index
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            query = f"""
                SELECT
                    json_extract(gi.answer, '$.company_name') AS company_name,
                    json_extract(gi.answer, '$.available_positions') AS available_positions,
                    json_extract(gi.answer, '$.small_summary') AS summary,
                    json_extract(gi.answer, '$.fit_for_resume') AS fit_for_resume,
                    json_extract(gi.answer, '$.fit_justification') AS fit_justification,
                    json_extract(gi.answer, '$.how_to_apply') AS how_to_apply,
                    json_extract(gi.answer, '$.remote_positions') AS remote_positions,
                    json_extract(gi.answer, '$.hiring_in_us') AS hiring_in_us,
                    gi.job_id,
                    jl.original_text,
                    jl.external_id,
                    jl.scraped_at
                FROM
                    gpt_interactions gi
                JOIN
                    job_listings jl ON gi.job_id = jl.id
                WHERE
                    {self.good_match_filters}
                ORDER BY jl.scraped_at DESC, jl.id DESC
                LIMIT 1 OFFSET {offset}
            """
            self.log(f"Executing query: {query}")  # Log the query
            cur.execute(query)
            data = cur.fetchone()
            self.log(f"Fetched {len(data)} rows")  # Log the number of results
            conn.close()
            return data
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return None

    def fetch_data(self, page_num):
        offset = (page_num - 1) * self.rows_per_page
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            query = f"""
                SELECT
                    json_extract(gi.answer, '$.company_name') AS company_name,
                    json_extract(gi.answer, '$.available_positions') AS available_positions,
                    json_extract(gi.answer, '$.small_summary') AS summary,
                    json_extract(gi.answer, '$.fit_for_resume') AS fit_for_resume,
                    json_extract(gi.answer, '$.fit_justification') AS fit_justification,
                    json_extract(gi.answer, '$.how_to_apply') AS how_to_apply,
                    json_extract(gi.answer, '$.remote_positions') AS remote_positions,
                    json_extract(gi.answer, '$.hiring_in_us') AS hiring_in_us,
                    gi.job_id,
                    jl.original_text,
                    jl.scraped_at
                FROM
                    gpt_interactions gi
                JOIN
                    job_listings jl ON gi.job_id = jl.id
                WHERE
                    {self.good_match_filters}
                ORDER BY jl.scraped_at DESC, jl.id DESC
                LIMIT {self.rows_per_page} OFFSET {offset}
            """
            self.log(f"Executing query: {query}")  # Log the query
            cur.execute(query)
            data = cur.fetchall()
            self.log(f"Fetched {len(data)} rows")  # Log the number of results
            conn.close()
            return data
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return None


    def draw_page(self, current_page):
        max_y, max_x = self.stdscr.getmaxyx()
        data = self.fetch_data(page_num=current_page)

        # Adjusted column widths
        column_widths = {
            "Company": 15,
            "Position": 20,  # Assign 1/4 screen width to Position for JSON data
            "Summary": 40,   # Summary could be long, so assign 1/4 screen width
            "Good Fit?": 10,
            "Why?": 30,
            "How to Apply?": 20
        }

        self.stdscr.clear()
        header = "   ".join(title.center(column_widths[title]) for title in column_widths.keys())
        self.stdscr.attron(curses.color_pair(4))
        self.stdscr.addstr(0, 0, header)
        self.stdscr.attroff(curses.color_pair(4))

        y_offset = 2  # Start below the header

        for idx, listing in enumerate(data):
            if idx == self.highlighted_row_index:
                self.stdscr.attron(curses.color_pair(3))

            max_height_wrapped_text = 1
            for i, key in enumerate(column_widths.keys()):
                field = listing[i]
                width = column_widths[key]

                # Parse JSON for the 'Position' column and extract position titles
                if key == "Position":
                    try:
                        positions = json.loads(field) or []
                        # keep only those with a real string for "position"
                        titles = [pos.get("position") for pos in positions
                                if isinstance(pos.get("position"), str)]
                        field = ", ".join(titles) if titles else ""
                    except (json.JSONDecodeError, TypeError):
                        # JSON was bad, or field was None
                        field = "Invalid data"
                
                # For the 'Company' column, add scraped date underneath
                if key == "Company":
                    # listing has scraped_at as the last field (index 10 in fetch_data, index 11 in fetch_job)
                    scraped_at = listing[10] if len(listing) > 10 else None
                    formatted_date = self.format_scraped_date(scraped_at)
                    field = f"{field}\n({formatted_date})"
                
                # This part takes a field content and wraps it in width
                # then it loops through it line by line, and 
                wrapped_text = textwrap.wrap(str(field), width=width)
                for j, line in enumerate(wrapped_text):
                    line_pos = sum(column_widths[title] for title in list(column_widths.keys())[:i]) + i * 3
                    # if line_pos + len(line) < max_x and y_offset + j < max_y:
                    if line_pos + width <= max_x and y_offset + j < max_y - 1:
                        self.stdscr.addstr(y_offset + j, line_pos, line.ljust(width))
                
                if j > max_height_wrapped_text:
                    max_height_wrapped_text = j
                
            y_offset += max_height_wrapped_text + 2

            if y_offset >= max_y - 3:  # Check if we've reached the end of the screen
                break  # Stop drawing if there's no more space on the screen

            if idx == self.highlighted_row_index:
                self.stdscr.attroff(curses.color_pair(3))

        # Pagination info
        pagination_info = f"Page {self.current_page} of {self.total_pages} ({self.total_entries} great matches for your resume 😁)"
        self.stdscr.attron(curses.color_pair(5))
        self.stdscr.addstr(max_y - 2, 0, pagination_info)
        self.stdscr.attroff(curses.color_pair(5))
        # self.stdscr.addstr(max_y - 1, 0, pagination_info.ljust(max_x))  # Clear to the end of line

        # --- new controls hint bar ---
        # --- footer line: pagination + controls ---
        footer_y = max_y - 2

        # 1) Draw pagination (flush-left)
        pagination = f"Page {self.current_page} of {self.total_pages} ({self.total_entries} great matches for your resume 😁)"
        self.stdscr.attron(curses.color_pair(5))
        self.stdscr.addstr(footer_y, 0, pagination.ljust(max_x))
        self.stdscr.attroff(curses.color_pair(5))

        # 2) Prepare controls text
        controls_text = "[↑↓] Move  [←→ ] Page  [Enter] View  [d] Discard  [a] Apply  [q] Back to Menu"

        # 3) Clear the next line so no overlap
        self.stdscr.move(footer_y + 1, 0)
        self.stdscr.clrtoeol()

        # 4) Draw controls (same left alignment)
        self.stdscr.attron(curses.color_pair(7))
        self.stdscr.addstr(footer_y + 1, 0, controls_text[: max_x - 1])
        self.stdscr.attroff(curses.color_pair(7))

        self.stdscr.refresh()


    def draw_table(self):
        self.total_entries = self.fetch_total_entries()
        self.total_pages = (self.total_entries + self.rows_per_page - 1) // self.rows_per_page

        self.draw_page(self.current_page)

        while True:
            key = self.stdscr.getch()
            if key == curses.KEY_DOWN:
                self.highlighted_row_index = min(self.highlighted_row_index + 1, self.rows_per_page - 1)
                self.draw_page(self.current_page)
            elif key == curses.KEY_UP:
                self.highlighted_row_index = max(0, self.highlighted_row_index - 1)
                self.draw_page(self.current_page)
            elif key == curses.KEY_RIGHT:
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    self.highlighted_row_index = 0  # Reset highlighted row for the new page
                    self.draw_page(self.current_page)
            elif key == curses.KEY_LEFT:
                if self.current_page > 1:
                    self.current_page -= 1
                    self.highlighted_row_index = 0  # Reset highlighted row for the new page
                    self.draw_page(self.current_page)
            elif key in [curses.KEY_ENTER, 10, 13]:
                self.show_job_detail(self.highlighted_row_index + (self.current_page - 1) * self.rows_per_page)
                self.draw_page(self.current_page)  # Redraw the table after returning from the detail view
            elif key == ord('d'):
                # Discard current job
                job = self.fetch_job(self.highlighted_row_index + (self.current_page - 1) * self.rows_per_page)
                if job:
                    self.discard_listing(job[8])  # job[8] = job_id
                    self.total_entries = self.fetch_total_entries()
                    self.total_pages = (self.total_entries + self.rows_per_page - 1) // self.rows_per_page
                    # self.highlighted_row_index = 0
                    self.draw_page(self.current_page)
            elif key == ord('q'):
                break  # Exit the table view
            elif key == ord('a'):
                # Apply to current job
                job = self.fetch_job(self.highlighted_row_index + (self.current_page - 1) * self.rows_per_page)
                if job:
                    self.apply_to_listing(job[8])  # job[8] = job_id
                    # Show post-apply dialog
                    choice = self.show_post_apply_dialog()
                    if choice == 'a':
                        # Go to applications view
                        apps = ApplicationsDisplay(self.stdscr, self.db_path)
                        apps.draw_board()
                        return
                    # If 'q', just return to table view
                    self.total_entries = self.fetch_total_entries()
                    self.total_pages = (self.total_entries + self.rows_per_page - 1) // self.rows_per_page
                    # self.highlighted_row_index = 0
                    self.draw_page(self.current_page)

    def discard_listing(self, job_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("UPDATE job_listings SET discarded = 1 WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
            self.log(f"Discarded job {job_id}")
        except Exception as e:
            self.log(f"Error discarding job {job_id}: {e}")

    def apply_to_listing(self, job_id):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL;")
            cur = conn.cursor()

            # 1) mark the listing itself as applied
            today = date.today().isoformat()  # e.g. "2025-05-14"
            cur.execute("""
                UPDATE job_listings
                SET applied = 1,
                    applied_date = ?
                WHERE id = ?
            """, (today, job_id))

            # 2) upsert into applications
            #    - if an application already exists, just refresh its timestamps/status
            #    - otherwise insert a new one
            cur.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if row:
                application_id = row[0]
                cur.execute("""
                    UPDATE applications
                    SET status     = 'Open',
                        created_at = ?,    -- in case you want created_at to match apply date
                        updated_at = ?
                    WHERE id = ?
                """, (today, today, application_id))
            else:
                cur.execute("""
                    INSERT INTO applications (job_id, status, created_at, updated_at)
                        VALUES (?, 'Open', ?, ?)
                """, (job_id, today, today))

            conn.commit()
            conn.close()

            self.log(f"Applied to job {job_id} (and created application record)")
        except Exception as e:
            self.log(f"Error marking job {job_id} as applied: {e}")


    def show_job_detail(self, job_index):
        self.total_entries = self.fetch_total_entries()  # Get total number of entries for cycling

        # Enter a loop to allow cycling through job details
        while True:
            job = self.fetch_job(job_index)  # Fetch job details
            if not job:
                return  # If no job is found, simply return
            if job:
                self.stdscr.clear()

                # Screen dimensions
                max_y, max_x = self.stdscr.getmaxyx()

                # Set maximum content width
                content_width = min(76, max_x)
                start_col = max(0, (max_x - content_width) // 2)  # Calculate start position for centered text

                y_offset = 1  # Start from the second row for better visibility
                for idx, detail in enumerate([job[0], job[1], job[4], job[5], job[9]]):
                    self.log(f'{idx} {detail}')
                    header = ["Company", "Position", "Why it's a good fit", "How to Apply", "Job Description"][idx]
                    
                    if header == "Position":
                        try:
                            # if detail is None or "null", coerce to empty list
                            positions = json.loads(detail) or []
                            # only keep real strings
                            titles = [
                                p.get("position")
                                for p in positions
                                if isinstance(p.get("position"), str)
                            ]
                            detail = ", ".join(titles)
                        except (json.JSONDecodeError, TypeError):
                            # fall back to blank if we can’t parse
                            detail = ""

                    # Calculate the position for left-aligned headers within the content area
                    header_lines = textwrap.wrap(header, content_width)

                    # Header with background
                    self.stdscr.attron(curses.color_pair(4))
                    header_start_col = start_col  # Align left within the content width
                    header_line = f' {header_lines[0]}          '
                    self.stdscr.addstr(y_offset, header_start_col - 2, header_line)
                    header_width = len(header_line)
                    y_offset += 1
                    self.stdscr.attroff(curses.color_pair(4))
                    if header == "Job Description":
                        y_offset -= 1
                        link_text = job[10] if job[10] is not None else ""
                        link_lines = textwrap.wrap(link_text, content_width)
                        for idx, line in enumerate(link_lines):
                            start_on = start_col
                            if idx == 0:
                                start_on += header_width + 1
                            # Underline the text of the link
                            self.stdscr.addstr(y_offset, start_on, line, curses.A_UNDERLINE)
                            y_offset += 1
                    y_offset += 1
                    
                    # Detail text
                    # avoid passing None to wrap()
                    detail_text = detail if detail is not None else ""
                    detail_lines = textwrap.wrap(detail_text, content_width)
                    for line in detail_lines:
                        if y_offset < max_y - 1:  # Check to avoid writing beyond the screen
                            detail_start_col = max(start_col, (max_x - len(line)) // 2)  # Center detail text
                            self.stdscr.addstr(y_offset, detail_start_col, line)
                            y_offset += 1
                    y_offset += 1  # Extra space between sections

                self.stdscr.refresh()
                # Ensure getch() waits for input by disabling nodelay mode
                self.stdscr.nodelay(False)

                while True:
                    # Draw control hints at the bottom center
                    controls = "[← ] Prev  [→ ] Next  [q] Back  [a] Apply"
                    self.stdscr.attron(curses.color_pair(7))
                    self.stdscr.addstr(max_y - 2,
                                    max(0, (max_x - len(controls)) // 2),
                                    controls)
                    self.stdscr.attroff(curses.color_pair(7))
                    self.stdscr.refresh()
                    
                    ch = self.stdscr.getch()
                    if ch == ord('q'):
                        return  # Quit the detail view
                    elif ch == curses.KEY_LEFT:
                        job_index = (job_index - 1) % self.total_entries  # Move to the previous job or wrap around
                        break  # Break the inner loop to refresh the job detail view with the new index
                    elif ch == curses.KEY_RIGHT:
                        job_index = (job_index + 1) % self.total_entries  # Move to the next job or wrap around
                        break  # Break the inner loop to refresh the job detail view with the new index
                    elif ch == ord('a'):
                        # Apply directly from detail view
                        job_id = job[8]  # adjust index if needed
                        self.apply_to_listing(job_id)
                        # Show post-apply dialog
                        choice = self.show_post_apply_dialog()
                        if choice == 'a':
                            # Go to applications view
                            apps = ApplicationsDisplay(self.stdscr, self.db_path)
                            apps.draw_board()
                            return
                        # If 'q', just return to detail view
                        break

    def show_post_apply_dialog(self):
        """
        Display a centered dialog offering [q] Keep browsing or [a] Go to applications.
        Returns 'q' or 'a'.
        """
        max_y, max_x = self.stdscr.getmaxyx()
        text = "[q] Keep browsing  [a] Go to applications?"
        width = len(text) + 4
        height = 3
        start_y = (max_y - height) // 2
        start_x = (max_x - width) // 2

        win = curses.newwin(height, width, start_y, start_x)
        win.box()
        win.attron(curses.color_pair(7))
        win.addstr(1, 2, text)
        win.attroff(curses.color_pair(7))
        win.refresh()

        # Immediately listen for q or a (no Enter required)
        while True:
            ch = win.getch()
            if ch in (ord('q'), ord('a')):
                break

        # Clear dialog and refresh underlying screen
        win.clear()
        self.stdscr.touchwin()
        self.stdscr.refresh()
        return chr(ch)