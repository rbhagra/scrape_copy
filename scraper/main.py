from html_storer import store_html
from txt_storer import retreive_txt
from def_storer import store_defs
from dbconnection import create_connection
from mysql.connector import Error
from dotenv import load_dotenv
import os
import time

load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")
#### USED FOR LOCALIZED TESTING. DO NOT RUN FOR PIPELINE EXECUTION.
def process_new_url(url, allow_duplicates=False):
    """
    Process a new URL through the pipeline.
    
    Args:
        url: The URL to process
        allow_duplicates: If True, allows processing duplicate URLs/text. If False, skips duplicates.
    """
    print(f"Processing new bill: {url}")
    result = store_html(url, allow_duplicates=allow_duplicates)
    return result
def process_all_unprocessed_html():
    while True:
        result = retreive_txt()
        if result is None:
            print("All records processed.")
            break
        time.sleep(1)  # Small delay between records

def process_all_unprocessed_text():
    """Process all existing processed text records that haven't had definitions extracted yet"""
    connection = None
    cursor = None
    
    try:
        connection = create_connection(host, user, pw, database)
        cursor = connection.cursor()
        
        # Fetch ALL processed records that haven't had definitions extracted yet
        query = """
            SELECT p.id, p.clean_text, h.source_url
            FROM leg_processed p
            JOIN leg_html h ON p.raw_doc_id = h.search_id
            LEFT JOIN definitions d ON p.id = d.processed_doc_id
            WHERE d.processed_doc_id IS NULL
        """
        cursor.execute(query)
        all_records = cursor.fetchall()
        
        if not all_records:
            print("No processed text records found that need definition extraction.")
            return 0
        
        total = len(all_records)
        print(f"Found {total} processed text records to extract definitions from.\n")
        
        # Process each record
        count = 0
        for record in all_records:
            processed_doc_id, clean_text, source_url = record
            count += 1
            print(f"[{count}/{total}] Processing definitions for processed_doc_id: {processed_doc_id}...")
            
            # Call def_storer
            result = store_defs(processed_doc_id, clean_text, source_url)
            
            if result:
                print(f"✓ Stored {result} definitions\n")
            else:
                print("⚠ No definitions found for this record\n")
            
            time.sleep(1)  
        
        print(f"\n✓ Completed! Processed {count} out of {total} records.")
        return count
        
    except Error as e:
        print(f"✗ Error processing text records: {e}")
        return None
    finally:
        if connection and connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()

if __name__ == "__main__":
    # Configuration: set to true to allow duplicates or false to avoid them 
    ALLOW_DUPLICATES = True
    
    # Option 1: Process a new URL (full pipeline: HTML → Text → Definitions)
    url = "https://capitol.texas.gov/tlodocs/89R/billtext/pdf/HB00149I.pdf"
    process_new_url(url, allow_duplicates=ALLOW_DUPLICATES)
    
    # Option 2: Process all existing unprocessed HTML records (Text → Definitions)
    # process_all_unprocessed_html()
    
    # Option 3: Process all existing processed text records (Definitions extraction)
   # process_all_unprocessed_text() # needs to be fixed -- a lot. Definitions doesn't really work as intended.
    
    # Option 4: Process one unprocessed record
    # retreive_txt()