"""
Utility functions for exporting database tables to CSV files.
"""
import csv
from mysql.connector import Error
import time



def export_table_to_csv(connection, table_name, output_path, columns=None, where_clause=None, params=None):
    """
    Export a database table to a CSV file
    
    Returns:
         Number of rows exported
    """
    cursor = None
    try:
        cursor = connection.cursor()
        
        # build sql query
        if columns:
            column_list = ", ".join(columns)
            query = f"SELECT {column_list} FROM {table_name}"
        else:
            query = f"SELECT * FROM {table_name}"
        
        # Add WHERE clause if provided
        if where_clause:
            query += f" WHERE {where_clause}"
        
        # Execute with parameters if provided
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        results = cursor.fetchall()
        
        # Get column names from cursor description
        if columns:
            column_names = columns
        else:
            column_names = [desc[0] for desc in cursor.description]
        
        # Write to CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(column_names)
            
            # Write data rows
            for row in results:
                writer.writerow(row)
        
        return len(results)
        
    except Error as e:
        print(f"Error exporting {table_name} to CSV: {e}")
        return None
    except IOError as e:
        print(f"Error writing CSV file {output_path}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()


def export_all_tables(connection, results_dir, html_ids=None):
    """
    Export all three main tables (leg_html, leg_processed, definitions) to CSV files.
    
    Args:
        connection: Database connection
        results_dir: Directory to save CSV files
        html_ids: List of HTML IDs to filter by (only export bills from this run)
    
    Returns:
        dict: Dictionary with table names as keys and row counts as values
    """
    exports = {}
    
    # Build WHERE clause for filtering by html_ids
    where_clause = None
    params = None
    if html_ids and len(html_ids) > 0:
        placeholders = ",".join(["%s"] * len(html_ids))
        html_where = f"id IN ({placeholders})"
        processed_where = f"raw_doc_id IN ({placeholders})"
        params = tuple(html_ids)
    
    # Export leg_html - including raw content
    html_path = f"{results_dir}/html_records.csv"
    html_count = export_table_to_csv(
        connection, 
        "leg_html", 
        html_path,
        columns=["id", "source_url", "raw_content", "created_at"],
        where_clause=html_where if html_ids else None,
        params=params if html_ids else None
    )
    exports["html_records"] = html_count
    
    # Export leg_processed 
    processed_path = f"{results_dir}/processed_text.csv"
    processed_count = export_table_to_csv(
        connection,
        "leg_processed",
        processed_path,
        columns=["id", "raw_doc_id", "clean_text", "processed_at"],
        where_clause=processed_where if html_ids else None,
        params=params if html_ids else None
    )
    exports["processed_text"] = processed_count
    ''' not using defs for now. 
    # Export definitions - need to join to get only definitions from this run's processed docs
    definitions_path = f"{results_dir}/definitions.csv"
    if html_ids and len(html_ids) > 0:
        # Custom query for definitions to filter by html_ids through processed docs
        cursor = connection.cursor()
        try:
            query = """
                SELECT d.id, d.processed_doc_id, d.term, d.definition_text
                FROM definitions d
                JOIN leg_processed p ON d.processed_doc_id = p.id
                WHERE p.raw_doc_id IN ({})
            """.format(placeholders)
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Write to CSV manually
            import csv
            with open(definitions_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["id", "processed_doc_id", "term", "definition_text"])
                for row in results:
                    writer.writerow(row)
            
            definitions_count = len(results)
            cursor.close()
        except Exception as e:
            print(f"Error exporting definitions: {e}")
            definitions_count = None
    else:
        definitions_count = export_table_to_csv(
            connection,
            "definitions",
            definitions_path,
            columns=["id", "processed_doc_id", "term", "definition_text"]
        )
    exports["definitions"] = definitions_count
    '''
    return exports
