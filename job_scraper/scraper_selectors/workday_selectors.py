from enum import StrEnum


class WorkDaySelectors(StrEnum):
    JOB_LISTING_XPATH = '//li[@class="css-1q2dra3"]'
    JOB_TITLE_XPATH = './/h3/a'
    JOB_ID_XPATH = './/ul[@data-automation-id="subtitle"]/li'
    POSTED_ON_XAPTH = './/dd[@class="css-129m7dg"][preceding-sibling::dt[contains(text(),"posted on")]]'
    JOB_DESCRIPTION_XPATH = '//div[@data-automation-id="jobPostingDescription"]'