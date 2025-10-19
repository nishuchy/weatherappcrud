# models/db.py
import psycopg2
from config import DB_CONFIG
from flask import request
import requests
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)





def update_weather_info(location, date, temp_max, temp_min, description, weatherid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
               UPDATE tbl_weather
               SET location=%s, date=%s, temp_max=%s, temp_min=%s, description=%s
               WHERE weatherid=%s
           """, (location, date, temp_max, temp_min, description, weatherid))
    conn.commit()
    cur.close()
    conn.close()


def weather_base_info(weatherid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM tbl_weather WHERE weatherid=%s', (weatherid,))
    row = cur.fetchall()  # fetchone() returns single tuple
    cur.close()
    conn.close()
    return row


def delete_weather(weatherid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tbl_weather WHERE weatherid=%s", (weatherid,))
    conn.commit()
    cur.close()
    conn.close()





def insert_update_user(fullname, username, userpassword,  user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    if user_id:
        #  Proper UPDATE query with WHERE clause
        cur.execute("""
            UPDATE tbl_user 
            SET username = %s, password = %s, fullname = %s 
            WHERE user_id = %s
        """, (username, userpassword,  fullname, user_id))
        message = "Update successfully!"
    else:
        #  Correct INSERT query with 4 placeholders
        cur.execute("SELECT COUNT(0) FROM tbl_user WHERE username = %s"  , (username,))
        user_count = cur.fetchone()[0]
        if user_count > 0:
            message = "User role already exists!"
        else:
            cur.execute("""
                INSERT INTO tbl_user (username, password,  fullname) 
                VALUES (%s, %s, %s)
            """, (username, userpassword,  fullname))
            message = "Saved successfully!"

    conn.commit()
    cur.close()
    conn.close()

    return message




def fetch_history():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tbl_weather WHERE userid = %s", (int(request.cookies.get("user_id")),))
    rows = cur.fetchall()

    return rows