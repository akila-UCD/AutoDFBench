#!/usr/bin/env python3
import os
import re
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from autodfbench.eval.string_search import evaluate_string_search

import mysql.connector
from dotenv import load_dotenv

# -------------------- ENV --------------------
load_dotenv()
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# -------------------- DB HELPERS --------------------
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=int(DB_PORT) if DB_PORT else None,
        )
    except mysql.connector.Error as err:
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

def get_gt_map(base_test_case,os_type):
    """
    Returns:
      - gt_lines: set of file_line strings
      - line_to_type: dict file_line -> type ('active'|'deleted'|'unallocated' ... normalised lower)
    Filters by cftt_task='string_search'.
    """
    conn = get_db_connection()
    if conn is None:
        return set(), {}

    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT file_line, `type`
               FROM ground_truth
               WHERE base_test_case=%s AND os=%s AND cftt_task='string_search'""",
            (base_test_case,os_type),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"[DB] Query Error: {err}")
        return set(), {}

    normalise_line = lambda s: str(s).strip() if s is not None else ""
    normalise_type = lambda s: str(s).strip().lower() if s is not None else ""

    line_to_type = {}
    for fl, ty in rows:
        fln = normalise_line(fl)
        tyn = normalise_type(ty)
        if fln:
            line_to_type[fln] = tyn

    return set(line_to_type.keys()), line_to_type

# -------------------- METRICS --------------------
def _div(n, d): return (n / d) if d else 0.0
def compute_metrics(tp, fp, fn):
    p = _div(tp, tp + fp)
    r = _div(tp, tp + fn)
    f1 = _div(2 * p * r, p + r)
    return p, r, f1

# -------------------- HTTP --------------------
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def _json_error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode("utf-8"))



    def do_POST(self):
        if self.path != "/api/v1/string-search/evaluate":
            return self._json_error(404, "Endpoint not found")

        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            return self._json_error(400, "Content-Type must be application/json")

        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            resp = evaluate_string_search(payload)   # ✅ single source of truth
        except json.JSONDecodeError as e:
            return self._json_error(400, f"Invalid JSON: {e}")
        except ValueError as e:
            # evaluator raises ValueError for missing fields etc.
            return self._json_error(400, str(e))
        except Exception as e:
            return self._json_error(500, f"Internal error: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp, indent=2).encode("utf-8"))




    # def do_POST(self):
    #     if self.path != "/api/v1/string-search/evaluate":
    #         return self._json_error(404, "Endpoint not found")

    #     if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
    #         return self._json_error(400, "Content-Type must be application/json")

    #     try:
    #         length = int(self.headers.get("Content-Length", "0") or "0")
    #         payload = json.loads(self.rfile.read(length).decode("utf-8"))
    #         resp = evaluate_string_search(payload)
    #     except Exception as e:
    #         # return self._json_error(400, f"Invalid JSON: {e}")
    #         return self._json_error(400, str(e))

    #     base_test_case = str(payload.get("base_test_case", "")).strip()
    #     tool_used = str(payload.get("tool_used", "")).strip()
    #     found_list = payload.get("file_contents_found", [])
    #     os_type = str(payload.get("os", "")).strip()

    #     if not base_test_case:
    #         return self._json_error(400, "Missing 'base_test_case'")
    #     if not tool_used:
    #         return self._json_error(400, "Missing 'tool_used'")
    #     if not isinstance(found_list, list):
    #         return self._json_error(400, "'file_contents_found' must be an array of strings")
    #     if not os_type:
    #         return self._json_error(400, "Missing 'OS Type'")


    #     # Extract 4-digit line numbers
    #     line_re = re.compile(r"\b(\d{4})\b")
    #     submitted = set()
    #     for s in found_list:
    #         if isinstance(s, str):
    #             m = line_re.search(s)
    #             if m:
    #                 submitted.add(m.group(1))

    #     # Load GT (lines + type map)
    #     gt_lines, line_to_type = get_gt_map(base_test_case,os_type)
    #     if not gt_lines:
    #         return self._json_error(400, "Invalid test case or no GT rows for cftt_task='string_search'")

    #     matched = submitted & gt_lines
    #     fp_set = submitted - gt_lines
    #     fn_set = gt_lines - submitted

    #     tp, fp, fn = len(matched), len(fp_set), len(fn_set)
    #     precision, recall, f1 = compute_metrics(tp, fp, fn)

    #     # ---- Per-type hit counts (for TP only) ----
    #     type_counts = {"active": 0, "deleted": 0, "unallocated": 0}
    #     per_type_matched = {"active": [], "deleted": [], "unallocated": []}

    #     for ln in matched:
    #         t = line_to_type.get(ln, "").lower()
    #         # normalise a couple of common misspellings/variants
    #         if t in ("unalloc", "unallocated", "unalocated", "un-allocated"):
    #             t = "unallocated"
    #         if t in type_counts:
    #             type_counts[t] += 1
    #             per_type_matched[t].append(ln)

    #     test_case = f"{base_test_case}_{tool_used}"
    #     insert_result_to_db(base_test_case, test_case, tp, fp, fn, precision, recall, f1)

    #     resp = {
    #         "base_test_case": base_test_case,
    #         "tool_used": tool_used,
    #         "total_gt_lines": len(gt_lines),
    #         "total_submitted_lines": len(submitted),
    #         "true_positives": tp,
    #         "false_positives": fp,
    #         "false_negatives": fn,
    #         "precision": precision,
    #         "recall": recall,
    #         "f1_score": f1,
    #         "hit_counts_by_type": {
    #             "active": type_counts["active"],
    #             "deleted": type_counts["deleted"],
    #             "unallocated": type_counts["unallocated"]
    #         }
    #         # "details": {
    #         #     "matched_lines": sorted(list(matched)),
    #         #     "matched_lines_by_type": {
    #         #         "active": sorted(per_type_matched["active"]),
    #         #         "deleted": sorted(per_type_matched["deleted"]),
    #         #         "unallocated": sorted(per_type_matched["unallocated"])
    #         #     },
    #         #     "false_positive_lines": sorted(list(fp_set)),
    #         #     "missed_gt_lines": sorted(list(fn_set))
    #         # }
    #     }

    #     self.send_response(200)
    #     self.send_header("Content-Type", "application/json")
    #     self.end_headers()
    #     self.wfile.write(json.dumps(resp, indent=2).encode("utf-8"))

# -------------------- RUN --------------------
def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    httpd = server_class(('', port), handler_class)
    print(f"Starting server on port {port}…")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
