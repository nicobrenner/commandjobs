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
    
    return job_links


def get_job_details(job_url):
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
            original_html = extracted_content_str[:20] + '...'

            # Extract external ID from job URL
            external_id = job_url.split('/')[-1]

            source = "Work at a startup"
            print("original text: ", original_text)
            print("original html: ", original_html)
            print("source : ", source)
            print("external_id: ", external_id)

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

def scrape_jobs(main_page_url):
    jobs_list = []
    company_links = get_company_links(main_page_url)
    
    for company_link in company_links:
        print(f"Processing company: {company_link}")
        job_links = get_job_links(company_link)
        print(f"Found {len(job_links)} job links for company {company_link}")
        for job_link in job_links:
            print(f"Job link: {job_link}")
            job_details = get_job_details(job_link)
            if job_details:
                jobs_list.append(job_details)
    
    return jobs_list

main_page_url = 'https://www.workatastartup.com/jobs'
jobs_list = scrape_jobs(main_page_url)

#print("\nScraped Jobs:")
#for job in jobs_list:
#    print(job)
