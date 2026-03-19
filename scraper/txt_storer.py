from mysql.connector import Error
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from dotenv import load_dotenv
from error_codes import ErrorCode
import os
import io
import time
import warnings
import requests
import pymupdf
import pymupdf4llm
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from html_storer import is_federal_reg_url; from html_storer import extract_federal_reg_id
from detail_extract import congress_extract

warnings.filterwarnings("ignore", message=".*pymupdf_layout.*")
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

import json
import zipfile
from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
from adobe.pdfservices.operation.pdf_services import PDFServices
from adobe.pdfservices.operation.pdfjobs.jobs.extract_pdf_job import ExtractPDFJob
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_element_type import ExtractElementType
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_pdf_params import ExtractPDFParams
from adobe.pdfservices.operation.pdfjobs.result.extract_pdf_result import ExtractPDFResult

load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")
congress_api_key = os.getenv("congress_api_key")
adobe_client_id = os.getenv("adobe_client_id")
adobe_client_secret = os.getenv("adobe_client_secret")

# Minimum character threshold for valid bill text
MIN_BILL_TEXT_LENGTH = 500

def is_pdf_url(url):
    """
    Check if a URL points to a PDF file.
    Returns True if URL ends with .pdf or contains PDF indicators.
    """
    if not url:
        return False
    url_lower = url.lower()
    if url_lower.endswith('.pdf'):
        return True
    if '.pdf' in url_lower or 'format=pdf' in url_lower or 'type=pdf' in url_lower:
        return True
    return False

def remove_empty_lines(text):
    """
    Remove empty lines, lines with only whitespace, and lines with only numbers from text.
    
    Args:
        text: Input text with potential empty lines
    
    Returns:
        str: Text with empty/number-only lines removed
    """
    if not text:
        return text
    lines = text.split('\n')
    # keeping lines that have content 
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # skipping empty lines that are only numbers
        if stripped and not stripped.replace(' ', '').isdigit():
            cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)


def pdf_quality_check(text):
   # determines if previous extraction method was succesful via length and ratio of uknown chars.
    if not text or len(text.strip()) < MIN_BILL_TEXT_LENGTH:
        return False
    replacement_count = text.count(chr(0xFFFD))
    if replacement_count/len(text) > 0.3: # arbitrary treshold for unknown chars. Can be adjusted as needed.
        return False
    return True


def extract_text_from_pdf_adobe(pdf_bytes):
    #extracts using adobe pdf extract api -- limited to 500 docs per month
    if not adobe_client_id or not adobe_client_secret:
        print("Adobe PDF credentials not configured, skipping Adobe fallback")
        return None
    try:
        credentials = ServicePrincipalCredentials(
            client_id=adobe_client_id,
            client_secret=adobe_client_secret
        )
        pdf_services = PDFServices(credentials=credentials)

        input_asset = pdf_services.upload(
            input_stream=pdf_bytes,
            mime_type=PDFServicesMediaType.PDF
        )

        extract_params = ExtractPDFParams(
            elements_to_extract=[ExtractElementType.TEXT]
        )

        extract_job = ExtractPDFJob(input_asset=input_asset, extract_pdf_params=extract_params)
        location = pdf_services.submit(extract_job)
        pdf_result = pdf_services.get_job_result(location, ExtractPDFResult)

        result_asset = pdf_result.get_result().get_resource()
        stream_asset = pdf_services.get_content(result_asset)
        zip_bytes = stream_asset.get_input_stream()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            with zf.open("structuredData.json") as f:
                structured_data = json.loads(f.read())

        paragraphs = []
        for element in structured_data.get("elements", []):
            text = element.get("Text")
            if text:
                paragraphs.append(text)

        full_text = "\n".join(paragraphs)
        return remove_empty_lines(full_text) if full_text.strip() else None

    except Exception as e:
        print(f"Adobe PDF Extract API error: {e}")
        return None


