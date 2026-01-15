from pydoc import text
from socket import create_connection
import mysql.connector
from mysql.connector import Error
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from bs4 import XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")

def retreive_txt(allow_duplicates=False):
    connection = None
    try:
        from dbconnection import create_connection
        connection = create_connection(host,user , pw, database)
        cursor = connection.cursor()
        query = """
        SELECT h.id, h.raw_content, h.source_url 
        FROM leg_html h
        LEFT JOIN leg_processed p ON h.id = p.raw_doc_id
        WHERE p.raw_doc_id IS NULL LIMIT 1
        """
        cursor.execute(query)
        result = cursor.fetchone()

        if not result:
            print("No more HTML to process")
            return None
        
        id_val, raw_content, source_url = result 
        soup = BeautifulSoup(raw_content, "lxml")  # assume LXML, but write a check with if statements to handle other formats and assign soup

        if "congress.gov" in source_url.lower(): #checks for congress.gov to utilize TXT feature via selenium. Else deafults to processing HTML via BS
            driver = webdriver.Firefox() #change if using chrome etc
            try: 
                driver.get(source_url)
                wait = WebDriverWait(driver, 2)
                text_tab = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "Text")))
                text_tab.click()

                txt_link = wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "TXT")))
                txt_link.click()
                time.sleep(2)
            except:
                pass 

            all_text = driver.find_element(By.TAG_NAME, "body").text
            start = "<DOC>"
            end ="<all>"
            if start in all_text and end in all_text:
                start_index = all_text.find(start)
                end_index = all_text.find(end)
                body = all_text[start_index : end_index]
                return store_txt(connection, id_val, body, source_url, allow_duplicates=allow_duplicates)
                driver.quit()

            return store_txt(connection, id_val, all_text, source_url, allow_duplicates=allow_duplicates)
            driver.quit()
        else:
            for junk in soup (["script", "style", "header", "footer", "nav"]):
                junk.decompose()
            cleaned_text = soup.get_text(separator= " ", strip= True)
            if "legislature.ca.gov" in source_url.lower(): # checks for ca bills in order to filter out preamble to bill 
                bill_start = "SECTION 1." # heuristic for start of bill 
                bill_start_index = cleaned_text.find(bill_start)
                cleaned_text_adjusted = cleaned_text[bill_start_index :]
                return store_txt(connection,id_val,cleaned_text_adjusted, source_url, allow_duplicates=allow_duplicates) # adds modified to database
            else:
                return store_txt(connection, id_val, cleaned_text, source_url, allow_duplicates=allow_duplicates)

    
    except Error as e:
        print(f"Error in database operations: {e}")
        return None
    finally:
        if connection and connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()
def store_txt(connection, raw_id, clean_text, source_url=None, allow_duplicates=False): # accepts duplicates flag to determine wheter to store text that already exists
    try: 
        cursor = connection.cursor()
        
        # Check if this raw_id already has processed text (avoid duplicate processing)
        if not allow_duplicates: # skips check if duplicates are allowed by user.
            check_query = "SELECT id FROM leg_processed WHERE raw_doc_id = %s"
            cursor.execute(check_query, (raw_id,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"Bill text already processed (processed_id: {existing[0]}). Skipping duplicate.")
                return existing[0]
        
        insert_query = "INSERT INTO leg_processed (raw_doc_id, clean_text) VALUES (%s, %s)"
        cursor.execute(insert_query, (raw_id,clean_text))
        connection.commit()
        processed_doc_id = cursor.lastrowid
        
        print("Bill text stored.")
        
        # Pipeline: After storing text, trigger definition extraction skip for now while def section in development

        # from def_storer import store_defs
        # store_defs(processed_doc_id, clean_text, source_url)
        
        return processed_doc_id

    except Exception as e:
        print(f"Error storing processed text: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

# NOTES: works for congress.gov. Needs exception handling and output processing for other sources (as it's just outputting soup output)
# returned value needs to be saved in database (table 2) and lastrow row id needs to be returned. Also make sure this traverses the 
# entire database. Changes on Jan 4. 




            




                
                
            