import sqlite3
import os


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
#
#     search_link_id (Foreign Key): links to search_links.id (the search that discovered this URL)
#
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

def table_create(connection):
    """
    Creates tables based on the active database mode.
    """
    try:
        cursor = connection.cursor()

        # SQLite requires us to explicitly turn on Foreign Key enforcement
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # 1. leg_html (SQLite Dialect)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leg_html (
                search_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT NOT NULL,
                HTML TEXT,
                domain TEXT,
                num_tries INTEGER DEFAULT 0,
                num_failures INTEGER DEFAULT 0,
                failure_type TEXT,
                warnings TEXT,
                is_successful INTEGER DEFAULT 0,
                processing_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. search_links (SQLite Dialect)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_method TEXT NOT NULL,
                keyword_search TEXT NOT NULL,
                other_filters TEXT,
                link TEXT NOT NULL,
                processing_time REAL,
                num_api_tries INTEGER DEFAULT 0,
                num_api_failures INTEGER DEFAULT 0,
                failure_type TEXT,
                is_successful INTEGER DEFAULT 1,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. leg_processed (SQLite Dialect)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leg_processed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_doc_id INTEGER,
                source_url TEXT,
                clean_text TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                num_tries_text_processing INTEGER DEFAULT 0,
                num_failures_text_processing INTEGER DEFAULT 0,
                failure_type TEXT,
                text_processing_method TEXT,
                domain TEXT,
                warnings TEXT,
                is_successful INTEGER DEFAULT 0,
                processing_time REAL,
                search_link_id INTEGER,
                search_term TEXT,
                FOREIGN KEY (raw_doc_id) REFERENCES leg_html(search_id) ON DELETE CASCADE,
                FOREIGN KEY (search_link_id) REFERENCES search_links(id) ON DELETE SET NULL
            );
        """)

        # 4. definitions (SQLite Dialect)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                processed_doc_id INTEGER,
                term TEXT,
                definition_text TEXT,
                FOREIGN KEY (processed_doc_id) REFERENCES leg_processed(id) ON DELETE CASCADE
            );
        """)
        print("dbsetup: SQLite tables validated/created successfully.")

        # Commit the changes to the database!
        connection.commit()

    except Exception as e:
        print(f"Error: {e}")


#function to setup sqlite dbs that runs on the pipeline
def sqlite_setup():
    '''
    Checks to see if a db for the current job exists, if not, creates a new one based on SCRAPE_JOB_ID env var
    '''
    
    #creating job subfile path
    DB_FOLDER = "temp_dbs"

    job_id = os.getenv('SCRAPE_JOB_ID')
    if not job_id:
        raise ValueError("SQLite-related error: SCRAPE_JOB_ID not set in environment")

    db_filename = f"scrape_data_{job_id}.db"
    db_filepath = os.path.join(DB_FOLDER, db_filename)
  
    if not os.path.exists(db_filepath):
        #connect to file with sqlite (will automake new file if needed)
        connection = sqlite3.connect(db_filepath)

        #format table as needed
        table_create(connection)
    

