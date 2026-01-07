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


def store_html(url):
    connection = None
    cursor = None
    html_content = retrieve_html(url)
    if html_content is None:
        return None
    try:
        connection = create_connection(host, user, pw, database)
        cursor = connection.cursor()
        insert_query = "INSERT INTO leg_html (source_url, raw_content) VALUES (%s, %s)"
        cursor.execute(insert_query, (url, html_content))
        connection.commit()
        html_id = cursor.lastrowid
        
        from txt_storer import retreive_txt
        retreive_txt()
        
        return html_id

    except Error as e:
        print(f"Error in database insertion: '{e}'")
        return None
    finally:
        if connection and connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()



