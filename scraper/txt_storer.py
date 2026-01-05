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


load_dotenv()
pw = os.getenv("password")

def retreive_txt():
    connection = None
    try:
        from dbconnection import create_connection
        connection = create_connection("localhost", "root", pw, "scraping")
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
        soup = BeautifulSoup(raw_content, "lxml")  # assume LXML, but write a check with IF statements to handle other formats and assign soup

        if "congress.gov" in source_url.lower(): # otherwise we need to apply the previous scraping ALG, just pick up everything
            driver = webdriver.Firefox()
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
                return store_txt(connection, id_val, body)
                driver.quit()

            return store_txt(connection, id_val, all_text)
            driver.quit()
        else:
            for junk in soup (["script", "style", "header", "footer", "nav"]):
                junk.decompose()
            cleaned_text = soup.get_text(separator= " ", strip= True)
            return store_txt(connection, id_val,cleaned_text)

    
    except Error as e:
        print(f"Error in database operations: {e}")
        return None
    finally:
        if connection and connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()
def store_txt(connection, raw_id, clean_text):
    try: 
        cursor = connection.cursor()
        insert_query = "INSERT INTO leg_processed (raw_doc_id, clean_text) VALUES (%s, %s)"
        cursor.execute(insert_query, (raw_id,clean_text))
        connection.commit()
        return cursor.lastrowid

    except Exception as e:
        print(f"Error storing processed text: {e}")
    finally:
        if cursor:
            cursor.close()

# if __name__ == "__main__":
#     while True:
        
#         result =  retreive_txt()
        
#         if result is None:
#             print("All bills have been processed")
#             break
#         time.sleep(1)


## NOTES: works for congress.gov. Needs exception handling and output processing for other sources (as it's just outputting soup output)
## returned value needs to be saved in database (table 2) and lastrow row id needs to be returned. Also make sure this traverses the 
## entire database. Changes on Jan 4. 




            




                
                
            