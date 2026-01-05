import requests
import mysql.connector
from mysql.connector import Error
from dbconnection import create_connection
from dotenv import load_dotenv
import os

load_dotenv()
pw = os.getenv("password")
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
    html_content = retrieve_html(url)
    try:
        connection = create_connection("localhost", "root", pw, "scraping")
        cursor = connection.cursor()
        insert_query = "INSERT INTO leg_html (source_url, raw_content) VALUES (%s, %s)"
        cursor.execute(insert_query, (url, html_content))
        connection.commit()
        return cursor.lastrowid

    except Error as e:
        print(f"Error in database insertion: '{e}'")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()



