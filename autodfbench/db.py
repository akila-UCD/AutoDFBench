# autodfbench/db.py

from autodfbench.database import get_db_connection as _storage_connection, Error as DBError
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """SQLite storage (see autodfbench/database.py)."""
    return _storage_connection()


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
    except DBError as err:
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
    except DBError as err:
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
