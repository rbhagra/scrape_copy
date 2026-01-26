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
        response = requests.get(url)
        html_content = response.text
        return html_content
    except Exception as e:
        print(f"Error retrieving HTML: {e}")
        return None


def store_html(url, allow_duplicates=False):
    """
    Returns dict: {"html_id": int or None, "warning": str or None, "error": str or None}
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
        txt_result = retreive_txt(allow_duplicates=allow_duplicates, html_id=html_id)
        
        # Capture warning from text extraction
        warning = None
        if txt_result:
            if txt_result.get("warning"):
                warning = txt_result["warning"]
            if not txt_result.get("success"):
                warning = txt_result.get("warning") or "Text extraction failed"
        
        return {"html_id": html_id, "warning": warning, "error": None}

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



