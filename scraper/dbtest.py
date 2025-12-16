import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("db_HOST"),
        port=int(os.getenv("db_PORT")),
        user=os.getenv("db_USER"),
        password=os.getenv("db_PASS"),
        database=os.getenv("db_NAME"),
        autocommit=True
    )