def extract_text_from_pdf(url):
  
  #first tries pymupdf, then falls back to adobe if poor quality or timeout
    pdf_raw = None
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        pdf_raw = response.content
    except requests.RequestException as e:
        print(f"PDF download failed for {url}: {e}")
        return None

    try:
        pdf_bytes = io.BytesIO(pdf_raw)
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        md_text = pymupdf4llm.to_markdown(doc)
        cleaned_text = remove_empty_lines(md_text)
        if pdf_quality_check(cleaned_text):
            return cleaned_text
        print(f"PyMuPDF produced poor quality text for {url}, trying Adobe fallback")
    except Exception as e:
        print(f"PyMuPDF extraction failed for {url}: {e}, trying Adobe fallback")

    adobe_text = extract_text_from_pdf_adobe(pdf_raw)
    if adobe_text and len(adobe_text.strip()) > 0:
        return adobe_text

    return None

def _looks_like_document_url(url):
    """Check if a URL looks like it points to a document (PDF, DOCX, etc.)."""
    if not url:
        return False
    url_lower = url.lower()
    doc_extensions = ['.pdf', '.doc', '.docx', '.txt', '.rtf']
    for ext in doc_extensions:
        if ext in url_lower:
            return True
    doc_indicators = ['format=pdf', 'type=pdf', '/pdf/', '/document/', '/viewer/']
    for indicator in doc_indicators:
        if indicator in url_lower:
            return True
    return False


def get_embedded_document_url(soup, source_url):
    """
    Scan parsed HTML for embedded document viewers (iframe, embed, object).
    If a tag points to a document URL (PDF, etc.) or looks like a large content
    viewer, resolve and return the absolute URL.  Returns None otherwise.
    """
    # Pass 1: tags whose src/data clearly points to a document file
    for tag in soup.find_all("iframe"):
        src = tag.get("src", "")
        if src and _looks_like_document_url(src):
            return urljoin(source_url, src)

    for tag in soup.find_all("embed"):
        src = tag.get("src", "")
        if src and _looks_like_document_url(src):
            return urljoin(source_url, src)

    for tag in soup.find_all("object"):
        data = tag.get("data", "")
        if data and _looks_like_document_url(data):
            return urljoin(source_url, data)

    # Pass 2: iframes that look like content viewers (keyword or large size)
    for tag in soup.find_all("iframe"):
        src = tag.get("src", "")
        if not src:
            continue
        src_lower = src.lower()
        # Viewer-like URL keywords
        if any(kw in src_lower for kw in ["viewer", "document", "bill", "legislation", "text"]):
            return urljoin(source_url, src)
        # Large iframes are likely content viewers
        width = tag.get("width", "")
        height = tag.get("height", "")
        if width and height:
            try:
                w = int(str(width).replace("px", "").replace("%", ""))
                h = int(str(height).replace("px", "").replace("%", ""))
                if w >= 400 and h >= 400:
                    return urljoin(source_url, src)
            except ValueError:
                pass

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

def pload_url(url, driver, max_retries=3):
    # loads url with up to 3 retries, creates new driver for each retry
    for attempt in range(max_retries):
        try:
            driver.set_page_load_timeout(10) 
            driver.get(url)
            return driver
        except TimeoutException:
            print(f"Attempt {attempt + 1}/{max_retries} timeout for {url}, creating new driver...")
            time.sleep(2)
            if attempt < max_retries - 1:  # not last attempt
                try:
                    driver.quit()
                    driver = webdriver.Firefox()
                except Exception as driver_e:
                    print(f"Failed to create new driver: {driver_e}")
                    return driver
        except Exception:
            print(f"Attempt {attempt + 1}/{max_retries} failed to load URL: {url}")
            time.sleep(2)
            if attempt < max_retries - 1:  # not last attempt
                try:
                    driver.quit()
                    driver = webdriver.Firefox()
                except Exception as driver_e:
                    print(f"Failed to create new driver: {driver_e}")
                    return driver
    return driver

