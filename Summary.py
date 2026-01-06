#!/usr/bin/env python3
import os
import shutil
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import cgi
import json
import sys
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

# --- Support path (unchanged) ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../support')))

# --- File staging ---
TEMP_UPLOAD_PATH = os.getenv('TEMP_FILE_UPLOAD_PATH', '/tmp')
UPLOAD_DIR = Path(TEMP_UPLOAD_PATH)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- MySQL connection configuration ---
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

print(DB_HOST)
print(DB_USER)

def get_db_connection():
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def get_ground_truth_rows(base_test_case: str):
    """
    Fetch GT rows for string-search.
    Expected columns in ground_truth:
      - base_test_case (VARCHAR)
      - cftt_task='string_search'
      - file_line (token string/number)
      - type      in {'active','deleted','unallocated'}
    """
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT base_test_case, file_line, `type`
            FROM ground_truth
            WHERE base_test_case LIKE %s
              AND cftt_task = 'string_search'
        """
        cursor.execute(query, (f"%{base_test_case}%",))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return []

def f1_from_pr(precision: float, recall: float) -> float:
    return (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def _bad_request(self, message: str):
        self.send_error(400, message)

    def do_POST(self):
        if self.path != "/api/v1/string-search/evaluate":
            self.send_error(404, "Endpoint not found")
            return

        content_type = self.headers.get('content-type')
        if not content_type:
            self._bad_request("Content-Type header is missing")
            return

        ctype, pdict = cgi.parse_header(content_type)
        if ctype != 'multipart/form-data':
            self._bad_request("Content-Type must be multipart/form-data")
            return

        # Parse multipart form
        pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
        pdict['CONTENT-LENGTH'] = int(self.headers['Content-Length'])
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST'},
            keep_blank_values=True
        )

        base_test_case = form.getvalue("base_test_case")
        tool_used = form.getvalue("tool_used")

        if not base_test_case:
            self._bad_request("Missing field: base_test_case")
            return
        if not tool_used:
            self._bad_request("Missing field: tool_used")
            return

        files_field = form.getlist("files")
        if not files_field:
            self._bad_request("No files provided (use field name 'files')")
            return

        # --- Load GT ---
        gt_rows = get_ground_truth_rows(base_test_case)
        if not gt_rows:
            self._bad_request("Invalid Test Case or no GT rows for cftt_task='string_search'")
            return

        scopes = ("active", "deleted", "unallocated")

        # Build GT token sets by type
        gt_tokens_by_type = {s: set() for s in scopes}
        for r in gt_rows:
            t = (r.get("type") or "").strip().lower()
            if t not in scopes:
                continue
            tok = str(r.get("file_line") or "").strip()
            if tok:
                gt_tokens_by_type[t].add(tok)

        # Track which GT tokens were found (per type)
        found_tokens_by_type = {s: set() for s in scopes}

        # Row-level counts per type for output
        counts = {
            "active": {"hit_count": 0, "misses": 0},
            "deleted": {"hit_count": 0, "misses": 0},
            "unallocated": {"hit_count": 0, "misses": 0}
        }

        details = []

        # Precompute a flat map token -> type for quick lookup (unique tokens assumed)
        token_to_type = {}
        for s in scopes:
            for tok in gt_tokens_by_type[s]:
                token_to_type[tok] = s

        # --- Process each uploaded file ---
        for part in files_field:
            fi = part
            filename = os.path.basename(getattr(fi, "filename", "") or "")
            if not filename:
                continue

            file_path = UPLOAD_DIR / filename
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(fi.file, f)

            per_type_row_hits = {s: 0 for s in scopes}
            total_rows = 0

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        total_rows += 1
                        line_stripped = line.rstrip("\n")

                        # Row-wise: if any token of a type is present in this row, count a hit for that type
                        for s in scopes:
                            tokens = gt_tokens_by_type[s]
                            if tokens and any(tok in line_stripped for tok in tokens):
                                per_type_row_hits[s] += 1

                        # Token-wise: mark each GT token found at least once anywhere
                        for tok, s in token_to_type.items():
                            if tok in line_stripped:
                                found_tokens_by_type[s].add(tok)

                # Update global row-level counters
                for s in scopes:
                    counts[s]["hit_count"] += per_type_row_hits[s]
                    counts[s]["misses"] += max(0, total_rows - per_type_row_hits[s])

                details.append({
                    "submitted_file": filename,
                    "total_rows": total_rows,
                    "per_type": {
                        s: {
                            "matched_rows": per_type_row_hits[s],
                            "missed_rows": max(0, total_rows - per_type_row_hits[s])
                        } for s in scopes
                    }
                })

            except Exception as e:
                details.append({
                    "submitted_file": filename,
                    "error": f"Failed to read/analyse file: {e}"
                })

        # --- Per-type metrics (token-level) ---
        per_type_metrics = {}
        for s in scopes:
            TP = len(found_tokens_by_type[s])             # GT tokens of this type found at least once
            FN = len(gt_tokens_by_type[s] - found_tokens_by_type[s])
            FP = 0  # by design: we only look for GT tokens; nothing outside GT is “predicted”
            precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
            recall = TP / (TP + FN) if (TP + FN) > 0 else 0.0
            per_type_metrics[s] = {
                "TP": TP, "FP": FP, "FN": FN,
                "precision": precision,
                "recall": recall,
                "F1": f1_from_pr(precision, recall)
            }

        # --- Response ---
        response = {
            "base_test_case": base_test_case,
            "tool_used": tool_used,
            "active_file": counts["active"],
            "deleted_file": counts["deleted"],
            "unallocated_space": counts["unallocated"],
            "metrics_by_type": per_type_metrics,
            "details": details
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting server on port {port}...")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
