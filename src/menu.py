import curses
import os
import time
from job_scraper.hacker_news.scraper import HNScraper
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

from job_scraper.workday.scraper import WorkdayScraper
from work_startup_scraper import WorkStartupScraper

DB_PATH='job_listings.db'

class MenuApp:
    def __init__(self, stdscr, logger):
        # Load environment variables
        load_dotenv()
        required_values = (
            "OPENAI_API_KEY",
            "OPENAI_GPT_MODEL",
            "BASE_RESUME_PATH",
            "HN_START_URL",
            "COMMANDJOBS_LISTINGS_PER_BATCH",
        )
        for required_value in required_values:
            if not os.getenv(required_value):
                error_message = f'''
                    {required_value} env variable is not set; Please check the documentation at
                    https://github.com/nicobrenner/commandjobs?tab=readme-ov-file#configuration
                    '''
                raise ValueError(error_message)

        self.scraping_done_event = threading.Event()  # Event to signal scraping completion
        self.logger = logger
        self.stdscr = stdscr
        self.setup_ncurses()
        self.db_path = DB_PATH
        self.db_manager = DatabaseManager(self.db_path)  # Specify the path
        self.gpt_processor = GPTProcessor(self.db_manager, os.getenv('OPENAI_API_KEY'))
        self.resume_path = os.getenv('BASE_RESUME_PATH')
        self.table_display = MatchingTableDisplay(self.stdscr, self.db_path)
        self.total_ai_job_recommendations = self.table_display.fetch_total_entries()
        self.update_processed_listings_count()
        self.total_listings = self.get_total_listings()
        env_limit = 0 if os.getenv('COMMANDJOBS_LISTINGS_PER_BATCH') is None else os.getenv('COMMANDJOBS_LISTINGS_PER_BATCH')
        self.listings_per_request = max(int(env_limit), 10)

        resume_menu = "📄 Create resume (just paste it here once)"
        find_best_matches_menu = "🧠 Find best matches with AI (Create your resume first)"
        resume_str = self.read_resume_from_file()
        if len(resume_str) > 0:
            resume_menu = "📄 Edit resume"
            find_best_matches_menu = f"🧠 Find best matches for resume with AI (will check {self.listings_per_request} listings at a time)"
        
        total_processed = f'{self.processed_listings_count} processed with AI so far'
        db_menu_item = f"💾 Navigate jobs in local db ({self.total_listings} listings, {total_processed})"
        ai_recommendations_menu = "😅 No job matches for your resume yet"
        if self.total_ai_job_recommendations > 0:
            ai_recommendations_menu = f"✅ {self.total_ai_job_recommendations} recommended listings, out of {total_processed}"

        self.menu_items = [resume_menu,
                           "🕸  Scrape \"Ask HN: Who's hiring?\"",
                           "🕸  Scrape \"Work at a Startup jobs\"",
                            "🕸  Scrape \"Workday\"",
                           db_menu_item, find_best_matches_menu, 
                           ai_recommendations_menu]  # New menu option added
        self.current_row = 0
        self.display_splash_screen()
        self.run()
    
    def update_processed_listings_count(self):
        self.processed_listings_count = self.db_manager.fetch_processed_listings_count()

    async def process_with_gpt(self):
        exit_message = 'Processing completed successfully'
        try:
            self.logger.debug('Calling: self.gpt_processor.process_job_listings_with_gpt')
            await self.gpt_processor.process_job_listings_with_gpt(self.resume_path, update_ui_callback=self.update_status_bar)
        except Exception as e:
            self.logger.exception("Failed to process listings with GPT: %s", str(e))
            exit_message = f'Failed to process listings with GPT: {str(e)}'
        finally:
            new_count = self.table_display.fetch_total_entries()
            if new_count > self.total_ai_job_recommendations:
                count_diff = new_count - self.total_ai_job_recommendations
                exit_message = f'Processing completed successfully. {count_diff} new matches found ({new_count} total)'
            else:
                exit_message = f'Processing completed successfully. No new matches found ({new_count} total)'

        return exit_message
    

    def read_resume_from_file(self):
        try:
            with open(self.resume_path, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return ''

    def setup_ncurses(self):
        curses.curs_set(0)  # Turn off cursor visibility
        self.stdscr.keypad(True)  # Enable keypad mode
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Highlight color
        curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Highlight headers color
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_MAGENTA)  # Highlight headers color
        curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)  # Highlight headers color
        curses.init_pair(7, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(8, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(9, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(10, curses.COLOR_MAGENTA, curses.COLOR_BLACK)
        curses.init_pair(11, curses.COLOR_RED, curses.COLOR_BLACK)

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
        
        # Repeat base animation 3 times
        for i in range(0, 3):
            # Loop through color pairs 7 to 11
            # defined inside setup_ncurses()
            for color in range(7, 12):
                self.stdscr.attron(curses.color_pair(color))
                for i, line in enumerate(splash_text):
                    # Calculate the starting position for each line to be centered
                    start_x = max(0, (max_x - len(line)) // 2)
                    self.stdscr.addstr(i + (max_y - len(splash_text)) // 2, start_x, line)
                self.stdscr.refresh()
                # 100ms per color
                curses.napms(100)
                self.stdscr.attroff(curses.color_pair(color))
        self.stdscr.clear()
        self.stdscr.refresh()

    def draw_title(self, title="Command Jobs"):
        max_y, max_x = self.stdscr.getmaxyx()
        title_x = max(0, (max_x - len(title)) // 2)
        self.stdscr.attron(curses.A_BOLD)
        self.stdscr.addstr(0, title_x, title)
        self.stdscr.attroff(curses.A_BOLD)
        self.stdscr.addstr(1, 0, "-" * max_x)

    def draw_menu(self):
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
        # Update the total and processed listings count
        self.total_listings = self.get_total_listings()
        self.total_ai_job_recommendations = self.table_display.fetch_total_entries()
        self.update_processed_listings_count()
        
        # Update the resume option
        resume_menu = "📄 Create resume (just paste it here once)"
        find_best_matches_menu = "🧠 Find best matches with AI (Create your resume first)"
        resume_str = self.read_resume_from_file()
        if len(resume_str) > 0:
            resume_menu = "📄 Edit resume"
            find_best_matches_menu = f"🧠 Find best matches for resume with AI (will check {self.listings_per_request} listings at a time)"
        
        # Update menu items with the new counts
        total_processed = f'{self.processed_listings_count} processed with AI so far'
        db_menu_item = f"💾 Navigate jobs in local db ({self.total_listings} listings, {total_processed})"
        ai_recommendations_menu = "😅 No job matches for your resume yet"
        if self.total_ai_job_recommendations > 0:
            ai_recommendations_menu = f"✅ {self.total_ai_job_recommendations} recommended listings, out of {total_processed}"
        
        # Update the relevant menu items
        self.menu_items[0] = resume_menu
        self.menu_items[4] = db_menu_item
        self.menu_items[5] = find_best_matches_menu
        self.menu_items[6] = ai_recommendations_menu
        
        # Redraw the menu to reflect the updated items
        self.draw_menu()


    # Menu options, the number map to the self.menu_items array
    # eg. first option (0): self.menu_items[0] = resume_menu 
    # = "Create or replace base resume"
    def execute_menu_action(self):
        exit_message = ''
        if self.current_row == 0:  # Create or replace base resume
            exit_message = self.manage_resume(self.stdscr)
        elif self.current_row == 1:  # Scrape "Ask HN: Who's hiring?"
            self.start_scraping_with_status_updates()
        elif self.current_row == 2:  # Scrape Work at a Startup jobs
            self.start_scraping_WaaS_with_status_updates()
        elif self.current_row == 3:  # Scrape Workday
            self.start_scraping_workday_with_status_updates()
        elif self.current_row == 4:  # Navigate jobs in local db
            draw_table(self.stdscr, self.db_path)
        elif self.current_row == 5:  # "Process job listings with GPT" option
            exit_message = asyncio.run(self.process_with_gpt())
        elif self.current_row == 6:  # Index of the new menu option
            self.table_display.draw_table()
        self.stdscr.clear()
        self.update_menu_items()
        if exit_message != '':
            self.update_status_bar(exit_message)

    def display_text_with_scrolling(self, header, lines):
        curses.noecho()
        max_y, max_x = self.stdscr.getmaxyx()
        offset = 0  # How much we've scrolled
        resume_updated = False
        new_lines = ''

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
                new_lines = self.capture_text_with_scrolling()
                if len(new_lines) > 0:
                    resume_updated = new_lines != lines
                break
        
        return resume_updated
    
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
        
        resume_updated = False
        exit_message = 'Resume not updated'

        if os.path.exists(resume_path):
            with open(resume_path, 'r') as file:
                lines = file.readlines()
            
            header = "Base Resume (Press 'q' to go back, 'r' to replace):"  # Use a separator for clarity
            resume_updated = self.display_text_with_scrolling(header, lines)
        else:
            resume_updated = self.capture_text_with_scrolling()
            
        if resume_updated:
            exit_message = f"Resume saved to {self.resume_path}"
        
        return exit_message
    
    def update_status_bar(self, text):
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
        # Pass self.update_status_bar as the update function to HNScraper
        self.scraper = HNScraper(self.db_path)  # Initialize the scraper
        start_url = os.getenv('HN_START_URL')  # Starting URL
        scraping_thread = threading.Thread(target=self.scraper.scrape_hn_jobs, args=(
            start_url, self.stdscr, self.update_status_bar, self.scraping_done_event, result_queue))
        scraping_thread.start()
        # Call this method after the scraping is done
        self.scraping_done_event.wait()  # Wait for the event to be set by the scraping thread
        # Retrieve the result from the queue
        new_listings_count = result_queue.get()  # This will block until the result is available
        self.update_status_bar(f"Scraping completed {new_listings_count} new listings added")
        self.scraping_done_event.clear()  # Clear the event for the next scraping operation

       
        
    def start_scraping_WaaS_with_status_updates(self):  
        result_queue= Queue()
        self.scraper = WorkStartupScraper(self.db_path)
        scraping_thread = threading.Thread(target=self.scraper.scrape_jobs, args=(self.stdscr, self.update_status_bar, self.scraping_done_event, result_queue))
        scraping_thread.start()
        self.scraping_done_event.wait()
        new_listings_count = result_queue.get()
        self.update_status_bar(f"Scraping of Waas completed {new_listings_count} new listings added")
        self.scraping_done_event.clear()
        time.sleep(3)
        self.stdscr.clear()

    def start_scraping_workday_with_status_updates(self):
        result_queue= Queue()
        self.scraper = WorkdayScraper(self.db_path, self.update_status_bar, self.scraping_done_event, result_queue)
        scraping_thread = threading.Thread(target=self.scraper.scrape)
        scraping_thread.start()
        self.scraping_done_event.wait()
        new_listings_count = result_queue.get()
        self.update_status_bar(f"Scraping of Workday completed {new_listings_count} new listings added")
        self.scraping_done_event.clear()
        time.sleep(3)
        self.stdscr.clear()


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

        input_lines = ''.join(text)
        if text != []:
            with open(self.resume_path, 'w') as file:
                file.writelines(input_lines)

        curses.curs_set(0) # hide cursor again

        return input_lines

# Ensure logging is configured to write to a file or standard output
logging.basicConfig(filename='application.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

def main(stdscr):
    global logger
    app = MenuApp(stdscr, logger)
    app.run()  # Ensuring app.run is called to start the application loop

if __name__ == "__main__":
    curses.wrapper(main)

