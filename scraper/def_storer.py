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
    
    if not text:
        return definitions
    
    # Try XML parsing first if text contains XML structure (for congress.gov XML bills)
    if source_url and "congress.gov" in source_url.lower():
        # Check if text contains XML tags
        if '<section>' in text or '<paragraph>' in text or '<header>' in text:
            try:
                soup = BeautifulSoup(text, "xml")
                if soup.find('section') or soup.find('paragraph'):
                    from alg import classify
                    result = classify(soup)
                    if isinstance(result, dict) and result:
                        return result
            except Exception as e:
                print(f"XML parsing failed: {e}")
                pass
    
    # Try to get raw_content from database if we have processed_doc_id and it might be XML
    # This handles cases where clean_text is plain text but raw_content has XML
    
    # Pattern-based regex searching for plain text definitions
    # More flexible patterns to catch various definition formats
    patterns = [
        r'"([^"]+)"\s+means\s+"([^"]+)"',  # "Term" means "Definition"
        r'"([^"]+)"\s+means\s+([^\.]+)',    # "Term" means definition.
        r'"([^"]+)"\s+means\s+([^;]+)',     # "Term" means definition;
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+means\s+"([^"]+)"',  # Term means "Definition"
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+means\s+([^\.]+)',   # Term means definition.
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+means\s+([^;]+)',   # Term means definition;
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+means\s+([^\n]+)',   # Term means definition\n
        r'\(([^)]+)\)\s+means\s+"([^"]+)"',  # (Term) means "Definition"
        r'\(([^)]+)\)\s+means\s+([^\.]+)',   # (Term) means definition.
        r'([A-Z][A-Za-z\s]+?)\s*[:–-]\s*([^\.]+)',  # Term: Definition or Term - Definition
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            term = match.group(1).strip()
            definition = match.group(2).strip()
            # Filter out invalid matches
            if term and definition and len(term) < 100 and len(definition) > 5:
                # Avoid duplicates
                if term not in definitions:
                    definitions[term] = definition
    
    return definitions

def store_defs(processed_doc_id, clean_text, source_url=None):
    connection = None
    cursor = None

    try:
        from dbconnection import create_connection
        connection = create_connection(host, user, pw, database)
        cursor = connection.cursor()
            
        # queries source URL and raw_content from database
        query = """
            SELECT h.source_url, h.raw_content
            FROM leg_processed p
            JOIN leg_html h ON p.raw_doc_id = h.id
            WHERE p.id = %s
        """
        cursor.execute(query, (processed_doc_id,))
        result = cursor.fetchone()
        if result:
            db_source_url = result[0]
            raw_content = result[1]
            # Use provided source_url if available, otherwise use from DB
            if source_url is None:
                source_url = db_source_url
        else:
            raw_content = None
        
        # Try extracting from clean_text first
        definitions_dict = extract_definitions_from_text(clean_text, source_url)
        
        # If no definitions found and we have raw_content, try extracting from raw_content (might be XML)
        if not definitions_dict and raw_content and source_url and "congress.gov" in source_url.lower():
            if '<section>' in raw_content or '<paragraph>' in raw_content:
                print(f"Trying XML extraction from raw_content for processed_doc_id: {processed_doc_id}")
                definitions_dict = extract_definitions_from_text(raw_content, source_url)
        
        if not definitions_dict:
            print(f"No definitions found for processed_doc_id: {processed_doc_id} (text length: {len(clean_text) if clean_text else 0})")
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

