import requests
from bs4 import BeautifulSoup
import json

base_url = 'https://www.workatastartup.com'

def get_company_links(main_page_url):
    response = requests.get(main_page_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    company_links_set = set()
    company_links = []
    
    for a in soup.select('a[target="company"]'):
        company_url = a['href']
        if company_url not in company_links_set:
            company_links.append(company_url)
            company_links_set.add(company_url)
    
    return company_links


def get_job_links(company_url):

    
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
    
    print(f"Company {company_url} has {len(job_links)} job links:")
    for link in job_links:
        print(link)
    
    return job_links


def get_job_details(job_url):
    response = requests.get(job_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Adjust the selector based on inspection
    job_description_section = soup.select_one('div.job-description')
    if job_description_section:
        original_text = job_description_section.get_text(strip=True)[:20] + '...'
        original_html = str(job_description_section)[:20] + '...'
        external_id = job_url.split('/')[-1]
        
        return {
            'original_text': original_text,
            'original_html': original_html,
            'source': job_url,
            'external_id': external_id
        }
    return None

def scrape_jobs(main_page_url):
    jobs_list = []
    company_links = get_company_links(main_page_url)
    
    for company_link in company_links:
        job_links = get_job_links(company_link)
        
    
    return jobs_list

main_page_url = 'https://www.workatastartup.com/jobs'
jobs_list = scrape_jobs(main_page_url)

