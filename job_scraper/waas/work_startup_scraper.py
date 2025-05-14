import sqlite3
import requests
from bs4 import BeautifulSoup
import json

class ScrapingInterrupt(Exception):
    pass

class WorkStartupScraper:

    def __init__(self, db_path='job_listings.db'):
        self.db_path = db_path
        # Define the base URL for Ask HN: Who's hiring
        self.base_url = 'https://www.workatastartup.com/jobs'
        self.new_entries_count = 0  # Initialize counter for new entries

    def get_company_links(self):
        response = requests.get(self.base_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        company_links_set = set()
        company_links = []
        
        for a in soup.select('a[target="company"]'):
            company_url = a['href']
            if company_url not in company_links_set:
                company_links.append(company_url)
                company_links_set.add(company_url)
        
        return company_links


    def get_job_links(self, company_url):
        
        # Fetch the HTML content from the URL
        response = requests.get(company_url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all elements with a data-page attribute
        data_page_elements = soup.find_all(attrs={"data-page": True})

        # Initialize a list to store matching links
        job_links = []

        # Find the div with the data-page attribute
        div = soup.find('div', {'data-page': True})
        if div:
            # Extract the JSON-like content from the data-page attribute
            data_page_content = div['data-page']
            
            # Parse the JSON content
            data = json.loads(data_page_content)
            
            # Extract job links
            for job in data['props']['rawCompany']['jobs']:
                job_link = job['show_path']
                job_links.append(job_link)
        
        return job_links


    def get_job_details(self, job_url):
        response = requests.get(job_url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the "About the role" section and extract content until "How you'll contribute"
        about_section = soup.find(string="About the role")
        if about_section:
            # Find the parent element of "About the role"
            about_div = about_section.find_parent('div')
            if about_div:
                # Extract content between "About the role" and "How you'll contribute"
                extracted_content = []
                for sibling in about_div.next_siblings:
                    if sibling.name == 'div' and sibling.find(string="How you'll contribute"):
                        break
                    extracted_content.append(str(sibling))

                # Join the extracted content
                extracted_content_str = ''.join(extracted_content).strip()

                # Get original text and HTML
                original_text = BeautifulSoup(extracted_content_str, 'html.parser').get_text(strip=True)
                original_html = extracted_content_str

                # Extract external ID from job URL
                external_id = job_url
                source = "Work at a startup"

                return {
                    'original_text': original_text,
                    'original_html': original_html,
                    'source': source,
                    'external_id': external_id
                }
            else:
                print(f"No parent element found for 'About the role' in {job_url}")
        else:
            print(f"'About the role' section not found in {job_url}")
        return None

    def scrape_jobs(self, stdscr, update_func=None, done_event=None, result_queue=None):
        """Scrape job listings from Work at a Startup and save them to the database."""
        jobs_list = []
        update_func(f"Scraping: {self.base_url}")
        try: 
            company_links = self.get_company_links()
            count = 0
            flag1 = False
            flag2 = False
            flag3 = False
            for company_link in company_links:
                count += 1
                job_links = self.get_job_links(company_link)
                for job_link in job_links:
                    job_details = self.get_job_details(job_link)
                    if job_details:
                        jobs_list.append(job_details)
                if update_func:
                    update_func(f"Scraping: {company_link}")
                # Updates the progress of the scraping
                if  count / len(company_links)>= 0.25 and not flag1:
                    update_func("Scraping: 25% of companies completed")
                    flag1 = True
                elif count / len(company_links)>= 0.5 and not flag2:
                    update_func("Scraping: 50% of companies completed")
                    flag2 = True
                elif count / len(company_links)>= 0.75:
                    update_func("Scraping: 75% of companies completed")
                    flag3 = True
            
            for job in jobs_list:
                inserted= self.save_to_database(job['original_text'], job['original_html'], job['source'], job['external_id'])
                if inserted:
                    self.new_entries_count += 1
                
                if job==jobs_list[-1]:
                    if done_event:
                        result_queue.put(self.new_entries_count)
                        done_event.set()  # Set the event to signal that scraping is done
            
        except requests.exceptions.Timeout as e:
            if update_func:
                update_func("Request timed out. Try again later.")
            
        except requests.exceptions.RequestException as e:
            if update_func:
                update_func(f"Request failed: {str(e)}")

        # Handle user interrupts
        except ScrapingInterrupt:
            if update_func:
                update_func(f"Scraping interrupted by user. {self.new_entries_count} new listings added")


    def save_to_database(self, original_text, original_html, source, external_id):
            """Save a job listing to the SQLite database."""
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL;")
            c = conn.cursor()
            # Use INSERT OR IGNORE to skip existing records with the same external_id
            c.execute("INSERT OR IGNORE INTO job_listings (original_text, original_html, source, external_id) VALUES (?, ?, ?, ?)",
                    (original_text, original_html, source, external_id))
            conn.commit()
            conn.close()
            return c.rowcount > 0 # True if the listing was inserted
