# autodfbench/db.py

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
    try:
        port = None
        if DB_PORT is not None:
            s = str(DB_PORT).strip()
            if s and s.lower() != "none":
                port = int(s)

        kwargs = dict(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
        )
        if port is not None:
            kwargs["port"] = port

        return mysql.connector.connect(**kwargs)

    except (ValueError, TypeError) as e:
        print(f"[DB] Invalid DB_PORT={DB_PORT!r}: {e}")
        return None
    except mysql.connector.Error as err:
        print(DB_HOST)
        print(DB_USER)
        print(DB_PASSWORD)
        print(f"[DB] Error: {err}")
        return None


def insert_result_to_db(base_test_case, test_case, tp, fp, fn, precision, recall, f1):
    try:
        conn = get_db_connection()
        if conn is None:
            print("[DB] Skipped insert: no connection.")
            return
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO test_results
                 (base_test_case, testCase, job_id, TP, FP, FN, `precision`, `recall`, F1)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (base_test_case, test_case, '0', tp, fp, fn, precision, recall, f1),
        )
        conn.commit()
        cur.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"[DB] Insert Error: {err}")

def get_ss_gt_map(base_test_case, os_type):
    conn = get_db_connection()
    if conn is None:
        return set(), {}

    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT file_line, `type`
               FROM ground_truth
               WHERE base_test_case=%s AND os=%s AND cftt_task='string_search'""",
            (base_test_case, os_type),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"[DB] Query Error: {err}")
        return set(), {}

    normalise_line = lambda s: str(s).strip() if s is not None else ""
    normalise_type = lambda s: str(s).strip().lower() if s is not None else ""
    print(rows)
    line_to_type = {}
    for fl, ty in rows:
        fln = normalise_line(fl)
        tyn = normalise_type(ty)
        if fln:
            line_to_type[fln] = tyn

    return set(line_to_type.keys()), line_to_type
