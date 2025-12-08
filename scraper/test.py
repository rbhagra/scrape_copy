
import requests
from bs4 import BeautifulSoup


def scrape():
    url ="https://www.congress.gov/119/bills/hr4305/BILLS-119hr4305rh.xml"
    response = requests.get(url)
    soup = BeautifulSoup (response.text, "lxml")
    print(soup.prettify())

if __name__ == '__main__':
    scrape()
