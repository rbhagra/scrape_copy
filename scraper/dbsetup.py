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

        # 2. search discovery table (created before leg_processed due to FK dependency)
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

        # 3. table for processed legislation
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
                        search_link_id INT,
                        search_term VARCHAR(1000),
                        FOREIGN KEY (raw_doc_id) REFERENCES leg_html(search_id) ON DELETE CASCADE,
                        FOREIGN KEY (search_link_id) REFERENCES search_links(id) ON DELETE SET NULL
                    ) ENGINE=InnoDB;
                """)

        # 4. defs table
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS definitions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        processed_doc_id INT,
                        term VARCHAR(255),
                        definition_text TEXT,
                        FOREIGN KEY (processed_doc_id) REFERENCES leg_processed(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB;
                """)

        # --- Schema migration for existing DBs ---
        # helps migrate old dbs
        """ INTERNAL USE, FIXING CURRENT DB """
        try:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'leg_processed'
                  AND COLUMN_NAME = 'search_link_id'
                """,
                (database,),
            )
            has_col = cursor.fetchone()[0] > 0
            if not has_col:
                print("dbsetup: adding missing leg_processed.search_link_id column")
                cursor.execute("ALTER TABLE leg_processed ADD COLUMN search_link_id INT NULL")
                connection.commit()
            else:
                print("dbsetup: leg_processed.search_link_id already exists")

            # Ensure FK constraint exists (best-effort; may already exist).
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.REFERENTIAL_CONSTRAINTS rc
                WHERE rc.CONSTRAINT_NAME = 'fk_leg_processed_search_link_id'
                """
            )
            fk_exists = cursor.fetchone()[0] > 0
            if not fk_exists:
                print("dbsetup: adding FK fk_leg_processed_search_link_id")
                cursor.execute(
                    "ALTER TABLE leg_processed "
                    "ADD CONSTRAINT fk_leg_processed_search_link_id "
                    "FOREIGN KEY (search_link_id) REFERENCES search_links(id) "
                    "ON DELETE SET NULL"
                )
                connection.commit()
            else:
                print("dbsetup: FK fk_leg_processed_search_link_id already exists")

            # Add index on search_links.link for fast dedup lookups
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'search_links'
                  AND INDEX_NAME = 'idx_search_links_link'
                """,
                (database,),
            )
            has_link_idx = cursor.fetchone()[0] > 0
            if not has_link_idx:
                print("dbsetup: adding index idx_search_links_link")
                cursor.execute("CREATE INDEX idx_search_links_link ON search_links(link)")
                connection.commit()
         

            # Add leg_processed.search_term for existing DBs
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = 'leg_processed'
                  AND COLUMN_NAME = 'search_term'
                """,
                (database,),
            )
            has_search_term_col = cursor.fetchone()[0] > 0
            if not has_search_term_col:
                print("dbsetup: adding missing leg_processed.search_term column")
                cursor.execute("ALTER TABLE leg_processed ADD COLUMN search_term VARCHAR(1000) NULL")
                connection.commit()
            else:
                print("dbsetup: leg_processed.search_term already exists")
        except Error as e:
            print(f"dbsetup: schema migration best-effort failed: {e}")


    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    table_create()
