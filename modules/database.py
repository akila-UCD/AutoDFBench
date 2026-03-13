import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
    except mysql.connector.Error as err:
        print(f"DB error: {err}")
        return None


def get_ground_truth(
    base_test_case,
    file_name,
    sqlite_table_name=None,
    like_base=False,
    fetch_many=False,
    select_columns="*"
):
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)

        query = f"SELECT {select_columns} FROM ground_truth WHERE cftt_task='sqlite'"
        params = []

        if like_base:
            query += " AND base_test_case LIKE %s"
            params.append(base_test_case + "%")
        else:
            query += " AND base_test_case = %s"
            params.append(base_test_case)

        query += " AND file_name = %s"
        params.append(file_name)

        if sqlite_table_name:
            query += " AND sqlite_table_name = %s"
            params.append(sqlite_table_name)

        cursor.execute(query, tuple(params))
        result = cursor.fetchall() if fetch_many else cursor.fetchone()

        cursor.close()
        conn.close()
        return result

    except mysql.connector.Error as err:
        print(f"Query error: {err}")
        return None
