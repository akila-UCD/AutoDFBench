import os
import shutil
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import sys
from email.parser import BytesParser
from email.policy import default as email_default_policy
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

# Add support directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../support')))
from ImageCheck import ImageCheck
from ImageCompare import ImageCompare

TEMP_UPLOAD_PATH = os.getenv('TEMP_FILE_UPLOAD_PATH', '/tmp')
UPLOAD_DIR = Path(TEMP_UPLOAD_PATH)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ----- MySQL connection configuration -----
DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', '3306') or 3306)
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')


def get_db_connection():
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
    except mysql.connector.Error as err:
        print(f"[DB] Connection error: {err}")
        return None


def get_confgs(conf_value):
    """
    Returns the first row for the given config type, or None.
    Expectation (by your code): row[2] contains the path/value.
    """
    conn = get_db_connection()
    if conn is None:
        return None
    cursor = None
    try:
        cursor = conn.cursor()
        query = """
            SELECT *
            FROM config
            WHERE `type` = %s
        """
        cursor.execute(query, (conf_value,))
        results = cursor.fetchall()
        return results[0] if results else None
    except mysql.connector.Error as err:
        print(f"[DB] Query error: {err}")
        return None
    finally:
        try:
            if cursor: cursor.close()
            conn.close()
        except Exception:
            pass


def get_ground_truth_paths(base_test_case):
    """
    Returns all GT rows for the given base_test_case and cftt_task='windows_registry'.
    Expectation (by your code): row[6] is the GT filename.
    """
    conn = get_db_connection()
    if conn is None:
        return None
    cursor = None
    try:
        cursor = conn.cursor()
        query = """
            SELECT *
            FROM ground_truth
            WHERE base_test_case = %s AND cftt_task = 'windows_registry'
        """
        cursor.execute(query, (base_test_case,))
        results = cursor.fetchall()
        return results
    except mysql.connector.Error as err:
        print(f"[DB] Query error: {err}")
        return None
    finally:
        try:
            if cursor: cursor.close()
            conn.close()
        except Exception:
            pass


