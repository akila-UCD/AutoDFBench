# autodfbench/db_windows_registry.py
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

def get_db_connection():
    """Establish database connection"""
    try:
        kwargs = dict(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        # Optional port parsing (robust)
        if DB_PORT is not None:
            s = str(DB_PORT).strip()
            if s and s.lower() != "none":
                kwargs["port"] = int(s)
        return mysql.connector.connect(**kwargs)
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None
    except Exception as err:
        print(f"Database connection error: {err}")
        return None

def get_configs(conf_value):
    """Get configuration value from config table"""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM config WHERE `type` = %s"
        cursor.execute(query, (conf_value,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results[0] if results else None
    except mysql.connector.Error as err:
        print(f"Config query error: {err}")
        return None

def get_ground_truth_paths(base_test_case):
    """Get ground truth file paths for a test case"""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor()
        query = """
            SELECT * FROM ground_truth 
            WHERE base_test_case = %s AND cftt_task = 'windows_registry'
        """
        cursor.execute(query, (base_test_case,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except mysql.connector.Error as err:
        print(f"Ground truth query error: {err}")
        return None

def insert_result_to_db(base_test_case, testcase, job_id, tp, fp, fn, precision, recall, f1):
    """Insert test results into database"""
    try:
        conn = get_db_connection()
        if conn is None:
            return False

        cursor = conn.cursor()
        insert_query = """
            INSERT INTO test_results (base_test_case, testCase, job_id, TP, FP, FN, `precision`, `recall`, F1)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (base_test_case, testcase, job_id, tp, fp, fn, precision, recall, f1))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except mysql.connector.Error as err:
        print(f"Database insert error: {err}")
        return False

def get_all_test_results():
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT id, base_test_case, testCase, job_id, TP, FP, FN,
                   `precision`, `recall`, F1, created_at, updated_at
            FROM test_results
            ORDER BY created_at DESC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except mysql.connector.Error as err:
        print(f"Test results query error: {err}")
        return None

def get_test_results_by_base_case(base_test_case):
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT id, base_test_case, testCase, job_id, TP, FP, FN,
                   `precision`, `recall`, F1, created_at, updated_at
            FROM test_results
            WHERE base_test_case = %s
            ORDER BY created_at DESC
        """
        cursor.execute(query, (base_test_case,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except mysql.connector.Error as err:
        print(f"Test results by base case query error: {err}")
        return None
