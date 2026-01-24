from pydoc import text
from selenium.webdriver.firefox.webdriver import WebDriver
from socket import create_connection
from typing import Any
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
import requests
import io
import pymupdf
import pymupdf4llm
from selenium.common.exceptions import TimeoutException
import logging
logger = logging.getLogger(__name__)
try:
    import PyPDF2
    PDF_LIB_AVAILABLE = True
except ImportError:
    try:
        import pdfplumber
        PDF_LIB_AVAILABLE = True
    except ImportError:
        PDF_LIB_AVAILABLE = False
        print("Warning: NO PDF LIBRARY FOUND")

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")

# Minimum character threshold for valid bill text
MIN_BILL_TEXT_LENGTH = 500

def is_pdf_url(url):
    """
    Check if a URL points to a PDF file.
    Returns True if URL ends with .pdf or contains PDF indicators.
    """
    url_lower = url.lower()
    # Check file extension
    if url_lower.endswith('.pdf'):
        return True
    # Check URL parameters that might indicate PDF
    if '.pdf' in url_lower or 'format=pdf' in url_lower or 'type=pdf' in url_lower:
        return True
    return False

def extract_text_from_pdf(url):
    """
    Download PDF from URL and extract clean text using pymupdf4llm.
    
    Args:
        url: URL to the PDF file (must end with .pdf)
    
    Returns:
        str: Clean text extracted from the PDF
    """
    try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            pdf_bytes = io.BytesIO(response.content)
            # Open with pymupdf first using stream parameter
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            md_text = pymupdf4llm.to_markdown(doc)
            return md_text
    except requests.RequestException as e:
            print(f"Error downloading PDF: {e}")
            return None

def is_dynamically_loaded(raw_content, soup):
    """
    Detect if a page loads  bill content dynamically.
    Returns true if the page may need selenium to fetch content.
    """
    # Check 1: Look for JavaScript that loads content dynamically
    js_loading_indicators = [
        'loadBillJSON',           # Utah
        'loadContent',            # Generic
        'fetchBillText',          # Generic
        'getBillData',            # Generic
        'ajax',                   # jQuery AJAX calls
        '$.get(',                 # jQuery GET
        '$.post(',                # jQuery POST
        'fetch(',                 # Modern fetch API
        'XMLHttpRequest',         # XHR
        'document.ready',         # jQuery ready with dynamic content
        'componentDidMount',      # React
        'mounted()',              # Vue
        'ngOnInit',               # Angular
    ]
    
    for indicator in js_loading_indicators:
        if indicator.lower() in raw_content.lower():
            # filter out analytics js
            script_tags = soup.find_all('script')
            for script in script_tags:
                script_text = script.string or ''
                if indicator.lower() in script_text.lower():
                    # indicates js that loads content dynamically
                    return True
    
    # Check 2: Empty content containers that should have bill text
    empty_container_ids = ['billbox', 'bill-text', 'billText', 'bill-content', 'legislation-text', 'main-content']
    for container_id in empty_container_ids:
        container = soup.find(id=container_id)
        if container:
            container_text = container.get_text(strip=True)
            if len(container_text) < 100:  
                return True
            # checks for mistmatch between html and text in terms of length.
        body = soup.find('body')
    if body:
        # Remove scripts and styles for text check
        for tag in body.find_all(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        body_text = body.get_text(strip=True)
        
        # If body has lots of HTML structure but little text, likely dynamic
        html_length = len(raw_content)
        text_length = len(body_text)
        
        # If HTML is large but text is small, content is probably loaded dynamically
        if html_length > 4000 and text_length < MIN_BILL_TEXT_LENGTH:
            return True
    
    return False

def load_url(url, driver, max_retries=3):
    # loads url with up to 3 retries, creates new driver for each retry
    for attempt in range(max_retries):
        try:
            driver.set_page_load_timeout(10) 
            driver.get(url)
            return driver
        except TimeoutException as e:
            logger.error(f"Attempt {attempt + 1}/{max_retries} timeout for {url}, creating new driver...")
            time.sleep(2)
            if attempt < max_retries - 1:  # not last attempt
                try:
                    driver.quit()
                    driver = webdriver.Firefox()
                except Exception as driver_e:
                    logger.error(f"Failed to create new driver: {driver_e}")
                    return driver
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}/{max_retries} failed to load URL: {url}", exc_info=True)
            time.sleep(2)
            if attempt < max_retries - 1:  # not last attempt
                try:
                    driver.quit()
                    driver = webdriver.Firefox()
                except Exception as driver_e:
                    logger.error(f"Failed to create new driver: {driver_e}")
                    return driver
    return driver

