import sqlite3
import time
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from job_scraper.scraper_selectors.workday_selectors import WorkDaySelectors
from job_scraper.utils import get_workday_post_time_range, get_workday_company_urls


class WorkdayScraper:
    def __init__(self, db_path='job_listings.db', update_func=None, done_event=None, result_queue=None):
        self.db_path = db_path
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.get_selenium_configs())
        self.one_week_span_text = get_workday_post_time_range()
        self.company_urls = get_workday_company_urls()
        self.new_entries_count = 0
        self.done_event = done_event
        self.result_queue = result_queue
        self.update_func = update_func
        self.job_listings = []

    @staticmethod
    def get_selenium_configs() -> Options:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        return chrome_options

    def save_to_database(self, original_text, original_html, source, external_id):
        """Save a job listing to the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO job_listings (original_text, original_html, source, external_id) VALUES (?, ?, ?, ?)",
                  (original_text, original_html, source, external_id))
        conn.commit()
        conn.close()
        return c.rowcount > 0

    def save_new_job_listing(self, job_description, job_description_html, job_url, job_id):
        if not job_description:
            return
        if not job_description_html:
            return
        if not job_url:
            return
        if not job_id:
            return
        self.job_listings.append({
            'original_text': job_description,
            'original_html': job_description_html,
            'source': job_url,
            'external_id': job_id
        })

    def save_job_listings_to_db(self):
        for job in self.job_listings:
            # inserted = self.save_to_database(
            #     job['original_text'],
            #     job['original_html'],
            #     job['source'],
            #     job['external_id']
            # )
            inserted = job['external_id']
            if inserted:
                self.new_entries_count += 1
        if self.done_event:
            self.result_queue.put(self.new_entries_count)
            self.done_event.set()

    def scrape(self):
        for company_name, company_url in self.company_urls.items():
            self.driver.get(company_url)
            wait = WebDriverWait(self.driver, 10)
            self.update_func(f"Scraping Workday companies:\t{", ".join(self.company_urls.keys())}")

            posted_this_week = True
            while posted_this_week:
                try:
                    wait.until(EC.presence_of_element_located((By.XPATH, WorkDaySelectors.JOB_LISTING_XPATH)))
                except TimeoutException:
                    self.update_func("Job Listing Element not found. Try again later")
                    break

                job_elements = self.driver.find_elements(By.XPATH, WorkDaySelectors.JOB_LISTING_XPATH)
                for job_element in job_elements:
                    try:
                        self.update_func(f"*{company_name}* \n {self.driver.current_url}")
                        job_title_element = job_element.find_element(By.XPATH, WorkDaySelectors.JOB_TITLE_XPATH)
                        job_id_element = job_element.find_element(By.XPATH, WorkDaySelectors.JOB_ID_XPATH)
                        job_id = job_id_element.text
                        posted_on_element = job_element.find_element(By.XPATH, WorkDaySelectors.POSTED_ON_XAPTH)
                        posted_on = posted_on_element.text

                        if posted_on.lower() in self.one_week_span_text:
                            job_url = job_title_element.get_attribute('href')
                            job_title_element.click()
                            job_description_element = wait.until(
                                EC.presence_of_element_located((By.XPATH, WorkDaySelectors.JOB_DESCRIPTION_XPATH))
                            )
                            job_description = job_description_element.text
                            job_description_html = job_description_element.get_attribute("innerHTML")
                            self.save_new_job_listing(job_description, job_description_html, job_url, job_id)
                        else:
                            posted_this_week = False
                            break
                    except StaleElementReferenceException:
                        self.update_func("Encountered an issue while fetching job list. Retrying...")
                        time.sleep(1)

                if not posted_this_week:
                    break

                try:
                    next_page_button = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@data-uxi-element-id='next']"))
                    )
                    next_page_button.click()
                except TimeoutException:
                    self.update_func("TimeoutException. Please try again later!")
                    break

        self.save_job_listings_to_db()
        self.update_func("Scraping completed for all companies.")
