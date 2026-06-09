import mysql.connector
from mysql.connector import Error
import os
import sqlite3
from flask import Flask, session

def create_connection(host_name="", user_name="", password="", database_name="", dbtype="sqlite"):
    connection = None
    #creating connection to our normal mysql db
    if (dbtype == "mysql"):

        #creating connection
        try:
            connection = mysql.connector.connect(
                host=host_name,
                user=user_name,
                password=password,
                database=database_name
            )
        except Error as e:
            print(f"Error while connecting to MySQL: {e}")
            return None
    #db_type not set to mysql defaults to an sqlite style database
    else:
        
        #grabbing userid
        if 'user_id' not in session:
            NameError("SQLite-related error: user_id not generated")

        current_user = session['user_id']

        
        #making folder and subfile
        DB_FOLDER = "temp_dbs"

        db_filename = f"scrape_data_{current_user}.db"
        db_filepath = os.path.join(DB_FOLDER, db_filename)

        #connection to sqlite
        try:
            connection = sqlite3.connect(db_filepath)
        except Error as e:
            print(f"Error while connecting to SQLite: {e}")
            return None

    return connection


