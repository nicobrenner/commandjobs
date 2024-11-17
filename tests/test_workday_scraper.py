import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

from job_scraper.scraper_selectors.workday_selectors import WorkDaySelectors
from job_scraper.utils import get_workday_company_urls


@pytest.fixture(scope="module")
def selenium_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    yield driver
    driver.quit()

@pytest.mark.parametrize(
    "company_name, url", list(get_workday_company_urls().items())
)
def test_job_listing_xpath_present(selenium_driver, company_name, url):
    selenium_driver.get(url)
    wait = WebDriverWait(selenium_driver, 10)

    try:
        wait.until(EC.presence_of_element_located((By.XPATH, WorkDaySelectors.JOB_LISTING_XPATH)))
        print(f"PASS: JOB_LISTING_XPATH found for {company_name}")
    except TimeoutException:
        pytest.fail(f"FAIL: JOB_LISTING_XPATH not found for {company_name}")