import curses
import textwrap
import os
from hn_scraping import HNScraper
from display_table import draw_table
from database_manager import DatabaseManager
from display_matching_table import MatchingTableDisplay
from gpt_processor import GPTProcessor

import asyncio
import sqlite3
import logging
import threading
from queue import Queue
from dotenv import load_dotenv

class MenuApp:
    def __init__(self, stdscr, logger):
        # Load environment variables
        load_dotenv()
        required_values = (
            "OPENAI_API_KEY",
            "OPENAI_GPT_MODEL",
            "BASE_RESUME_PATH",
            "DB_PATH",
            "HN_START_URL",
        )
        for required_value in required_values:
            if not os.getenv(required_value):
                print(
                    "Failed to initialize the application. The following values are required to be "
                    "set in a .env file:",
                    *required_values,
                    sep="\n",
                )
                print(
                    "If you don't have an OpenAI key, visit openai.com to obtain one."
                )
                print("See README.md for more configuration options.")
                raise ValueError(f"{required_value} is not set; exiting.")

        self.scraping_done_event = threading.Event()  # Event to signal scraping completion
        self.logger = logger
        self.db_path = os.getenv('DB_PATH')
        if self.db_path is None:
            # I don't like raising an exception here, but haven't been able to
            # push out an error message using print() before closing
            # the program with sys.exit(1) (at least with docker, there's no output)
            raise ValueError("DB_PATH variable is not set. Please configure your .env file")
        
        self.db_manager = DatabaseManager(self.db_path)  # Specify the path
        self.gpt_processor = GPTProcessor(self.db_manager, os.getenv('OPENAI_API_KEY'))
        self.resume_path = os.getenv('BASE_RESUME_PATH')
        self.stdscr = stdscr
        self.table_display = MatchingTableDisplay(self.stdscr, self.db_path)
        self.total_ai_job_recommendations = self.table_display.fetch_total_entries()
        self.total_listings = self.get_total_listings()

        resume_menu = "📄 Create resume (just paste it here once)"
        find_best_matches_menu = "🧠 Create your resume"
        resume_str = self.read_resume_from_file()
        if len(resume_str) > 0:
            resume_menu = "📄 Edit resume"
            find_best_matches_menu = "🧠 Find best matches for resume with AI"
        
        db_menu_item = f"💾 Navigate jobs in local db ({self.total_listings} listings)"
        ai_recommendations_menu = "😅 No job matches for your resume yet"
        if self.total_ai_job_recommendations > 0:
            ai_recommendations_menu = f"✅ AI found {self.total_ai_job_recommendations} listings match your resume and job preferences"

        self.menu_items = [resume_menu, "🕸  Scrape \"Ask HN: Who's hiring?\"",
                           db_menu_item, find_best_matches_menu, 
                           ai_recommendations_menu]  # New menu option added
        self.current_row = 0
        self.setup()
        
    async def process_with_gpt(self):
        try:
            def update_ui(message):
                self.stdscr.clear()
                self.stdscr.addstr(0, 0, message)
                self.stdscr.refresh()
                self.logger.debug("It's getting back to update_ui at least")
            
            self.logger.debug("Calling: self.gpt_processor.process_job_listings_with_gpt")
            await self.gpt_processor.process_job_listings_with_gpt(self.resume_path, update_ui_callback=update_ui)
        except Exception as e:
            self.logger.exception("Failed to process listings with GPT: %s", str(e))
        finally:
            # Update menu items and redraw the menu after scraping is done
            self.update_menu_items()
            self.stdscr.refresh()
            self.stdscr.getch()  # Wait for any key press after completion

    def read_resume_from_file(self):
        try:
            with open(self.resume_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return ""

    def setup(self):
        curses.curs_set(0)  # Turn off cursor visibility
        self.display_splash_screen()
        self.stdscr.keypad(True)  # Enable keypad mode
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
        self.run()

    def display_splash_screen(self):
        splash_text = [
            " ██████╗ ██████╗ ███╗   ███╗███╗   ███╗ █████╗ ███╗   ██╗██████╗ ",
            "██╔════╝██╔═══██╗████╗ ████║████╗ ████║██╔══██╗████╗  ██║██╔══██╗",
            "██║     ██║   ██║██╔████╔██║██╔████╔██║███████║██╔██╗ ██║██║  ██║",
            "██║     ██║   ██║██║╚██╔╝██║██║╚██╔╝██║██╔══██║██║╚██╗██║██║  ██║",
            "╚██████╗╚██████╔╝██║ ╚═╝ ██║██║ ╚═╝ ██║██║  ██║██║ ╚████║██████╔╝",
            "╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝ ",
            "                                                                ",
            "                   ██╗ ██████╗ ██████╗ ███████╗                 ",
            "                   ██║██╔═══██╗██╔══██╗██╔════╝                 ",
            "                   ██║██║   ██║██████╔╝███████╗                 ",
            "              ██   ██║██║   ██║██╔══██╗╚════██║                 ",
            "              ╚█████╔╝╚██████╔╝██████╔╝███████║                 ",
            "               ╚════╝  ╚═════╝ ╚═════╝ ╚══════╝                 ",
                                                
        ]
        self.stdscr.clear()
        max_y, max_x = self.stdscr.getmaxyx()
        self.stdscr.attron(curses.color_pair(6))
        for i, line in enumerate(splash_text):
            # Calculate the starting position for each line to be centered
            start_x = max(0, (max_x - len(line)) // 2)
            self.stdscr.addstr(i + (max_y - len(splash_text)) // 2, start_x, line)
        self.stdscr.refresh()
        curses.napms(1000)  # Display the splash screen for 500 milliseconds
        self.stdscr.attroff(curses.color_pair(6))

    def draw_title(self, title="Command Jobs"):
        max_y, max_x = self.stdscr.getmaxyx()
        title_x = max(0, (max_x - len(title)) // 2)
        self.stdscr.attron(curses.A_BOLD)
        self.stdscr.addstr(0, title_x, title)
        self.stdscr.attroff(curses.A_BOLD)
        self.stdscr.addstr(1, 0, "-" * max_x)

    def draw_menu(self):
        self.stdscr.clear()
        self.draw_title()
        h, w = self.stdscr.getmaxyx()
        for idx, item in enumerate(self.menu_items):
            x = w // 2 - len(item) // 2
            y = h // 2 - len(self.menu_items) // 2 + idx
            if idx == self.current_row:
                self.stdscr.attron(curses.color_pair(1))
                self.stdscr.addstr(y, x, item)
                self.stdscr.attroff(curses.color_pair(1))
            else:
                self.stdscr.addstr(y, x, item)
        self.stdscr.refresh()

    def run(self):
        while True:
            self.draw_menu()
            key = self.stdscr.getch()
            self.handle_keypress(key)

    def handle_keypress(self, key):
        if key == curses.KEY_UP:
            self.current_row = max(0, self.current_row - 1)
        elif key == curses.KEY_DOWN:
            self.current_row = min(len(self.menu_items) - 1, self.current_row + 1)
        elif key in [curses.KEY_ENTER, 10, 13]:
            self.execute_menu_action()
        elif key == ord('q'):
            exit()

    def update_menu_items(self):
        # Update the total listings count
        self.total_listings = self.get_total_listings()
        self.total_ai_job_recommendations = self.table_display.fetch_total_entries()
        
        # Update the resume option
        resume_menu = "📄 Create resume (just paste it here once)"
        resume_str = self.read_resume_from_file()
        if len(resume_str) > 0:
            resume_menu = "📄 Edit resume"
        
        # Update menu items with the new counts
        db_menu_item = f"💾 Navigate jobs in local db ({self.total_listings} listings)"
        ai_recommendations_menu = "😅 No job matches for your resume yet"
        if self.total_ai_job_recommendations > 0:
            ai_recommendations_menu = f"✅ AI found {self.total_ai_job_recommendations} listings match your resume and job preferences"
        
        # Update the relevant menu items
        self.menu_items[2] = db_menu_item
        self.menu_items[4] = ai_recommendations_menu
        self.menu_items[0] = resume_menu
        
        # Redraw the menu to reflect the updated items
        self.draw_menu()


    # Menu options, the number map to the self.menu_items array
    # eg. first option (0): self.menu_items[0] = resume_menu 
    # = "Create or replace base resume"
    def execute_menu_action(self):
        if self.current_row == 0:  # Create or replace base resume
            self.manage_resume(self.stdscr)
        elif self.current_row == 1:  # Scrape "Ask HN: Who's hiring?"
            self.start_scraping_with_status_updates()
        elif self.current_row == 2:  # Navigate jobs in local db
            draw_table(self.stdscr, self.db_path)
        elif self.current_row == 3:  # "Process job listings with GPT" option
            asyncio.run(self.process_with_gpt())
            self.stdscr.getch()  # Wait for any key press after completion
        elif self.current_row == 4:  # Index of the new menu option
            self.table_display.draw_table()
        self.stdscr.clear()

    def display_text_with_scrolling(self, header, lines, resume_path):
        curses.noecho()
        max_y, max_x = self.stdscr.getmaxyx()
        offset = 0  # How much we've scrolled

        while True:
            self.stdscr.clear()
            self.draw_title()  # Call draw_title as a method of the class
            # Draw the sticky header below the title
            self.stdscr.attron(curses.color_pair(2))  # Apply color pair for white background
            self.stdscr.addstr(2, 0, header + " " * (max_x - len(header)))  # Extend background to full width
            self.stdscr.attroff(curses.color_pair(2))  # Turn off color pair

            for i, line in enumerate(lines[offset:offset+max_y-5]):
                self.stdscr.addstr(i+3, 0, line.strip())
            
            key = self.stdscr.getch()
            if key in [ord('q'), ord('Q')]:
                break
            elif key == curses.KEY_DOWN:
                if offset < len(lines) - max_y + 2:
                    offset += 1
            elif key == curses.KEY_UP:
                if offset > 0:
                    offset -= 1
            elif key in [ord('r'), ord('R')]:
                lines = self.capture_text_with_scrolling()
                with open(resume_path, 'w') as file:
                    file.writelines(lines)
                break
    
    def get_total_listings(self):
        """Return the total number of job listings in the database."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM job_listings")
        total = cur.fetchone()[0]
        conn.close()
        return total

    def manage_resume(self, stdscr):
        curses.echo()
        resume_path = os.getenv('BASE_RESUME_PATH')

        if os.path.exists(resume_path):
            with open(resume_path, 'r') as file:
                lines = file.readlines()
            
            header = "Base Resume (Press 'q' to go back, 'r' to replace):"  # Use a separator for clarity
            self.display_text_with_scrolling(header, lines, resume_path)
        else:
            # Adjust the prompt position in capture_text_with_scrolling if needed
            input_lines = self.capture_text_with_scrolling()
            with open(resume_path, 'w') as file:
                file.writelines(input_lines)
            stdscr.clear()
            self.draw_title("Resume saved. Press any key to continue...")  # Redraw title after clearing
            stdscr.getch()
            self.update_menu_items()  # Redraw the menu with updated items
    
    def update_scraping_status(self, text):
        max_y, max_x = self.stdscr.getmaxyx()
        # Ensure the status text will not overflow the screen width
        status_text = text[:max_x - 3]
        try:
            # Clear the previous status bar content
            self.stdscr.move(max_y - 1, 0)
            self.stdscr.clrtoeol()
            # Write the new status bar content
            self.stdscr.addstr(max_y - 1, 0, status_text, curses.color_pair(2))
            self.stdscr.refresh()
        except curses.error:
            pass  # Ignore the error or handle it as needed

    def start_scraping_with_status_updates(self):
        # Create a queue to receive the result from the scraping thread
        result_queue = Queue()
        # Pass self.update_scraping_status as the update function to HNScraper
        self.scraper = HNScraper(self.db_path)  # Initialize the scraper
        start_url = os.getenv('HN_START_URL')  # Starting URL
        scraping_thread = threading.Thread(target=self.scraper.scrape_hn_jobs, args=(
            start_url, self.stdscr, self.update_scraping_status, self.scraping_done_event, result_queue))
        scraping_thread.start()
        # Call this method after the scraping is done
        self.scraping_done_event.wait()  # Wait for the event to be set by the scraping thread
        # Retrieve the result from the queue
        new_listings_count = result_queue.get()  # This will block until the result is available
        self.update_menu_items()  # Update the menu items after scraping
        self.draw_menu()  # Redraw the menu with updated items
        self.update_scraping_status(f"Scraping completed {new_listings_count} new listings added")
        self.stdscr.refresh()  # Refresh the screen to show the updated menu
        self.stdscr.getch()  # Wait for any key press after completion
        self.scraping_done_event.clear()  # Clear the event for the next scraping operation

    def update_ui(self, progress_text, source_text=""):
        # Clear the screen and display the progress or completion message
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, "Scraping progress:")
        self.stdscr.addstr(2, 0, progress_text)
        if source_text:
            self.stdscr.addstr(3, 0, f"Source: {source_text}")
        self.stdscr.refresh()

    # Despite the name of the method, this currently
    # is not handling scrolling 😅
    
    # It directs the user to paste text into the terminal
    # When Esc is pressed, captures the input and returns it 
    def capture_text_with_scrolling(self):
        directions = "Paste your resume text, then Press the 'Esc' key to finish and save"
        curses.curs_set(1)  # Show cursor
        self.stdscr.keypad(True)  # Enable keypad mode
        curses.noecho()      # Don't echo keypresses
        curses.raw()         # Raw mode - get all inputs
        self.stdscr.clear()       # Clear the screen
        self.stdscr.scrollok(True)  # Enable scrolling in the window
        
        text = []
        y, x = 0, 0  # Initial position
        max_y, max_x = self.stdscr.getmaxyx()
        
        # This loop "listens" for keyboard input
        while True:
            self.stdscr.addstr(0, 0, directions, curses.A_REVERSE)
            try:
                char = self.stdscr.get_wch()  # Get character or key press
            except AttributeError:
                # To be able to handle utf8, we need ncurses to have
                # the stdscr.get_wch() method available
                self.stdscr.addstr(0, 0, "Error, app needs stdscr.get_wch() method", curses.A_REVERSE)
                
                return ''
        
            if char == '\x1b':  # Escape key pressed
                break
            elif char == '\n':  # Handle newline
                text.append('\n')
                y += 1
                x = 0
                if y >= max_y - 1:
                    self.stdscr.scroll(1)
                    y -= 1
            elif isinstance(char, str):  # Regular character input
                if x >= max_x - 1:  # Move to next line if at the end
                    y += 1
                    x = 0
                    if y >= max_y - 1:
                        self.stdscr.scroll(1)
                        y -= 1
                text.append(char)
                try:
                    self.stdscr.addstr(y, x, char)
                except curses.error:
                    pass  # Ignore errors potentially caused by edge cases in window size
                x += 1
            self.stdscr.refresh()

        return ''.join(text)

# Ensure logging is configured to write to a file or standard output
logging.basicConfig(filename='application.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

def main(stdscr):
    global logger
    app = MenuApp(stdscr, logger)
    app.run()  # Ensuring app.run is called to start the application loop

if __name__ == "__main__":
    curses.wrapper(main)

