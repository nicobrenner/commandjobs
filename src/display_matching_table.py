import sqlite3
import curses
import textwrap
import logging
import json

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
        '''

    def log(self, message):
        """Log a message for debugging."""
        logging.debug(message)

    def fetch_total_entries(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(f"""
                SELECT COUNT(*) FROM (
                    SELECT gi.job_id
                    FROM gpt_interactions gi
                    JOIN job_listings jl ON gi.job_id = jl.id
                    WHERE {self.good_match_filters}
                )
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
                    jl.original_text
                FROM
                    gpt_interactions gi
                JOIN
                    job_listings jl ON gi.job_id = jl.id
                WHERE
                    {self.good_match_filters}
                ORDER BY jl.id DESC
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
                    jl.original_text
                FROM
                    gpt_interactions gi
                JOIN
                    job_listings jl ON gi.job_id = jl.id
                WHERE
                    {self.good_match_filters}
                ORDER BY jl.id DESC
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
                        positions = json.loads(field)
                        field = ", ".join(pos["position"] for pos in positions)
                    except json.JSONDecodeError:
                        field = "Invalid data"
                
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
            elif key == ord('q'):
                break  # Exit the table view

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

                # Helper function to wrap text within content width and determine text placement
                def wrap_text(text, width):
                    return textwrap.wrap(text, width=width)

                y_offset = 1  # Start from the second row for better visibility
                for idx, detail in enumerate([job[0], job[1], job[4], job[5], job[9]]):
                    header = ["Company", "Position", "Why it's a good fit", "How to Apply", "Job Description"][idx]
                    
                    if header == "Position":
                        try:
                            positions = json.loads(detail)
                            detail = ", ".join(pos["position"] for pos in positions)
                        except json.JSONDecodeError:
                            detail = "Invalid data"

                    # Calculate the position for left-aligned headers within the content area
                    header_lines = wrap_text(header, content_width)
                    detail_lines = wrap_text(detail, content_width)

                    # Header with background
                    self.stdscr.attron(curses.color_pair(4))
                    for line in header_lines:
                        header_start_col = start_col  # Align left within the content width
                        self.stdscr.addstr(y_offset, header_start_col - 2, "  " + line + "          ")
                        y_offset += 1
                    y_offset += 1
                    self.stdscr.attroff(curses.color_pair(4))
                    
                    # Detail text
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
                    ch = self.stdscr.getch()
                    if ch == ord('q'):
                        return  # Quit the detail view
                    elif ch == curses.KEY_LEFT:
                        job_index = (job_index - 1) % self.total_entries  # Move to the previous job or wrap around
                        break  # Break the inner loop to refresh the job detail view with the new index
                    elif ch == curses.KEY_RIGHT:
                        job_index = (job_index + 1) % self.total_entries  # Move to the next job or wrap around
                        break  # Break the inner loop to refresh the job detail view with the new index