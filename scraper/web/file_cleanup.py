from flask import Flask, g
import os
import time

#mapping DB relative path
DB_FOLDER = "temp_db"
DB_FILEPATH = os.path.join(__file__, os.pardir, os.pardir, os.pardir, DB_FOLDER)

def file_cleanup():
    """Scans temp_dbs folder and deletes all files that have been untouched for >1 day"""

    #folder existence check
    if not os.path.exists(DB_FILEPATH):
        return

    #Loop through files and delete ones that are too old
    for filename in os.listdir(DB_FILEPATH):
        filepath = os.path.join(DB_FILEPATH, filename)

        if os.path.isfile(filepath):

            #check time of last modification
            file_age = time.time() - os.path.getmtime(filepath)

            #deleting file if age is greater than a day
            if file_age > 86400:
                try:
                    os.remove(filepath)
                    print(f"Garbage Collector: Deleted expired file {filename}")
                
                except Exception as e:
                    print(f"Garbage Collector: Failed to delete {filename} - {e}")

if __name__ == '__main__':
    print(os.path.abspath(DB_FILEPATH))