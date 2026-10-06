# autodfbench/db_dfr.py
import os
import sys
from autodfbench.database import get_db_connection as _storage_connection, Error as DBError
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


def get_db_connection():
    """SQLite storage (see autodfbench/database.py)."""
    return _storage_connection()


def insert_result_to_db(base_test_case, testcase, tp, fp, fn, precision, recall, f1):
    conn = get_db_connection()
    if conn is None:
        return

    try:
        cursor = conn.cursor()
        insert_query = """
            INSERT INTO test_results (base_test_case, testCase, job_id, TP, FP, FN, `precision`, `recall`, F1)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (base_test_case, testcase, "0", tp, fp, fn, precision, recall, f1))
        conn.commit()
        cursor.close()
        conn.close()
    except DBError:
        try:
            conn.close()
        except Exception:
            pass


def get_ground_truth_paths(base_test_case):
    """
    Returns rows:
    0:file_name, 1:deleted_time_stamp, 2:modify_time_stamp, 3:access_time_stamp,
    4:change_time_stamp, 5:block_count, 6:size, 7:dfr_blocks
    """
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor()
        query = """
            SELECT file_name, deleted_time_stamp, modify_time_stamp, access_time_stamp, change_time_stamp, block_count, size, dfr_blocks
            FROM ground_truth
            WHERE LOWER(base_test_case) = LOWER(%s)
              AND cftt_task = 'deleted_file_recovery'
              AND type = 'deleted'
        """
        cursor.execute(query, (base_test_case,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except DBError:
        try:
            conn.close()
        except Exception:
            pass
        return None