def check_text_for_block(text):
    """
    Check if extracted text indicates the page was blocked.
    
    Returns:
        tuple: (ErrorCode, str) - error code and message, or (None, None) if no block detected
    """
    if not text:
        return None, None
    text_lower = text.lower()
    
    if "cloudflare" in text_lower and "ray id" in text_lower:
        return ErrorCode.CLOUDFLARE_ATTENTION_REQUIRED, "BLOCKED: Cloudflare protection"
    if ("you have been blocked" in text_lower or "attention required" in text_lower) and "cloudflare" in text_lower:
        return ErrorCode.CLOUDFLARE_ATTENTION_REQUIRED, "BLOCKED: Cloudflare security"
    
    if "the request could not be satisfied" in text_lower and "error" in text_lower:
        return ErrorCode.SCRAPER_BLOCKED, "BLOCKED: Request could not be satisfied"
    if "you have been blocked" in text_lower or "attention required" in text_lower:
        return ErrorCode.ACCESS_DENIED, "BLOCKED: Access denied by website security"
    if "access denied" in text_lower and len(text) < 2000:
        return ErrorCode.ACCESS_DENIED, "BLOCKED: Access denied"
    
    return None, None


def fetch_with_selenium(source_url, driver=None): #general selenium function for fetching text from page, not specific to congress.gov. More robust than beautifulsoup to attempt to assure accuracy.
    """
    Use Selenium to fetch page content after JavaScript has rendered.
    Returns the page text or None if failed.
    
    Args:
        source_url: URL to fetch
        driver: Optional existing WebDriver instance to reuse
    """
    owns_driver = driver is None
    try:
        if owns_driver:
            driver = webdriver.Firefox()
        driver = pload_url(source_url, driver)
        
        wait = WebDriverWait(driver, 10)
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

        # Iframe fallback: if main page still has little content, look inside iframes
        if len(bill_text) < MIN_BILL_TEXT_LENGTH:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    if not iframe.is_displayed():
                        continue
                    iframe_src = iframe.get_attribute("src") or ""
                    # If the iframe src is itself a PDF, skip (handled elsewhere)
                    if is_pdf_url(iframe_src):
                        continue
                    driver.switch_to.frame(iframe)
                    iframe_text = driver.find_element(By.TAG_NAME, "body").text.strip()
                    driver.switch_to.default_content()
                    if len(iframe_text) > len(bill_text):
                        bill_text = iframe_text
                except Exception:
                    try:
                        driver.switch_to.default_content()
                    except Exception:
                        pass
                    continue

        return bill_text
        
    except Exception as e:
        print(f"Selenium error: {e}")
        return None
    finally:
        # Only quit driver if we created it
        if owns_driver and driver:
            driver.quit()

