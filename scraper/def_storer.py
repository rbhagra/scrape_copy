from mysql.connector import Error
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import re

load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")
# LOGIC: If congress .gov, use previous algorithm, otherwise use regex searching of TXT. Can change this to also use regex for congress
def extract_definitions_from_text(text, source_url=None):
    definitions = {}
    
    # Only use classify function for congress.gov bills
    if source_url and "congress.gov" in source_url.lower():
        try:
            soup = BeautifulSoup(text, "xml")
            if soup.find('section') or soup.find('paragraph'):
                from alg import classify
                result = classify(soup)
                if isinstance(result, dict):
                    return result
        except:
            pass
    
  #pattern-based regex searching
    patterns = [
        r'"([^"]+)"\s+means\s+"([^"]+)"',  # "Term" means "Definition"
        r'"([^"]+)"\s+means\s+([^\.]+)',    # "Term" means definition.
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+means\s+"([^"]+)"',  # Term means "Definition"
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+means\s+([^\.]+)',   # Term means definition.
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            term = match.group(1).strip()
            definition = match.group(2).strip()
            if term and definition and len(term) <  75: # check on length
                definitions[term] = definition
    
    return definitions

def store_defs(processed_doc_id, clean_text, source_url=None):
    connection = None
    cursor = None
    
    try:
        from dbconnection import create_connection
        connection = create_connection(host, user, pw, database)
        cursor = connection.cursor()
        
        # queries source URL if not provided
        if source_url is None:
            query = """
                SELECT h.source_url 
                FROM leg_processed p
                JOIN leg_html h ON p.raw_doc_id = h.id
                WHERE p.id = %s
            """
            cursor.execute(query, (processed_doc_id,))
            result = cursor.fetchone()
            if result:
                source_url = result[0]
        
        definitions_dict = extract_definitions_from_text(clean_text, source_url)
        
        if not definitions_dict:
            print(f"No definitions found for processed_doc_id: {processed_doc_id}")
            return None
        insert_query = "INSERT INTO definitions (processed_doc_id, term, definition_text) VALUES (%s, %s, %s)"
        stored_count = 0
        
        for term, definition_text in definitions_dict.items():
            try:
                cursor.execute(insert_query, (processed_doc_id, term, definition_text))
                stored_count += 1
            except Exception as e:
                print(f"Error storing definition for term '{term}': {e}")
                continue
        
        connection.commit()
        print(f"Stored {stored_count} definitions for processed_doc_id: {processed_doc_id}")
        return stored_count
        
    except Error as e:
        print(f"Error in definition extraction/storage: {e}")
        return None
    finally:
        if connection and connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()

