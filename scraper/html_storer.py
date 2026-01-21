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


def store_html(url, allow_duplicates=False): #stores html 
    connection = None
    cursor = None
    html_content = retrieve_html(url)
    if html_content is None:
        return None
    try:
        connection = create_connection(host, user, pw, database)
        cursor = connection.cursor()
        
        # Check if URL already exists in database, only check to avoid duplicates. Can work in more sophisticated checks.
        if not allow_duplicates: # runs check only if user decides to not allow duplicates. Duplicates likely allowed for versions of bills.
            check_query = "SELECT id FROM leg_html WHERE source_url = %s"
            cursor.execute(check_query, (url,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"Bill already exists in database (ID: {existing[0]}). Skipping duplicate.")
                return existing[0]
        
        insert_query = "INSERT INTO leg_html (source_url, raw_content) VALUES (%s, %s)"
        cursor.execute(insert_query, (url, html_content))
        connection.commit()
        html_id = cursor.lastrowid
        
        from txt_storer import retreive_txt
        retreive_txt(allow_duplicates=allow_duplicates)
        
        return html_id

    except Error as e:
        print(f"Error in database insertion: '{e}'")
        return None
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