def insert_result_to_db(base_test_case, testcase, tp, fp, fn, precision, recall, F1):
    """
    Best-effort insert of the evaluation metrics into test_results.
    """
    conn = get_db_connection()
    if conn is None:
        print("[DB] Skipping insert: no connection")
        return
    cursor = None
    try:
        cursor = conn.cursor()
        insert_query = """
            INSERT INTO test_results (base_test_case, testCase, job_id, TP, FP, FN, `precision`, `recall`, F1)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (base_test_case, testcase, '0', tp, fp, fn, precision, recall, F1))
        conn.commit()
    except mysql.connector.Error as err:
        print(f"[DB] Insert error: {err}")
    finally:
        try:
            if cursor: cursor.close()
            conn.close()
        except Exception:
            pass


# ----- Multipart form parsing (no cgi) -----
def parse_multipart_form(content_type: str, body: bytes):
    """
    Parse a multipart/form-data HTTP request body using the stdlib email parser.

    Returns:
        fields: dict[str, str]                   # text fields (first value if repeated)
        files:  list[{"name": str,
                      "filename": str,
                      "content": bytes}]        # uploaded files
    """
    # Build a minimal MIME message for the email parser
    mime = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    msg = BytesParser(policy=email_default_policy).parsebytes(mime)

    if not msg.is_multipart():
        raise ValueError("Body is not multipart")

    fields = {}
    files = []
    for part in msg.iter_parts():
        disp = part.get("Content-Disposition", "")
        if "form-data" not in disp:
            continue

        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""

        if filename:
            files.append({"name": name, "filename": filename, "content": payload})
        else:
            # For text fields, decode per charset if given
            charset = part.get_content_charset() or "utf-8"
            value = payload.decode(charset, errors="ignore")
            # Keep only first occurrence for simplicity (adequate for your fields)
            if name not in fields:
                fields[name] = value

    return fields, files


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    # ----- Helpers for JSON responses -----
    def send_json(self, status_code, payload):
        body = json.dumps(payload, indent=2).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status_code, message, **extra):
        payload = {"error": message}
        if extra:
            payload.update(extra)
        self.send_json(status_code, payload)

    def do_POST(self):
        if self.path != "/api/v1/windows-registry/evaluate":
            self.send_error_json(404, "Endpoint not found")
            return

        content_type = self.headers.get('Content-Type') or self.headers.get('content-type')
        if not content_type:
            self.send_error_json(400, "Content-Type header is missing")
            return
        if "multipart/form-data" not in content_type.lower():
            self.send_error_json(400, "Content-Type must be multipart/form-data")
            return

        # Read body
        try:
            content_length = int(self.headers.get('Content-Length', '0') or 0)
        except ValueError:
            self.send_error_json(400, "Invalid Content-Length")
            return

        try:
            body = self.rfile.read(content_length)
        except Exception as e:
            self.send_error_json(400, f"Failed to read request body: {e}")
            return

        # Parse multipart
        try:
            fields, uploads = parse_multipart_form(content_type, body)
        except Exception as e:
            self.send_error_json(400, f"Failed to parse multipart form: {e}")
            return

        # Validate required text fields
        base_test_case = (fields.get("base_test_case") or "").strip()
        tool_used = (fields.get("tool_used") or "").strip()

        missing = []
        if not base_test_case:
            missing.append("base_test_case")
        if not tool_used:
            missing.append("tool_used")
        if missing:
            self.send_error_json(400, f"Missing required field(s): {', '.join(missing)}")
            return

        # Collect uploads for field name 'files' (supports multiple parts)
        file_parts = [u for u in uploads if u.get("name") == "files" and u.get("filename")]
        if not file_parts:
            self.send_error_json(400, "'files' must include at least one uploaded file")
            return

        # --- Config and Ground Truth lookups ---
        cfg_row = get_confgs('windows_registry_source_path')
        # Expecting cfg_row[2] to be the directory path to ground-truth files
        if not cfg_row or len(cfg_row) < 3 or not cfg_row[2]:
            self.send_error_json(500, "Server configuration 'windows_registry_source_path' is missing or invalid")
            return
        gt_root = Path(cfg_row[2])

        ground_truth_paths = get_ground_truth_paths(base_test_case)
        if not ground_truth_paths:
            self.send_error_json(400, "Invalid Test Case or no ground truth rows found")
            return

        # Extract GT filenames (row[6] per your schema usage)
        gt_filenames = set()
        for row in ground_truth_paths:
            try:
                name = row[6]
                if name:
                    gt_filenames.add(name)
            except Exception:
                continue

        if not gt_filenames:
            self.send_error_json(500, "Ground truth data incomplete: no filenames present")
            return

        # --- Evaluate submissions ---
        matched_gt_files = set()
        matched_files = 0
        total_submitted = len(file_parts)
        details = []

        for up in file_parts:
            filename = os.path.basename(up["filename"])
            file_path = UPLOAD_DIR / filename

            # Save uploaded file
            try:
                with open(file_path, "wb") as f:
                    f.write(up["content"])
            except Exception as e:
                details.append({
                    "submitted_file": filename,
                    "matched": False,
                    "matched_gt_file": None,
                    "error": f"failed to save upload: {e}"
                })
                continue

            matched = False
            matched_gt_name = None

            # Compare with each GT file
            for gt in ground_truth_paths:
                try:
                    gt_file_name = gt[6]
                    if not gt_file_name:
                        continue
                    gt_file_path = gt_root / gt_file_name
                    if not gt_file_path.exists():
                        # Skip missing GT files silently (or log)
                        continue

                    score = ImageCompare.compute_visibility(str(file_path), str(gt_file_path))
                    # Exact match threshold
                    if score == 100:
                        matched = True
                        matched_files += 1
                        matched_gt_files.add(gt_file_name)
                        matched_gt_name = gt_file_name
                        break
                except Exception as e:
                    print(f"[COMPARE] Error comparing {file_path} vs {gt}: {e}")
                    continue

            details.append({
                "submitted_file": filename,
                "matched": matched,
                "matched_gt_file": matched_gt_name
            })

        # Metrics
        true_positives = matched_files
        false_positives = total_submitted - matched_files
        false_negatives = len(gt_filenames - matched_gt_files)

        precision = (true_positives / (true_positives + false_positives)) if (true_positives + false_positives) > 0 else 0.0
        recall = (true_positives / (true_positives + false_negatives)) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        # Persist results (best-effort)
        try:
            test_case = f"{base_test_case}_{tool_used}"
            insert_result_to_db(base_test_case, test_case, true_positives, false_positives, false_negatives, precision, recall, f1_score)
        except Exception as e:
            print(f"[DB] Failed to insert results: {e}")

        response = {
            "base_test_case": base_test_case,
            "test_case": f"{base_test_case}_{tool_used}",
            "total_ground_truth_files": len(gt_filenames),
            "total_submitted_files": total_submitted,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "details": details
        }

        self.send_json(200, response)


def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting server on port {port}...")
    httpd.serve_forever()


if __name__ == '__main__':
    run()
