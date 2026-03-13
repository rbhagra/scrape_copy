
import requests
from bs4 import BeautifulSoup


def scrape():
    url ="https://www.congress.gov/118/bills/hr112/BILLS-118hr112ih.htm"
    response = requests.get(url)
    print(response.text)

if __name__ == '__main__':
    scrape()
