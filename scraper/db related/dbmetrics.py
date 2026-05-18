#use this function to run metrics on database

import mysql.connector
import csv
from datetime import datetime
import json
import argparse

from pathlib import Path
from dbconnection import create_connection
import os
from dotenv import load_dotenv
load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")
connection_setup = create_connection(host, user, pw, database)

def validate_config(config_path):
    print(f"Attempting to read config settings from {config_path}")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    #loading json into config
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")
    
    #check if metrics is set in config
    if "metrics" not in config:
        raise ValueError("'metrics' not found in config, running default database metrics")
    
    print("Config File successfully validated")
    return config

def load_config(config_path):

    config = validate_config(config_path)

    metrics_settings = config.get("metrics", {})

    #running db metrics with the settings from config
    print("Running metric analysis with config settings")
    dbmetrics(metrics_settings['type'], metrics_settings['phrase'])


def dbmetrics(type = "general", par = ""):
    try:
        #error catching if type is set but no parameter is set
        if type.lower() in ("link", "term") and not par:
            raise ValueError(f"'par' is required when type is '{type}'")
        
        #db connection
        print(f"Connecting to {database}...")
        connection = connection_setup
        cursor = connection.cursor()

        #setting names for metrics subfolder and file 
        PROJECTROOT = (Path(__file__).parent).parent


        output_folder =  os.path.join(PROJECTROOT,os.path.join("results", "metrics"))
        TIMESTAMP = (datetime.now()).strftime("%Y%m%d_%H%M%S")
        output_filename = f"{type}-{par}-{database}-metrics-{TIMESTAMP}"
        
        #checking for metrics subfolder in results
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
                
        #naming folder and setting path to subfolder

        output_filepath = os.path.join(output_folder, output_filename)

        #checking path already exists
        if os.path.isfile(output_filepath):
            raise RuntimeError("""
                                A metric already exists for this type, par, and time. 
                                Wait at least 1 second before trying again.
                                """)

        #default query, organizes all by both links and term groups
        if (type.lower() == "general"):
            query = """
                SELECT 
                    REGEXP_SUBSTR(search_term, '^"[^"]+"') AS first_phrase,
                    REGEXP_SUBSTR(search_term, 'site:[^ ]+') AS second_phrase,
                    COUNT(*) as term_frequency
                FROM leg_processed
                WHERE search_term LIKE '"%"%site:%' 
                AND search_term IS NOT NULL
                GROUP BY first_phrase, second_phrase
                ORDER BY second_phrase, term_frequency DESC;
                """
        #query creates ranked list of top terms by link
        elif (type.lower() == "link"):
            query = f"""
                SELECT 
                    REGEXP_SUBSTR(search_term, '^"[^"]+"') AS first_phrase,
                    COUNT(*) as term_frequency
                FROM leg_processed
                WHERE search_term LIKE '"%"%'
                    AND search_term LIKE '%{par}%'
                    AND search_term IS NOT NULL
                GROUP BY first_phrase
                ORDER BY term_frequency DESC;
                """
        elif (type.lower() == "term"):
            query = f"""
                SELECT 
                    REGEXP_SUBSTR(search_term, 'site:[^ ]+') AS first_phrase,
                    COUNT(*) as term_frequency
                FROM leg_processed
                WHERE search_term LIKE '"%"%'
                    AND search_term LIKE '%{par}%'
                    AND search_term IS NOT NULL
                GROUP BY first_phrase
                ORDER BY term_frequency DESC;
                """
        else:
            raise ValueError("Invalid type, try again")
        
        #executing query in db
        print(f"Tabulating {type} rankings")
        cursor.execute(query)

        #saving return of query
        rankings = cursor.fetchall()

        #writing results as csv file to folder
        print(f"Writing data to file {output_filepath}")
        with open(output_filepath, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            if type.lower() == "general":
                writer.writerow(["Search Term", "Site", "Frequency"])
            else:
                writer.writerow(["Phrase(s)", "Frequency"])

            writer.writerows(rankings)
        print(f"{len(rankings)} written to file")

    #connection error exception
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
    
    #incorrect input exception
    except ValueError as err:
        print(f"{err}")

    #closing any writing stuff left open
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()

#main function
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Run the databse scraper pipeline")

        parser.add_argument('--config', required=True, help="Path to your config.json file")

        args = parser.parse_args()

        #attempts to run metrics based off of json
        config = load_config(args.config)
    except:
        print("Running general metric analysis on database")
        dbmetrics()
    

