import locale
import sqlite3
import curses
import textwrap
import logging
import json
from datetime import datetime
from display_applications import ApplicationsDisplay

locale.setlocale(locale.LC_ALL, '')

class AllJobsDisplay:
    def __init__(self, stdscr, db_path):
        self.stdscr = stdscr
        self.db_path = db_path
        self.highlighted_row_index = 0
        self.current_page = 1
        self.total_pages = 0
        self.rows_per_page = 3
        self.search_term = ""
        logging.basicConfig(filename='all_jobs_display.log', level=logging.DEBUG)

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
    
    def get_search_filters(self):
        """Build additional WHERE conditions for search filtering."""
        if not self.search_term:
            return ""
        
        # Search in company name, summary, job description, and available positions
        search_conditions = [
            f"lower(json_extract(gi.answer, '$.company_name')) LIKE '%{self.search_term.lower()}%'",
            f"lower(json_extract(gi.answer, '$.small_summary')) LIKE '%{self.search_term.lower()}%'", 
            f"lower(jl.original_text) LIKE '%{self.search_term.lower()}%'",
            f"lower(json_extract(gi.answer, '$.available_positions')) LIKE '%{self.search_term.lower()}%'"
        ]
        
        return " AND (" + " OR ".join(search_conditions) + ")"
    
    def prompt_search(self):
        """Prompt user for search term and update search filters."""
        max_y, max_x = self.stdscr.getmaxyx()
        
        # Create input window
        input_win = curses.newwin(3, max_x - 4, max_y - 5, 2)
        input_win.box()
        input_win.addstr(1, 2, f"Search (current: '{self.search_term}'): ")
        input_win.refresh()
        
        # Enable echo and get input
        curses.echo()
        curses.curs_set(1)  # Show cursor
        
        # Get user input
        try:
            search_input = input_win.getstr(1, len(f"Search (current: '{self.search_term}'): ") + 2, 50).decode('utf-8')
            self.search_term = search_input.strip()
        except:
            pass  # Handle any input errors
        finally:
            curses.noecho()
            curses.curs_set(0)  # Hide cursor
        
        # Reset pagination
        self.current_page = 1
        self.highlighted_row_index = 0
        
        # Clear the input window
        input_win.clear()
        input_win.refresh()
        del input_win

    def fetch_total_entries(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            search_filters = self.get_search_filters()
            cur.execute(f"""
                SELECT COUNT(gi.job_id)
                FROM gpt_interactions gi
                JOIN job_listings jl ON gi.job_id = jl.id
                WHERE json_valid(gi.answer) = 1
                AND (jl.discarded IS NULL OR jl.discarded = 0)
                AND (jl.applied IS NULL OR jl.applied = 0){search_filters}
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
            search_filters = self.get_search_filters()
            
            query = f"""
                SELECT
                    json_extract(gi.answer, '$.company_name') AS company_name,
                    json_extract(gi.answer, '$.available_positions') AS available_positions,
                    json_extract(gi.answer, '$.small_summary') AS summary,
                    json_extract(gi.answer, '$.fit_for_resume') AS fit_for_resume,
                    json_extract(gi.answer, '$.fit_justification') AS fit_justification,
                    gi.job_id,
                    jl.original_text,
                    jl.external_id,
                    jl.scraped_at
                FROM
                    gpt_interactions gi
                JOIN
                    job_listings jl ON gi.job_id = jl.id
                WHERE
                    json_valid(gi.answer) = 1
                    AND (jl.discarded IS NULL OR jl.discarded = 0)
                    AND (jl.applied IS NULL OR jl.applied = 0){search_filters}
                ORDER BY jl.scraped_at DESC, jl.id DESC
                LIMIT 1 OFFSET {offset}
            """
            
            self.log(f"Executing query: {query}")  # Log the query
            cur.execute(query)
            data = cur.fetchone()
            self.log(f"Fetched 1 row")  # Log the number of results
            conn.close()
            return data
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            return None

    def fetch_data(self, page_num):
        offset = (page_num - 1) * self.rows_per_page
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            search_filters = self.get_search_filters()
            
            query = f"""
                SELECT
                    json_extract(gi.answer, '$.company_name') AS company_name,
                    json_extract(gi.answer, '$.available_positions') AS available_positions,
                    json_extract(gi.answer, '$.small_summary') AS summary,
                    json_extract(gi.answer, '$.fit_for_resume') AS fit_for_resume,
                    json_extract(gi.answer, '$.fit_justification') AS fit_justification,
                    gi.job_id,
                    jl.original_text,
                    jl.external_id,
                    jl.scraped_at
                FROM
                    gpt_interactions gi
                JOIN
                    job_listings jl ON gi.job_id = jl.id
                WHERE
                    json_valid(gi.answer) = 1
                    AND (jl.discarded IS NULL OR jl.discarded = 0)
                    AND (jl.applied IS NULL OR jl.applied = 0){search_filters}
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

        # Column widths for processed jobs
        column_widths = {
            "Company": 15,
            "Position": 25,
            "Summary": 50,
            "Why?": 30   # Fit justification
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
                if key == "Company":
                    field = listing[0]  # company_name from AI analysis
                elif key == "Position":
                    # Parse JSON positions and extract titles
                    try:
                        positions = json.loads(listing[1]) or []
                        titles = [pos.get("position") for pos in positions
                                if isinstance(pos.get("position"), str)]
                        field = ", ".join(titles) if titles else "Various"
                    except (json.JSONDecodeError, TypeError):
                        field = "Various"
                elif key == "Summary":
                    field = listing[2]  # small_summary from AI analysis
                elif key == "Why?":
                    # Show fit status and brief justification
                    fit_status = listing[3] if listing[3] else "Unknown"
                    justification = listing[4] if listing[4] else ""
                    field = f"{fit_status}: {justification[:100]}" if justification else fit_status
                
                width = column_widths[key]
                
                # For the 'Company' column, add scraped date underneath
                if key == "Company":
                    scraped_at = listing[8] if len(listing) > 8 else None
                    formatted_date = self.format_scraped_date(scraped_at)
                    field = f"{field}\n({formatted_date})"
                
                # This part takes a field content and wraps it in width
                wrapped_text = textwrap.wrap(str(field), width=width)
                for j, line in enumerate(wrapped_text):
                    line_pos = sum(column_widths[title] for title in list(column_widths.keys())[:i]) + i * 3
                    if line_pos + width <= max_x and y_offset + j < max_y - 1:
                        self.stdscr.addstr(y_offset + j, line_pos, line.ljust(width))
                
                if j > max_height_wrapped_text:
                    max_height_wrapped_text = j
                
            y_offset += max_height_wrapped_text + 2

            if y_offset >= max_y - 3:  # Check if we've reached the end of the screen
                break  # Stop drawing if there's no more space on the screen

            if idx == self.highlighted_row_index:
                self.stdscr.attroff(curses.color_pair(3))

        # --- footer line: pagination + controls ---
        footer_y = max_y - 2

        # 1) Draw pagination (flush-left)
        search_status = f" (filtered: '{self.search_term}')" if self.search_term else ""
        pagination = f"Page {self.current_page} of {self.total_pages} ({self.total_entries} job listings{search_status} 📋)"
        self.stdscr.attron(curses.color_pair(5))
        self.stdscr.addstr(footer_y, 0, pagination.ljust(max_x))
        self.stdscr.attroff(curses.color_pair(5))

        # 2) Prepare controls text
        controls_text = "[↑↓] Move  [←→ ] Page  [Enter] View  [d] Discard  [a] Apply  [s] Search  [c] Clear  [q] Back"

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
                    self.discard_listing(job[5])  # job[5] = job_id
                    self.total_entries = self.fetch_total_entries()
                    self.total_pages = (self.total_entries + self.rows_per_page - 1) // self.rows_per_page
                    self.draw_page(self.current_page)
            elif key == ord('s'):
                # Search functionality
                self.prompt_search()
                self.total_entries = self.fetch_total_entries()
                self.total_pages = (self.total_entries + self.rows_per_page - 1) // self.rows_per_page
                self.draw_page(self.current_page)
            elif key == ord('c'):
                # Clear search
                if self.search_term:
                    self.search_term = ""
                    self.current_page = 1
                    self.highlighted_row_index = 0
                    self.total_entries = self.fetch_total_entries()
                    self.total_pages = (self.total_entries + self.rows_per_page - 1) // self.rows_per_page
                    self.draw_page(self.current_page)
            elif key == ord('q'):
                break  # Exit the table view
            elif key == ord('a'):
                # Apply to current job
                job = self.fetch_job(self.highlighted_row_index + (self.current_page - 1) * self.rows_per_page)
                if job:
                    self.apply_to_listing(job[5])  # job[5] = job_id
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
            from datetime import date
            today = date.today().isoformat()  # e.g. "2025-05-14"
            cur.execute("""
                UPDATE job_listings
                SET applied = 1,
                    applied_date = ?
                WHERE id = ?
            """, (today, job_id))

            # 2) upsert into applications
            cur.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if row:
                application_id = row[0]
                cur.execute("""
                    UPDATE applications
                    SET status     = 'Open',
                        created_at = ?,
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
                # Show: Company, Position, Summary, Why it's a fit, Job Description, External Link
                company_name = job[0]
                positions_json = job[1]
                try:
                    positions = json.loads(positions_json) or []
                    position_titles = [pos.get("position") for pos in positions if isinstance(pos.get("position"), str)]
                    position_text = ", ".join(position_titles) if position_titles else "Various"
                except (json.JSONDecodeError, TypeError):
                    position_text = "Various"
                
                details = [company_name, position_text, job[2], job[4], job[7], job[6]]  # company, positions, summary, fit_justification, external_id, original_text
                headers = ["Company", "Position", "Summary", "Why it's a good fit", "External Link", "Job Description"]
                
                for idx, detail in enumerate(details):
                    self.log(f'{idx} {detail}')
                    header = headers[idx]

                    # Calculate the position for left-aligned headers within the content area
                    header_lines = textwrap.wrap(header, content_width)

                    # Header with background
                    self.stdscr.attron(curses.color_pair(4))
                    header_start_col = max(0, start_col - 2)  # Ensure we don't go negative
                    header_line = f' {header_lines[0]}          '
                    if y_offset < max_y - 1 and header_start_col + len(header_line) < max_x:
                        self.stdscr.addstr(y_offset, header_start_col, header_line)
                    header_width = len(header_line)
                    y_offset += 1
                    self.stdscr.attroff(curses.color_pair(4))
                    
                    y_offset += 1
                    
                    # Detail text - special handling for job description to prevent overflow
                    detail_text = detail if detail is not None else ""
                    
                    if header == "External Link":
                        # Display external link with underline formatting, consistent with other sections
                        detail_lines = textwrap.wrap(detail_text, content_width)
                        for line in detail_lines:
                            if y_offset < max_y - 3:  # Check to avoid writing beyond the screen
                                detail_start_col = max(start_col, (max_x - len(line)) // 2)  # Center detail text
                                self.stdscr.addstr(y_offset, detail_start_col, line, curses.A_UNDERLINE)
                                y_offset += 1
                            else:
                                break
                    elif header == "Job Description":
                        # Limit job description to prevent screen overflow
                        remaining_lines = max_y - y_offset - 4  # Leave space for controls
                        detail_lines = textwrap.wrap(detail_text, content_width)
                        
                        # Show only as many lines as will fit, with truncation indicator
                        if len(detail_lines) > remaining_lines:
                            display_lines = detail_lines[:remaining_lines-1]
                            display_lines.append("... [See full description on External Link above]")
                        else:
                            display_lines = detail_lines
                            
                        for line in display_lines:
                            if y_offset < max_y - 3:  # Leave more space for controls
                                detail_start_col = max(start_col, (max_x - len(line)) // 2)  # Center detail text
                                self.stdscr.addstr(y_offset, detail_start_col, line)
                                y_offset += 1
                            else:
                                break
                    else:
                        # Normal processing for other sections
                        detail_lines = textwrap.wrap(detail_text, content_width)
                        for line in detail_lines:
                            if y_offset < max_y - 3:  # Check to avoid writing beyond the screen
                                detail_start_col = max(start_col, (max_x - len(line)) // 2)  # Center detail text
                                self.stdscr.addstr(y_offset, detail_start_col, line)
                                y_offset += 1
                            else:
                                break
                    y_offset += 1  # Extra space between sections

                self.stdscr.refresh()
                # Ensure getch() waits for input by disabling nodelay mode
                self.stdscr.nodelay(False)

                while True:
                    # Draw control hints at the bottom center
                    controls = "[← ] Prev  [→ ] Next  [q] Back  [a] Apply"
                    self.stdscr.attron(curses.color_pair(7))
                    control_x = max(0, (max_x - len(controls)) // 2)
                    control_y = max_y - 2
                    if control_y >= 0 and control_x + len(controls) < max_x:
                        self.stdscr.addstr(control_y, control_x, controls)
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
                        job_id = job[5]
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