import logging
import sqlite3
import time
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from job_scraper.scraper_selectors.workday_selectors import WorkDaySelectors
from job_scraper.utils import get_workday_post_time_range, get_workday_company_urls


class WorkdayScraper:
    def __init__(self, update_func=None):
        self.db_path = 'job_listings.db'
        self.driver = webdriver.Chrome(options=self.get_options_config())
        self.one_week_span_text = get_workday_post_time_range()
        self.company_urls = get_workday_company_urls()
        self.update_func = update_func
        self.job_listings = []

    @staticmethod
    def get_options_config() -> Options:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
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
            inserted = self.save_to_database(job['original_text'], job['original_html'], job['source'], job['external_id'])
            if inserted:
                self.new_entries_count += 1
        self.job_listings = []

    def scrape(self, stdscr, update_func=None, done_event=None, result_queue=None):
        total_companies = len(self.company_urls)
        for idx, company_url in enumerate(self.company_urls, 1):
            self.update_func(f"Scraping company {idx}/{total_companies}: {company_url}")
            self.driver.get(company_url)
            wait = WebDriverWait(self.driver, 10)

            posted_this_week = True
            while posted_this_week:
                try:
                    wait.until(EC.presence_of_element_located((By.XPATH, WorkDaySelectors.JOB_LISTING_XPATH)))
                except TimeoutException:
                    logging.warning("Job Listing Element not found")
                    break

                job_elements = self.driver.find_elements(By.XPATH, WorkDaySelectors.JOB_LISTING_XPATH)

                for job_element in job_elements:
                    try:
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
                            self.save_to_database(job_description, job_description_html, job_url, job_id)
                        else:
                            logging.info("Reached posts older than one week. Stopping!")
                            self.save_job_listings_to_db()
                            posted_this_week = False
                            break
                    except StaleElementReferenceException:
                        logging.warning("StaleElementReferenceException encountered. Retrying...")
                        time.sleep(1)
                        continue

                if not posted_this_week:
                    break

                try:
                    next_page_button = wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@data-uxi-element-id='next']"))
                    )
                    next_page_button.click()
                except TimeoutException:
                    logging.info("Reached end of job listings. Stopping!")
                    break

            progress_percent = (idx / total_companies) * 100
            self.update_func(f"Progress: {progress_percent:.0f}% - Completed {idx}/{total_companies} companies")

        self.update_func("Scraping completed for all companies.")


scraper = WorkdayScraper()
scraper.scrape()
