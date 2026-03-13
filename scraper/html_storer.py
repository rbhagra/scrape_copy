import requests
import re
import time
from urllib.parse import urlparse
from mysql.connector import Error
from dbconnection import create_connection
from error_codes import ErrorCode
from dotenv import load_dotenv
import os

load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")
congress_api_key = os.getenv("congress_api_key")


def is_federal_reg_url(url):

    return "federalregister.gov/documents/" in url


def is_congress_url(url):
    return "congress.gov/bill/" in url.lower()


VERSION_PRIORITY = [
    "Enrolled Bill", "Public Law", "Engrossed in House", "Engrossed in Senate",
    "Reported to House", "Reported to Senate",
    "Placed on Calendar Senate", "Placed on Calendar House",
    "Introduced in House", "Introduced in Senate",
]


def retrieve_congress_html(url):
    """Fetch the HTM-formatted bill text via the Congress API."""
    from detail_extract import congress_extract
    try:
        congress_num, bill_type, bill_number = congress_extract(url.lower())
        api_url = f"https://api.congress.gov/v3/bill/{congress_num}/{bill_type}/{bill_number}/text?format=json&api_key={congress_api_key}"
        response = requests.get(api_url, timeout=15)
        if response.status_code != 200:
            print(f"Congress API returned status {response.status_code}")
            return None
        data = response.json()

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

        if not htm_url:
            print(f"No Formatted Text URL found via Congress API for {url}")
            return None

        htm_response = requests.get(htm_url, timeout=15)
        if htm_response.status_code == 200:
            return htm_response.text

        print(f"Failed to fetch HTM from Congress API: status {htm_response.status_code}")
        return None

    except Exception as e:
        print(f"Error fetching from Congress API: {e}")
        return None


def extract_federal_reg_id(url):
    """
    extracts the document number from the url
    """ 
    if "federalregister.gov/documents/" not in url:
        return None
    # path is .../documents/YYYY/MM/DD/DOC-ID/
    path = url.split("federalregister.gov/documents/")[-1]
    parts = path.split("/")
    if len(parts) >= 4:
        return parts[3]  
    return None


def retrieve_federal_reg_html(url):
 #fetches HTML content using Federal Register API
    doc_id = extract_federal_reg_id(url)
    if not doc_id:
        print(f"Could not extract document number from Federal Register URL: {url}")
        return None

    api_url = f"https://www.federalregister.gov/api/v1/documents/{doc_id}.json?fields[]=body_html_url"
    try:
        response = requests.get(api_url, timeout=15)
        if response.status_code != 200:
            print(f"Federal Register API returned status {response.status_code}")
            return None

        data = response.json()
        html_url = data.get("body_html_url")
        if not html_url:
            print(f"Federal Register API did not return body_html_url for {doc_id}")
            return None

        html_response = requests.get(html_url, timeout=15)
        if html_response.status_code == 200:
            return html_response.text

        print(f"Failed to fetch HTML from body_html_url: status {html_response.status_code}")
        return None

    except Exception as e:
        print(f"Error fetching from Federal Register API: {e}")
        return None


def retrieve_html(url, timeout=15):
    try:
        response = requests.get(url, timeout=15)
        html_content = response.text
        return html_content
    except Exception as e:
        print(f"Error retrieving HTML: {e}")
        return None


def classify_block_error(html_content):
    """
    Detect Cloudflare block/challenge or generic block pages in raw HTML.
    
    Returns:
        tuple: (ErrorCode, str) - error code and human-readable message, or (None, None) if no block detected
    """
    if not html_content:
        return None, None
    lower = html_content.lower()
    
    
    if "_cf_chl_opt" in lower or "/cdn-cgi/challenge-platform/" in lower:
        return ErrorCode.CLOUDFLARE_ATTENTION_REQUIRED, "Blocked by clouflare)"
    
    # Cloudflare explicit block pages
    if "attention required" in lower and "cloudflare" in lower:
        return ErrorCode.CLOUDFLARE_ATTENTION_REQUIRED, "Cloudflare: Attention required / block page (enable cookies or unblock)"
    if "you have been blocked" in lower and "cloudflare" in lower:
        return ErrorCode.CLOUDFLARE_ATTENTION_REQUIRED, "Cloudflare: You have been blocked (site security triggered)"
    if "cloudflare" in lower and ("ray id" in lower or "please enable cookies" in lower):
        return ErrorCode.CLOUDFLARE_ATTENTION_REQUIRED, "Cloudflare: Block or challenge page detected"
    
    # non-cloudflare block, just based on searching text content
    if "the request could not be satisfied" in lower and "error" in lower:
        return ErrorCode.SCRAPER_BLOCKED, "Scraping blocked: Request could not be satisfied"
    if "blocked" in lower and "unable to access" in lower and len(html_content) < 15000:
        return ErrorCode.SCRAPER_BLOCKED, "Scraper blocked: Unable to access (security/block page)"
    
    return None, None


