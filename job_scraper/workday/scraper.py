import logging
import sqlite3
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

from job_scraper.scraper_selectors.workday_selectors import WorkDaySelectors
from job_scraper.utils import get_workday_company_urls, get_workday_post_time_range
from src.work_startup_scraper import WorkStartupScraper


class WorkdayScraper():
    def __init__(self, url, source = None):
        self.source = source
        self.db_path = 'job_listings.db'
        self.url: str = url
        self.driver: webdriver = webdriver.Chrome(options=self.get_options_config())
        self.jobs: list = []
        self.one_week_span_text: list[str] = get_workday_post_time_range()


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
        # Use INSERT OR IGNORE to skip existing records with the same external_id
        c.execute("INSERT OR IGNORE INTO job_listings (original_text, original_html, source, external_id) VALUES (?, ?, ?, ?)",
                  (original_text, original_html, source, external_id))
        conn.commit()
        conn.close()
        return c.rowcount > 0 # True if the listing was inserted

    def scrape(self) -> list:
        while True:
            self.driver.get(self.url)
            wait = WebDriverWait(self.driver, 10)

            posted_this_week = True
            while posted_this_week:
                time.sleep(2)
                try:
                    wait.until(EC.presence_of_element_located((By.XPATH, WorkDaySelectors.JOB_LISTING_XPATH)))
                except TimeoutException as e:
                    logging.warning(f"-- Job Listing Element not found")
                    continue

                job_elements = self.driver.find_elements(By.XPATH, WorkDaySelectors.JOB_LISTING_XPATH)

                for job_element in job_elements:
                    job_title_element = job_element.find_element(By.XPATH, WorkDaySelectors.JOB_TITLE_XPATH)
                    job_id_element = job_element.find_element(By.XPATH, WorkDaySelectors.JOB_ID_XPATH)
                    job_id = job_id_element.text
                    posted_on_element = job_element.find_element(By.XPATH, WorkDaySelectors.POSTED_ON_XAPTH)
                    posted_on = posted_on_element.text
                    if posted_on.lower() in posted_on.lower():
                        job_url = job_title_element.get_attribute('href')
                        job_title_element.click()
                        job_description_element = wait.until(EC.presence_of_element_located(
                            (By.XPATH, WorkDaySelectors.JOB_DESCRIPTION_XPATH)))
                        job_description = job_description_element.text
                        job_description_html = job_description_element.get_attribute("innerHTML")

                        self.save_to_database(job_description, job_description_html, job_url, job_id)
                    else:
                        logging.warning(f'-- Reached posts that are older than one week. Stopping!')
                next_page_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@data-uxi-element-id='next']")))
                next_page_button.click()
            return self.jobs
