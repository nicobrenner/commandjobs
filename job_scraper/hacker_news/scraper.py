import requests
from bs4 import BeautifulSoup
import sqlite3

# Define a new exception for interrupting scraping
class ScrapingInterrupt(Exception):
    pass

class HNScraper:
    def __init__(self, db_path='job_listings.db'):
        self.db_path = db_path
        # Define the base URL for Ask HN: Who's hiring
        self.base_url = 'https://news.ycombinator.com/item?id=40563283&p=1'
        self.new_entries_count = 0  # Initialize counter for new entries

    def save_to_database(self, original_text, original_html, source, external_id):
        """Save a job listing to the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Use INSERT OR IGNORE to skip existing records with the same external_id
        c.execute("INSERT OR IGNORE INTO job_listings (original_text, original_html, source, external_id) VALUES (?, ?, ?, ?)",
                  (original_text, original_html, source, external_id))
        conn.commit()
        conn.close()
        return c.rowcount > 0 # True if the listing was inserted

    def scrape_hn_jobs(self, start_url, stdscr, update_func=None, done_event=None, result_queue=None):
        """Scrape job listings from Hacker News and save them to the database."""
        url = start_url
        update_func(f"Scraping: {start_url}")
        while url:
            try:
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')

                comments = soup.find_all('tr', class_='athing comtr')
                for comment in comments:
                    ind_cell = comment.find('td', class_='ind')
                    img = ind_cell.find('img') if ind_cell else None
                    if img and img.get('width') == "0":  # Top-level comment
                        job_description = comment.find('div', class_='commtext c00')
                        if job_description:
                            original_text = job_description.text
                            original_html = job_description.prettify()
                            # Extract the external_id from the comment element
                            comment_id = comment.get('id')
                            external_id = f"https://news.ycombinator.com/item?id={comment_id}"
                            source = "Hacker News"
                            inserted = self.save_to_database(original_text, original_html, source, external_id)

                            if inserted:  # if the row was inserted
                                self.new_entries_count += 1  # Increment the new entries count
                                # Check for updates and interrupts
                                if update_func:
                                    update_func(original_text[:100])  # Call the update function with truncated text
                            if update_func:
                                update_func(f"Scraping: {source}")

                more_link = soup.find('a', class_='morelink')
                if more_link:
                    url = 'https://news.ycombinator.com/' + more_link['href']
                    if update_func:
                        update_func(f"Page complete, loading next... {self.new_entries_count} listings added so far")
                else:
                    url = None

            except requests.exceptions.Timeout as e:
                if update_func:
                    update_func("Request timed out. Try again later.")
                break
            
            except requests.exceptions.RequestException as e:
                if update_func:
                    update_func(f"Request failed: {str(e)}")
                break

            # Handle user interrupts
            except ScrapingInterrupt:
                if update_func:
                    update_func(f"Scraping interrupted by user. {self.new_entries_count} new listings added")
                break

        if update_func:
            # Put the result into the queue
            result_queue.put(self.new_entries_count)
            if done_event:
                done_event.set()  # Set the event to signal that scraping is done

if __name__ == "__main__":
    db_path = 'job_listings.db'
    scraper = HNScraper(db_path)
    start_url = 'https://news.ycombinator.com/item?id=40563283&p=1'
    scraper.scrape_hn_jobs(start_url)