def store_html(url, allow_duplicates=False, driver=None):
    """
    Returns dict: {"html_id": int or None, "warning": str or None, "error": str or None, "stage": str}

    Args:
        url: URL to fetch and store
        allow_duplicates: Whether to allow duplicate URLs
        driver: Optional existing WebDriver instance to reuse
    """
    connection = None
    cursor = None
    start_time = time.time()
    domain = urlparse(url).netloc.removeprefix("www.")

    from txt_storer import is_pdf_url
    timeout = 100 if is_pdf_url(url) else 15
    
    if is_congress_url(url):
        html_content = retrieve_congress_html(url)
        max_retries = 1
    elif is_federal_reg_url(url):
        html_content = retrieve_federal_reg_html(url)
        max_retries = 1
    else:
        html_content = retrieve_html(url, timeout=timeout)
        max_retries = 2
    
    retry_count = 0
    while html_content is None and retry_count < max_retries:
        if is_congress_url(url):
            html_content = retrieve_congress_html(url)
        elif is_federal_reg_url(url):
            html_content = retrieve_federal_reg_html(url)
        else:
            html_content = retrieve_html(url, timeout=timeout)
        retry_count += 1

    num_tries = 1 + retry_count
    num_failures = retry_count if html_content is not None else num_tries

    if html_content is None:
        return {"html_id": None, "warning": None, "error": "Failed to retrieve HTML after retries", "error_code": ErrorCode.NETWORK_REQUEST_FAILED.value, "stage": "html_fetch", "extraction_method": None}

    error_code, error_msg = classify_block_error(html_content)
    if error_code:
        return {"html_id": None, "warning": None, "error": error_msg, "error_code": error_code.value, "stage": "html_fetch", "extraction_method": None}

    try:
        connection = create_connection(host, user, pw, database)
        cursor = connection.cursor()

        if not allow_duplicates:
            check_query = "SELECT search_id FROM leg_html WHERE source_url = %s"
            cursor.execute(check_query, (url,))
            existing = cursor.fetchone()

            if existing:
                return {"html_id": existing[0], "warning": "Duplicate URL, using existing record", "error": None, "error_code": ErrorCode.DUPLICATE_SKIPPED.value, "stage": "complete", "extraction_method": None}

        insert_query = "INSERT INTO leg_html (source_url, HTML, domain, num_tries, num_failures) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(insert_query, (url, html_content, domain, num_tries, num_failures))
        connection.commit()
        html_id = cursor.lastrowid

        from txt_storer import retreive_txt
        txt_result = retreive_txt(allow_duplicates=allow_duplicates, html_id=html_id, driver=driver)

        warning = None
        error = None
        error_code = None
        extraction_method = None
        stage = "complete"
        failure_type = None
        if txt_result:
            if txt_result.get("warning"):
                warning = txt_result["warning"]
            extraction_method = txt_result.get("extraction_method")
            if txt_result.get("error"):
                error = txt_result["error"]
                error_code = txt_result.get("error_code")
                failure_type = error_code
                stage = "text_extraction"
            elif not txt_result.get("success"):
                warning = txt_result.get("warning") or "Text extraction failed"
                error_code = txt_result.get("error_code")
                failure_type = error_code
                stage = "text_extraction"

        processing_time = round(time.time() - start_time, 3)
        try:
            update_query = "UPDATE leg_html SET processing_time = %s, warnings = %s, failure_type = %s WHERE search_id = %s"
            cursor.execute(update_query, (processing_time, warning, failure_type, html_id))
            connection.commit()
        except Error:
            pass

        return {"html_id": html_id, "warning": warning, "error": error, "error_code": error_code, "stage": stage, "extraction_method": extraction_method}

    except Error as e:
        return {"html_id": None, "warning": None, "error": f"Database error: {e}", "error_code": ErrorCode.DATABASE_ERROR.value, "stage": "html_fetch", "extraction_method": None}
    finally:
        try:
            if cursor:
                cursor.fetchall() if cursor.with_rows else None
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
        except:
            pass
