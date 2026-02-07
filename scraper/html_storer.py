import requests
import mysql.connector
from mysql.connector import Error
from dbconnection import create_connection
from dotenv import load_dotenv
import os

load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")
def retrieve_html(url):
    try:
        response = requests.get(url, timeout=15)
        html_content = response.text
        return html_content
    except Exception as e:
        print(f"Error retrieving HTML: {e}")
        return None


def _is_cloudflare_or_block_page(html_content):
    """
    Detect Cloudflare block/challenge or generic block pages in raw HTML.
    Returns error message string if blocked, None otherwise.
    """
    if not html_content:
        return None
    lower = html_content.lower()
    # Cloudflare block page indicators
    if "attention required" in lower and "cloudflare" in lower:
        return "Cloudflare: Attention required / block page (enable cookies or unblock)"
    if "you have been blocked" in lower:
        return "Cloudflare: You have been blocked (site security triggered)"
    if "cloudflare" in lower and ("ray id" in lower or "please enable cookies" in lower):
        return "Cloudflare: Block or challenge page detected"
    # Generic block
    if "blocked" in lower and "unable to access" in lower and len(html_content) < 15000:
        return "Scraper blocked: Unable to access (security/block page)"
    return None


def store_html(url, allow_duplicates=False, driver=None):
    """
    Returns dict: {"html_id": int or None, "warning": str or None, "error": str or None}
    
    Args:
        url: URL to fetch and store
        allow_duplicates: Whether to allow duplicate URLs
        driver: Optional existing WebDriver instance to reuse (avoids opening new browser windows)
    """
    connection = None
    cursor = None
    html_content = retrieve_html(url)
    # allows retries for retrireiving html
    max_retries = 2
    retry_count = 0
    while html_content is None and retry_count < max_retries:
        html_content = retrieve_html(url)
        retry_count += 1
    
    if html_content is None:
        return {"html_id": None, "warning": None, "error": "Failed to retrieve HTML after retries"}

    block_error = _is_cloudflare_or_block_page(html_content)
    if block_error:
        return {"html_id": None, "warning": None, "error": block_error}

    try:
        connection = create_connection(host, user, pw, database)
        cursor = connection.cursor()
        
        # Check if URL already exists in database
        if not allow_duplicates:
            check_query = "SELECT id FROM leg_html WHERE source_url = %s"
            cursor.execute(check_query, (url,))
            existing = cursor.fetchone()
            
            if existing:
                return {"html_id": existing[0], "warning": "Duplicate URL, using existing record", "error": None}
        
        insert_query = "INSERT INTO leg_html (source_url, raw_content) VALUES (%s, %s)"
        cursor.execute(insert_query, (url, html_content))
        connection.commit()
        html_id = cursor.lastrowid
        
        from txt_storer import retreive_txt
        txt_result = retreive_txt(allow_duplicates=allow_duplicates, html_id=html_id, driver=driver)
        
        # Capture warning and error from text extraction
        warning = None
        error = None
        if txt_result:
            if txt_result.get("warning"):
                warning = txt_result["warning"]
            # Check for block/access errors
            if txt_result.get("error"):
                error = txt_result["error"]
            elif not txt_result.get("success"):
                warning = txt_result.get("warning") or "Text extraction failed"
        
        return {"html_id": html_id, "warning": warning, "error": error}

    except Error as e:
        return {"html_id": None, "warning": None, "error": f"Database error: {e}"}
    finally:
        try:
            if cursor:
                # Consume any unread results before closing
                cursor.fetchall() if cursor.with_rows else None
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
        except:
            pass



