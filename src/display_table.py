# display_table.py
import sqlite3
import curses
import textwrap

def fetch_data(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT original_text, external_id FROM job_listings LIMIT 5")
        data = cur.fetchall()
        conn.close()
        return data
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        return None

def draw_table(stdscr, db_path):
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Highlight color
    data = fetch_data(db_path)
    max_y, max_x = stdscr.getmaxyx()
    max_table_width = min(120, max_x - 4)  # Adjusted for padding and separators
    text_col_width = 78  # Adjusted for spacing between cells
    source_col_width = 18  # Adjusted for spacing

    if not data:
        stdscr.addstr(0, 0, "No data found or database is missing.")
        stdscr.refresh()
        stdscr.getch()
        return

    highlighted_row_index = 0
    offset = 0

    while True:
        stdscr.clear()
        row_num = 2  # Starting row for data

        for idx, (original_text, source) in enumerate(data[offset:]):
            wrapped_text = textwrap.wrap(original_text[:80], width=text_col_width)
            wrapped_source = textwrap.wrap(source, width=source_col_width)

            row_height = max(len(wrapped_text), len(wrapped_source))
            for i in range(row_height):
                text_line = wrapped_text[i] if i < len(wrapped_text) else ""
                source_line = wrapped_source[i] if i < len(wrapped_source) else ""
                # Construct the line with spacing between cells
                line = f"{text_line.ljust(text_col_width)} | {source_line.ljust(source_col_width)}"

                if idx + offset == highlighted_row_index:
                    stdscr.attron(curses.color_pair(3))
                    stdscr.addstr(row_num, 1, line)  # Adjusted to start from column 1 for padding
                    stdscr.attroff(curses.color_pair(3))
                else:
                    stdscr.addstr(row_num, 1, line)

                row_num += 1

            # Draw a horizontal separator line after each row
            stdscr.addstr(row_num, 1, '-' * (text_col_width + source_col_width + 3))  # '+3' for cell spacing and separator
            row_num += 1  # Increment row_num to account for the separator line

            if row_num >= max_y - 1:
                break

        stdscr.refresh()

        # Key handling for scrolling and quitting
        key = stdscr.getch()
        if key == curses.KEY_DOWN and highlighted_row_index < len(data) - 1:
            highlighted_row_index += 1
            if row_num >= max_y - 1 and offset < len(data) - (max_y - 2):
                offset += 1  # Scroll down
        elif key == curses.KEY_UP and highlighted_row_index > 0:
            highlighted_row_index -= 1
            if highlighted_row_index < offset:
                offset -= 1  # Scroll up
        elif key == ord('q'):
            break  # Quit the table view