def retreive_txt(allow_duplicates=False, html_id=None, driver=None, search_link_id=None):
    """
    Returns dict with: {"success": bool, "processed_id": int or None, "warning": str or None}
    
    Args:
        allow_duplicates: Whether to allow duplicate processing
        html_id: Specific HTML record ID to process
        driver: Optional existing WebDriver instance to reuse (avoids opening new browser windows)
        search_link_id: Optional search_links.id that discovered this URL
    """
    connection = None
    warning = None
    owns_driver = False  # Track if we created the driver
    start_time = time.time()
    num_tries = 0
    num_failures = 0
    try:
        from dbconnection import create_connection
        connection = create_connection(host,user , pw, database)
        cursor = connection.cursor()
        
        # If specific html_id provided, process that record
        if html_id:
            query = """
            SELECT h.search_id, h.HTML, h.source_url 
            FROM leg_html h
            WHERE h.search_id = %s
            """
            cursor.execute(query, (html_id,))
        else:
            # Fallback: find any unprocessed HTML
            query = """
            SELECT h.search_id, h.HTML, h.source_url 
            FROM leg_html h
            LEFT JOIN leg_processed p ON h.search_id = p.raw_doc_id
            WHERE p.raw_doc_id IS NULL LIMIT 1
            """
            cursor.execute(query)
        
        result = cursor.fetchone()

        if not result:
            return {"success": False, "processed_id": None, "warning": "No HTML to process", "error_code": ErrorCode.UNKNOWN_ERROR.value, "extraction_method": None}
        
        id_val, raw_content, source_url = result
        domain = urlparse(source_url).netloc.removeprefix("www.")
        
        # Early block detection on raw HTML before any extraction attempt
        block_code, block_error = check_text_for_block(raw_content)
        if block_code:
            processing_time = round(time.time() - start_time, 3)
            store_txt(connection, id_val, None, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                      domain=domain, num_tries=num_tries, num_failures=num_failures + 1,
                      failure_type=block_code.value, text_processing_method=None,
                      is_successful=0, processing_time=processing_time)
            return {"success": False, "processed_id": None, "warning": None, "error": block_error,
                    "error_code": block_code.value, "stage": "text_extraction", "extraction_method": None}
        
        # Check if URL is a PDF - try PDF extraction first
        if is_pdf_url(source_url):
            num_tries += 1
            pdf_text = extract_text_from_pdf(source_url)
            if pdf_text and len(pdf_text.strip()) > 0:
                if not pdf_quality_check(pdf_text):
                    num_failures += 1
                    processing_time = round(time.time() - start_time, 3)
                    store_txt(connection, id_val, None, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                        domain=domain, num_tries=num_tries, num_failures=num_failures,
                        failure_type=ErrorCode.PDF_EXTRACTION_FAILED.value, text_processing_method="pdf",
                        is_successful=0, processing_time=processing_time)
                    return {"success": False, "processed_id": None, "warning": None,
                            "error": "PDF could not be parsed correctly with any method",
                            "error_code": ErrorCode.PDF_EXTRACTION_FAILED.value, "extraction_method": "pdf"}
                processing_time = round(time.time() - start_time, 3)
                processed_id = store_txt(connection, id_val, pdf_text, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                    domain=domain, num_tries=num_tries, num_failures=num_failures,
                    text_processing_method="pdf", processing_time=processing_time)
                return {"success": processed_id is not None, "processed_id": processed_id, "warning": None, 
                        "error_code": None if processed_id else ErrorCode.DATABASE_ERROR.value, "extraction_method": "pdf"}
            else:
                num_failures += 1
                warning = f"PDF extraction failed for {source_url}, fell back to normal parsing"
        
        soup = BeautifulSoup(raw_content, "lxml")  # assume LXML, but write a check with if statements to handle other formats and assign soup

        # Check for embedded document viewers (iframe/embed/object pointing to a document URL)
        embedded_url = get_embedded_document_url(soup, source_url)
        if embedded_url:
            if is_pdf_url(embedded_url):
                num_tries += 1
                pdf_text = extract_text_from_pdf(embedded_url)
                if pdf_text and len(pdf_text.strip()) > 0:
                    if not pdf_quality_check(pdf_text):
                        num_failures += 1
                        processing_time = round(time.time() - start_time, 3)
                        store_txt(connection, id_val, None, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                            domain=domain, num_tries=num_tries, num_failures=num_failures,
                            failure_type=ErrorCode.PDF_EXTRACTION_FAILED.value, text_processing_method="embedded_pdf",
                            is_successful=0, processing_time=processing_time)
                        return {"success": False, "processed_id": None, "warning": None,
                                "error": "PDF could not be parsed correctly with any method",
                                "error_code": ErrorCode.PDF_EXTRACTION_FAILED.value, "extraction_method": "embedded_pdf"}
                    processing_time = round(time.time() - start_time, 3)
                    processed_id = store_txt(connection, id_val, pdf_text, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                        domain=domain, num_tries=num_tries, num_failures=num_failures,
                        warnings_text=f"Extracted text from embedded PDF: {embedded_url}",
                        text_processing_method="embedded_pdf", processing_time=processing_time)
                    return {"success": processed_id is not None, "processed_id": processed_id,
                            "warning": f"Extracted text from embedded PDF: {embedded_url}",
                            "error_code": None if processed_id else ErrorCode.DATABASE_ERROR.value,
                            "extraction_method": "embedded_pdf"}
                else:
                    num_failures += 1
                    warning = f"Embedded PDF extraction failed for {embedded_url}, falling back to normal parsing"
            else:
                num_tries += 1
                try:
                    embed_resp = requests.get(embedded_url, timeout=30)
                    embed_resp.raise_for_status()
                    embed_soup = BeautifulSoup(embed_resp.text, "lxml")
                    for junk in embed_soup.find_all(["script", "style", "header", "footer", "nav"]):
                        junk.decompose()
                    embed_text = embed_soup.get_text(separator=" ", strip=True)
                    if len(embed_text) >= MIN_BILL_TEXT_LENGTH:
                        processing_time = round(time.time() - start_time, 3)
                        processed_id = store_txt(connection, id_val, embed_text, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                            domain=domain, num_tries=num_tries, num_failures=num_failures,
                            warnings_text=f"Extracted text from embedded document: {embedded_url}",
                            text_processing_method="embedded_doc", processing_time=processing_time)
                        return {"success": processed_id is not None, "processed_id": processed_id,
                                "warning": f"Extracted text from embedded document: {embedded_url}",
                                "error_code": None if processed_id else ErrorCode.DATABASE_ERROR.value,
                                "extraction_method": "embedded_doc"}
                    else:
                        num_failures += 1
                        warning = f"Embedded doc at {embedded_url} had little text, falling back to normal parsing"
                except Exception:
                    num_failures += 1
                    warning = f"Could not fetch embedded doc at {embedded_url}, falling back to normal parsing"

        if "congress.gov" in source_url.lower():
            num_tries += 1
            try:
                congress_num, bill_type, bill_number = congress_extract(source_url.lower())
                api_url = f"https://api.congress.gov/v3/bill/{congress_num}/{bill_type}/{bill_number}/text?format=json&api_key={congress_api_key}"
                response = requests.get(api_url)
                data = response.json()
                VERSION_PRIORITY = ["Enrolled Bill", "Public Law", "Engrossed in House", "Engrossed in Senate",
                                    "Reported to House", "Reported to Senate",
                                    "Placed on Calendar Senate", "Placed on Calendar House",
                                    "Introduced in House", "Introduced in Senate"]
                pdf_url = None
                for preferred in VERSION_PRIORITY:
                    for version in data.get("textVersions", []):
                        if version.get("type") == preferred:
                            for fmt in version.get("formats", []):
                                if fmt.get("type") == "PDF":
                                    pdf_url = fmt["url"]
                                    break
                        if pdf_url:
                            break
                    if pdf_url:
                        break
                htm_url = None
                for preferred in VERSION_PRIORITY:
                    for version in data.get("textVersions", []):
                        if version.get("type") == preferred:
                            for fmt in version.get("formats", []):
                                if fmt.get("type") == "Formatted Text":
                                    htm_url = fmt["url"]
                                    break
                        if htm_url:
                            break
                    if htm_url:
                        break
                if not htm_url:
                    for version in data.get("textVersions", []):
                        for fmt in version.get("formats", []):
                            if fmt.get("type") == "Formatted Text":
                                htm_url = fmt["url"]
                                break
                        if htm_url:
                            break
                if htm_url:
                    htm_response = requests.get(htm_url)
                    if htm_response.status_code == 200:
                        soup = BeautifulSoup(htm_response.text, "html.parser")
                        htm_text = soup.get_text(separator="\n", strip=True)
                        if htm_text and len(htm_text.strip()) > 0:
                            processing_time = round(time.time() - start_time, 3)
                            processed_id = store_txt(connection, id_val, htm_text, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                                domain=domain, num_tries=num_tries, num_failures=num_failures,
                                text_processing_method="Congress.gov API (HTM)", processing_time=processing_time)
                            return {"success": processed_id is not None, "processed_id": processed_id, "warning": None,
                                    "error_code": None if processed_id else ErrorCode.DATABASE_ERROR.value, "extraction_method": "Congress.gov API (HTM)"}
                        else:
                            num_failures += 1
                            warning = f"HTM/API extraction failed for {source_url}, falling back to selenium based text storing"
                    else:
                        num_failures += 1
                        warning = f"HTM fetch returned {htm_response.status_code} for {htm_url}, falling back to selenium based text storing"
                else:
                    num_failures += 1
                    warning = f"No HTM URL found via Congress API for {source_url}, falling back to selenium"
            except Exception as e:
                num_failures += 1
                warning = f"Congress API extraction failed for {source_url} ({e}), falling back to selenium"
        
            num_tries += 1
            if driver is None:
                driver = webdriver.Firefox()
                owns_driver = True
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
            end_1 = "<All>"
            end_2 = "<Attest:>"

            if start in all_text:
                start_index = all_text.find(start)

                end_candidates = []
                if end_1 in all_text:
                    end_idx = all_text.find(end_1, start_index)
                    if end_idx != -1:
                        end_candidates.append(end_idx)
                if end_2 in all_text:
                    end_idx = all_text.find(end_2, start_index)
                    if end_idx != -1:
                        end_candidates.append(end_idx)

                if end_candidates:
                    end_index = max(end_candidates)
                    body = all_text[start_index:end_index]
                else:
                    body = all_text[start_index:]

                body = remove_empty_lines(body)
                processing_time = round(time.time() - start_time, 3)
                processed_id = store_txt(connection, id_val, body, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                    domain=domain, num_tries=num_tries, num_failures=num_failures,
                    warnings_text=warning, text_processing_method="congress_selenium", processing_time=processing_time)
                return {
                    "success": processed_id is not None,
                    "processed_id": processed_id,
                    "warning": warning,
                    "error_code": None if processed_id else ErrorCode.DATABASE_ERROR.value,
                    "extraction_method": "congress_selenium",
                }

            all_text = remove_empty_lines(all_text)
            processing_time = round(time.time() - start_time, 3)
            processed_id = store_txt(connection, id_val, all_text, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                domain=domain, num_tries=num_tries, num_failures=num_failures,
                warnings_text=warning, text_processing_method="congress_selenium", processing_time=processing_time)
            return {"success": processed_id is not None, "processed_id": processed_id, "warning": warning,
                    "error_code": None if processed_id else ErrorCode.DATABASE_ERROR.value,
                    "extraction_method": "congress_selenium"}
        if is_federal_reg_url(source_url):
            num_tries += 1
            federal_reg_id = extract_federal_reg_id(source_url)
            if not federal_reg_id:
                num_failures += 1
                print(f"Could not extract document number from Federal Register URL: {source_url}")
                processing_time = round(time.time() - start_time, 3)
                store_txt(connection, id_val, None, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                          domain=domain, num_tries=num_tries, num_failures=num_failures,
                          failure_type=ErrorCode.UNKNOWN_ERROR.value, text_processing_method="Federal Register API",
                          is_successful=0, processing_time=processing_time)
                return {"success": False, "processed_id": None, "warning": None, "error": "Could not extract Federal Register document ID",
                        "error_code": ErrorCode.UNKNOWN_ERROR.value, "stage": "text_extraction", "extraction_method": None}
            api_url = f"https://www.federalregister.gov/api/v1/documents/{federal_reg_id}.json?fields[]=raw_text_url"
            api_response = requests.get(api_url, timeout=15)
            if api_response.status_code != 200:
                num_failures += 1
                print(f"Federal Register API returned status {api_response.status_code}")
                processing_time = round(time.time() - start_time, 3)
                store_txt(connection, id_val, None, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                          domain=domain, num_tries=num_tries, num_failures=num_failures,
                          failure_type=ErrorCode.NETWORK_REQUEST_FAILED.value, text_processing_method="Federal Register API",
                          is_successful=0, processing_time=processing_time)
                return {"success": False, "processed_id": None, "warning": None, "error": f"Federal Register API returned {api_response.status_code}",
                        "error_code": ErrorCode.NETWORK_REQUEST_FAILED.value, "stage": "text_extraction", "extraction_method": None}
            data = api_response.json()
            raw_text_url = data.get("raw_text_url")
            if not raw_text_url:
                num_failures += 1
                print(f"Federal Register API did not return raw_text_url for {federal_reg_id}")
                processing_time = round(time.time() - start_time, 3)
                store_txt(connection, id_val, None, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                          domain=domain, num_tries=num_tries, num_failures=num_failures,
                          failure_type=ErrorCode.UNKNOWN_ERROR.value, text_processing_method="Federal Register API",
                          is_successful=0, processing_time=processing_time)
                return {"success": False, "processed_id": None, "warning": None, "error": "No raw_text_url in API response",
                        "error_code": ErrorCode.UNKNOWN_ERROR.value, "stage": "text_extraction", "extraction_method": None}
            text_response = requests.get(raw_text_url, timeout=15)
            if text_response.status_code != 200:
                num_failures += 1
                processing_time = round(time.time() - start_time, 3)
                store_txt(connection, id_val, None, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                          domain=domain, num_tries=num_tries, num_failures=num_failures,
                          failure_type=ErrorCode.NETWORK_REQUEST_FAILED.value, text_processing_method="Federal Register API",
                          is_successful=0, processing_time=processing_time)
                return {"success": False, "processed_id": None, "warning": None,
                        "error": f"Failed to fetch raw text: HTTP {text_response.status_code}",
                        "error_code": ErrorCode.NETWORK_REQUEST_FAILED.value, "stage": "text_extraction", "extraction_method": None}
            body_text = text_response.text
            if len(body_text) >= MIN_BILL_TEXT_LENGTH:
                start_index = body_text.find("<html>")
                end_index = body_text.find("</html>")
                if start_index != -1 and end_index != -1:
                    body_text = body_text[start_index:end_index]
                processing_time = round(time.time() - start_time, 3)
                processed_id = store_txt(connection, id_val, body_text, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                    domain=domain, num_tries=num_tries, num_failures=num_failures,
                    warnings_text=warning, text_processing_method="Federal Register API", processing_time=processing_time)
                return {"success": processed_id is not None, "processed_id": processed_id, "warning": warning,
                        "error_code": None if processed_id else ErrorCode.DATABASE_ERROR.value,
                        "extraction_method": "Federal Register API"}
            num_failures += 1
            processing_time = round(time.time() - start_time, 3)
            store_txt(connection, id_val, None, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                      domain=domain, num_tries=num_tries, num_failures=num_failures,
                      failure_type=ErrorCode.INSUFFICIENT_TEXT.value, text_processing_method="Federal Register API",
                      is_successful=0, processing_time=processing_time)
            return {"success": False, "processed_id": None, "warning": "Federal Register body had insufficient text",
                    "error_code": ErrorCode.INSUFFICIENT_TEXT.value, "extraction_method": "Federal Register API"}

        # For all other sites, first try BeautifulSoup, then check if content is dynamically loaded
        else:
            num_tries += 1
            soup_copy = BeautifulSoup(raw_content, "lxml")
            
            for junk in soup.find_all(["script", "style", "header", "footer", "nav"]):
                junk.decompose()
            cleaned_text = soup.get_text(separator=" ", strip=True)
            
            needs_selenium = is_dynamically_loaded(raw_content, soup_copy)
            
            if len(cleaned_text) < MIN_BILL_TEXT_LENGTH:
                needs_selenium = True
            
            extraction_method = "beautifulsoup"
            
            if needs_selenium:
                num_failures += 1
                num_tries += 1
                selenium_text = fetch_with_selenium(source_url, driver=driver)
                
                block_code, block_error = check_text_for_block(selenium_text)
                if block_code:
                    num_failures += 1
                    processing_time = round(time.time() - start_time, 3)
                    store_txt(connection, id_val, None, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                              domain=domain, num_tries=num_tries, num_failures=num_failures,
                              failure_type=block_code.value, text_processing_method="selenium",
                              is_successful=0, processing_time=processing_time)
                    return {"processed_id": None, "warning": None, "error": block_error, "error_code": block_code.value, 
                            "stage": "text_extraction", "extraction_method": "selenium"}

                if selenium_text and len(selenium_text) > len(cleaned_text):
                    cleaned_text = selenium_text
                    extraction_method = "selenium"
                else:
                    num_failures += 1
                    if not warning:
                        warning = "Selenium fallback did not improve text extraction results"
            
            if "legislature.ca.gov" in source_url.lower():
                bill_start = "SECTION 1."
                bill_start_index = cleaned_text.find(bill_start)
                if bill_start_index != -1:
                    cleaned_text = cleaned_text[bill_start_index:]

            if is_pdf_url(source_url) and not pdf_quality_check(cleaned_text): #checks pdf qaulity even if falls back to selenium/ BS parsing
                num_failures += 1
                processing_time = round(time.time() - start_time, 3)
                store_txt(connection, id_val, None, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                    domain=domain, num_tries=num_tries, num_failures=num_failures,
                    failure_type=ErrorCode.PDF_EXTRACTION_FAILED.value, text_processing_method=extraction_method,
                    is_successful=0, processing_time=processing_time)
                return {"success": False, "processed_id": None, "warning": None,
                        "error": "PDF could not be parsed correctly with any method",
                        "error_code": ErrorCode.PDF_EXTRACTION_FAILED.value, "extraction_method": extraction_method}

            processing_time = round(time.time() - start_time, 3)
            processed_id = store_txt(connection, id_val, cleaned_text, source_url, allow_duplicates=allow_duplicates, search_link_id=search_link_id,
                domain=domain, num_tries=num_tries, num_failures=num_failures,
                warnings_text=warning, text_processing_method=extraction_method, processing_time=processing_time)
            return {"success": processed_id is not None, "processed_id": processed_id, "warning": warning,
                    "error_code": None if processed_id else ErrorCode.DATABASE_ERROR.value,
                    "extraction_method": extraction_method}

    
    except Error as e:
        return {"success": False, "processed_id": None, "warning": f"Database error: {e}", "error_code": ErrorCode.DATABASE_ERROR.value, "extraction_method": None}
    finally:
        try: # handles unread results from query for duplicates, occurs when duplicate allowed once and multiple ids accesible for each URL
            # Only quit driver if we created it ourselves
            if owns_driver and driver:
                driver.quit()
            if cursor:
                # Consume any unread results before closing
                cursor.fetchall() if cursor.with_rows else None
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
        except:
            pass

