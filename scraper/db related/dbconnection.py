import mysql.connector
from mysql.connector import Error


def create_connection(host_name, user_name, password, database_name):
    connection = None
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

    return connection


