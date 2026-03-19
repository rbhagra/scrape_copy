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
#     HTML: full html
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
# 4. search_links
#
# tracks URLs discovered via search APIs (e.g. SERP API)
#     id (Primary Key): unique ID per discovered link
#
#     search_method: how the link was found (e.g. "SERPAPI")
#
#     keyword_search: the full query string sent to the search engine
#
#     other_filters: serialized URL filters applied after search
#
#     link: the discovered URL
#
#     processing_time: seconds taken by the SERP API call that found this link
#
#     num_api_tries: how many SERP API attempts were made for this query
#
#     num_api_failures: how many of those attempts failed
#
#     failure_type: error code if the search failed
#
#     is_successful: 1 if the link was accepted after filtering, 0 otherwise
#
#     discovered_at: timestamp of discovery
#
#
def table_create():
    connection = connection_setup
    try:
        cursor = connection.cursor()
        #1 table for unprocessed HTML
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS leg_html (
                        search_id INT AUTO_INCREMENT PRIMARY KEY,
                        source_url VARCHAR(500) NOT NULL,
                        HTML LONGTEXT,
                        domain VARCHAR(255),
                        num_tries INT DEFAULT 0,
                        num_failures INT DEFAULT 0,
                        failure_type VARCHAR(100),
                        warnings VARCHAR(2480),
                        is_successful TINYINT DEFAULT 0,
                        processing_time DECIMAL(10,3),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB;
                """)

        # table for processed legislation
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS leg_processed (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        raw_doc_id INT,
                        source_url VARCHAR(500),
                        clean_text LONGTEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        num_tries_text_processing INT DEFAULT 0,
                        num_failures_text_processing INT DEFAULT 0,
                        failure_type VARCHAR(1000),
                        text_processing_method VARCHAR(1000),
                        domain VARCHAR(200),
                        warnings VARCHAR(2480),
                        is_successful TINYINT DEFAULT 0,
                        processing_time DECIMAL(10,3),
                        FOREIGN KEY (raw_doc_id) REFERENCES leg_html(search_id) ON DELETE CASCADE
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

        # 4. search discovery table
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS search_links (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        search_method VARCHAR(100) NOT NULL,
                        keyword_search VARCHAR(1000) NOT NULL,
                        other_filters VARCHAR(1000),
                        link VARCHAR(500) NOT NULL,
                        processing_time DECIMAL(10,3),
                        num_api_tries INT DEFAULT 0,
                        num_api_failures INT DEFAULT 0,
                        failure_type VARCHAR(100),
                        is_successful TINYINT DEFAULT 1,
                        discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB;
                """)


    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    table_create()
