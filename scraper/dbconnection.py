import mysql.connector
from mysql.connector import Error
import pandas as pd

def create_connection(host_name, user_name, password, database_name):
    try:
        connection = mysql.connector.connect(
           host=host_name,
            user=user_name,
            password=password,
            database=database_name
        )
        print("Connection established")

    except Error as e:
        print("Error while connecting to MySQL", e)

    return connection






