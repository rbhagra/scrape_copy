## scraper
from http.client import responses

import requests
from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# URL = "https://www.congress.gov/118/bills/hr9737/BILLS-118hr9737ih.xml"

def scrape(URL):
    try:
        response = requests.get(URL)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "xml")
        return classify(soup)
    except Exception:
        return f"Error: could not find bill"


def classify(soup):
    
    # searches for defs header
    definitions_header = soup.find('header', string=lambda t: t and 'definitions' in t.lower())
    
    # alternative: hard searches defs in text and pulls header
    if not definitions_header:
        definitions_text_node = soup.find(string=lambda t: t and 'definitions' in t.lower())
        if definitions_text_node:
            definitions_header = definitions_text_node.find_parent('header')
    
    if definitions_header:
        # finds section w/ definitions
        definitions_section = definitions_header.find_parent('section')
        
        if not definitions_section:
            # second search
            definitions_section = definitions_header.find_next_sibling('section')
        
        if definitions_section:
            #extracting paragraph tags 
            paragraphs = definitions_section.find_all('paragraph')
            
            if paragraphs:
                # dictionary to store terms and defs
                definitions_dict = {}
                # Combining paragraphs 
                definitions_list = []
                for para in paragraphs:
                    ## strips numbering, can delete 52-54 if want to retain 
                    enum_tag = para.find('enum')
                    if enum_tag:
                        enum_tag.decompose()
                    header_tag = para.find('header')
                    # saves term and discards to pull definition
                    if header_tag:
                        term = header_tag.get_text(separator=' ', strip=True)
                        header_tag.decompose()
                    else:
                        term = "Unknown"
            
                    # identifies definitions
                    definition = para.get_text(separator=' ', strip=True)


                    # adds to dictionary 
                    if term and definition:
                        definitions_dict[term] = definition
                return definitions_dict
               
            else:
                # just grabbing all text
                definitions_text = definitions_section.get_text(separator='\n', strip=True)
                lines = definitions_text.split('\n')
                # drop header
                if lines and "Definitions" in lines[0]:
                    return "\n".join(lines[1:])
                return definitions_text
    # prints out as unformmated definitions section. Needs some work to handle end of definition section -- might be weird edge cases
    return "couldn't find definitions section"

if __name__ == "__main__":
    URL = input("Enter XML URL: ")
    data = scrape(URL)
    if isinstance(data, dict):
        for term, definition in data.items():
            print(f"TERM: {term}")
            print(f"DEF:  {definition}")
            print("-" * 40)

    else:
        print (data)