def fetch_with_selenium(source_url): #general selenium function for fetching text from page, not specific to congress.gov. More robust than beautifulsoup to attempt to assure accuracy.
    """
    Use Selenium to fetch page content after JavaScript has rendered.
    Returns the page text or None if failed.
    """
    driver = None
    try:
        driver = webdriver.Firefox()
        driver = load_url(source_url, driver)
        
        wait = WebDriverWait[Any | WebDriver](driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # wait for page load 
        time.sleep(2)
        
        # searching containers 
        bill_text = ""
        
        # List of common bill content container IDs/classes to check
        content_selectors = [
            (By.ID, "billbox"),
            (By.ID, "bill-text"),
            (By.ID, "billText"),
            (By.ID, "bill-content"),
            (By.ID, "legislation-text"),
            (By.ID, "main-content"),
            (By.CLASS_NAME, "bill-text"),
            (By.CLASS_NAME, "legislation-content"),
            (By.TAG_NAME, "article"),
        ]
        
        for selector_type, selector_value in content_selectors:
            try:
                element = driver.find_element(selector_type, selector_value)
                element_text = element.text.strip()
                if len(element_text) > len(bill_text):
                    bill_text = element_text
            except:
                continue
        
        # full body text if not found in container
        if len(bill_text) < MIN_BILL_TEXT_LENGTH:
            bill_text = driver.find_element(By.TAG_NAME, "body").text
        
        return bill_text
        
    except Exception as e:
        print(f"Selenium error: {e}")
        return None
    finally:
        if driver:
            driver.quit()

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
        
        # Check if URL is a PDF - try PDF extraction first
        if is_pdf_url(source_url):
            print("scraping text via pdf")
            pdf_text = extract_text_from_pdf(source_url)
            if pdf_text and len(pdf_text.strip()) > 0:
                return store_txt(connection, id_val, pdf_text, source_url, allow_duplicates=allow_duplicates)
            else:
                print(f"PDF extraction failed for {source_url}, falling back to normal parsing...")
        
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
            driver.quit()
            start = "<DOC>"
            end ="<all>"
            if start in all_text and end in all_text:
                start_index = all_text.find(start)
                end_index = all_text.find(end)
                body = all_text[start_index : end_index]
                return store_txt(connection, id_val, body, source_url, allow_duplicates=allow_duplicates)

            return store_txt(connection, id_val, all_text, source_url, allow_duplicates=allow_duplicates)
        
        # For all other sites, first try BeautifulSoup, then check if content is dynamically loaded
        else:
            # Create a copy of soup for detection (original soup will be modified)
            soup_copy = BeautifulSoup(raw_content, "lxml")
            
            # Remove junk tags for text extraction
            for junk in soup.find_all(["script", "style", "header", "footer", "nav"]):
                junk.decompose()
            cleaned_text = soup.get_text(separator=" ", strip=True)
            
            # Check if content appears to be dynamically loaded
            needs_selenium = is_dynamically_loaded(raw_content, soup_copy)
            
            # Also check if extracted text is too short (likely incomplete), both pass to selenimum 
            if len(cleaned_text) < MIN_BILL_TEXT_LENGTH:
                needs_selenium = True
            
            # pass to general selenium extractor. 
            if needs_selenium:
                selenium_text = fetch_with_selenium(source_url)
                
                if selenium_text and len(selenium_text) > len(cleaned_text):
                    cleaned_text = selenium_text
                else:
                    print(f"Altenative method for dybamic loading did not improve results, using original text.")
            
            # Site-specific post-processing
            if "legislature.ca.gov" in source_url.lower():
                bill_start = "SECTION 1."
                bill_start_index = cleaned_text.find(bill_start)
                if bill_start_index != -1:
                    cleaned_text = cleaned_text[bill_start_index:]
        
            
            return store_txt(connection, id_val, cleaned_text, source_url, allow_duplicates=allow_duplicates)

    
    except Error as e:
        print(f"Error in database operations: {e}")
        return None
    finally:
        try: # handles unread results from query for duplicates, occurs when duplicate allowed once and multiple ids accesible for each URL

            if cursor:
                # Consume any unread results before closing
                cursor.fetchall() if cursor.with_rows else None
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
        except:
            pass

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
    finally: #ensures cursor is closed even with thrown error for duplicates
        try:
            if cursor:
                cursor.fetchall() if cursor.with_rows else None
                cursor.close()
        except:
            pass

# NOTES: works for congress.gov. Needs exception handling and output processing for other sources (as it's just outputting soup output)
# returned value needs to be saved in database (table 2) and lastrow row id needs to be returned. Also make sure this traverses the 
# entire database. Changes on Jan 4. 




            




                
                
            