def store_txt(connection, raw_id, clean_text, source_url=None, allow_duplicates=False,
              domain=None, num_tries=0, num_failures=0, failure_type=None,
              warnings_text=None, text_processing_method=None, processing_time=None,
              is_successful=1, search_link_id=None):
    try: 
        cursor = connection.cursor()

        # If we have the search_link_id, fetch the originating search query text.
        # This lets us later join leg_processed -> search_links and export search_term.
        search_term = None
        if search_link_id is not None:
            cursor.execute(
                "SELECT keyword_search FROM search_links WHERE id = %s",
                (search_link_id,),
            )
            row = cursor.fetchone()
            if row:
                search_term = row[0]
        
        if not allow_duplicates:
            check_query = "SELECT id FROM leg_processed WHERE raw_doc_id = %s"
            cursor.execute(check_query, (raw_id,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"Bill text already processed (processed_id: {existing[0]}). Skipping duplicate.")
                return existing[0]
        
        insert_query = """INSERT INTO leg_processed 
            (raw_doc_id, source_url, clean_text, domain, num_tries_text_processing, 
             num_failures_text_processing, failure_type, warnings, text_processing_method, 
             is_successful, processing_time, search_link_id, search_term) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(
            insert_query,
            (
                raw_id,
                source_url,
                clean_text,
                domain,
                num_tries,
                num_failures,
                failure_type,
                warnings_text,
                text_processing_method,
                is_successful,
                processing_time,
                search_link_id,
                search_term,
            ),
        )
        connection.commit()
        processed_doc_id = cursor.lastrowid
        
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
