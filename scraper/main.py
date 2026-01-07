from dbsetup import table_create
from html_storer import store_html
from txt_storer import retreive_txt
import time

def process_new_url(url):
    print(f"Processing new bill: {url}")
    result = store_html(url)
    return result

def process_all_unprocessed_html():
    while True:
        result = retreive_txt()
        if result is None:
            print("All records processed.")
            break
        time.sleep(1)  # Small delay between records

if __name__ == "__main__":
    # Option 1: Process a new URL (full pipeline: HTML → Text → Definitions)
    url = "https://www.congress.gov/bill/119th-congress/senate-bill/232/text"
    process_new_url(url)
    
    # Option 2: Process all existing unprocessed HTML records (Text → Definitions)
    # process_all_unprocessed_html()
    
    # Option 3: Process one unprocessed record
    # process_one_record()