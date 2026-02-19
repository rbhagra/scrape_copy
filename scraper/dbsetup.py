from mysql.connector import Error
from dbconnection import create_connection
import os
from dotenv import load_dotenv
load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")
connection_setup = create_connection(host, user, pw, database)


# 1. leg_html
#
# Ingestion layer to save information scraped from the internet
#
#     id (Primary Key): currently integer to mark each scraped bill.
#
#     source_url: The direct link where the document was found.
#
#     raw_content: full html
#
#     created_at: timestamp of scrape
#
# 2. leg_processed
#
# refined layer top store plain text
#
#     id (Primary Key): id for processed legislation
#
#     raw_doc_id (Foreign Key): direct link to ingestion layer
#
#     clean_text: plain text of bill
#
#     processed_at: timestamp
# 3. definitions
#
# storing extracted defs
#     id (Primary Key): unique ID for the def .
#
#     processed_doc_id (Foreign Key): links to processed id.
#
#     term: specific term
#
#     definition_text:  definition
#
#
def table_create():
    connection = connection_setup
    try:
        cursor = connection.cursor()
        #1 table for unprocessed HTML
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS leg_html (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        source_url VARCHAR(2048) NOT NULL,
                        raw_content LONGTEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB;
                """)

        # table for processed legislation
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS leg_processed (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        raw_doc_id INT,
                        clean_text LONGTEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (raw_doc_id) REFERENCES leg_html(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB;
                """)

        # 3. defs table
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS definitions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        processed_doc_id INT,
                        term VARCHAR(255),
                        definition_text TEXT,
                        FOREIGN KEY (processed_doc_id) REFERENCES leg_processed(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB;
                """)


    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()