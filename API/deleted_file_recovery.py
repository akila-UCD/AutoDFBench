import os
import shutil
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import cgi
import json
import sys
import mysql.connector
import datetime
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Add support directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../support')))
from ImageCheck import ImageCheck
from ImageCompare import ImageCompare

TEMP_UPLOAD_PATH = os.getenv('TEMP_FILE_UPLOAD_PATH', '/tmp')
UPLOAD_DIR = Path(TEMP_UPLOAD_PATH)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# MySQL connection configuration
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

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

def get_confgs(conf_value):
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor()
        query = """
            SELECT * 
            FROM config 
            WHERE `type` = %s
        """
        cursor.execute(query, (conf_value,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results[0]
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def get_ground_truth_paths(base_test_case):
    """
    Returns rows with columns:
    0:file_name, 1:deleted_time_stamp, 2:modify_time_stamp, 3:access_time_stamp,
    4:change_time_stamp, 5:f-bks, 6:size
    """
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor()
        query = """
            SELECT file_name, deleted_time_stamp, modify_time_stamp, access_time_stamp, change_time_stamp, `f-bks`, size
            FROM ground_truth 
            WHERE base_test_case = %s AND cftt_task = 'deleted_file_recovery' AND type = 'deleted'
        """
        cursor.execute(query, (base_test_case,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def insert_result_to_db(base_test_case, testcase, tp, fp, fn, precision, recall, F1):
    try:
        conn = get_db_connection()
        if conn is None:
            print("DB connection failed; cannot insert results.")
            return
        cursor = conn.cursor()
        insert_query = """
            INSERT INTO test_results ( base_test_case, testCase, job_id, TP, FP, FN, `precision`, `recall`, F1 )
            VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (base_test_case, testcase, '0', tp, fp, fn, precision, recall, F1))
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Error: {err}")

# ------- helpers -------
def to_int(v):
    """Robustly convert a value to int; return None if not possible."""
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            s = str(v).strip()
            return int(s)
        except Exception:
            return None

def has_recoverable_inode(inode_val, size_val):
    """Recoverable = inode present (non-empty, not 'invalid/none/null') AND size > 0."""
    if inode_val is None:
        return False
    inode_str = str(inode_val).strip()
    if len(inode_str) == 0 or inode_str.lower() in {"invalid", "none", "null"}:
        return False
    size_int = to_int(size_val)
    return size_int is not None and size_int > 0
# -----------------------

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/v1/deleted_file_recovery/evaluate":
            content_type = self.headers.get('Content-Type')
            if content_type != 'application/json':
                self.send_error(400, "Content-Type must be application/json")
                return

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            base_test_case = data.get("base_test_case")
            tool_used = data.get("tool_used")
            files = data.get("files", [])
            file_system = data.get("file_system", "")
            check_meta = data.get("check_meta", False)
            include_orphans = bool(data.get("include_orphans", False))  # NEW: include orphan files?

            if not base_test_case or not tool_used or not isinstance(files, list):
                self.send_error(400, "Missing or invalid fields: base_test_case, tool_used, files")
                return

            # Validate duplicate file names
            seen_filenames = set()
            for file_entry in files:
                file_name = file_entry.get("file_name")
                inode_val = file_entry.get("inode")
                file_size_val = file_entry.get("file_size")

                # Check for required fields
                if file_name in (None, "", "NULL") or inode_val in (None, "", "NULL") or file_size_val in (None, "", "NULL"):
                    self.send_error(
                        400,
                        f"Missing required fields in submitted file entry: inode={inode_val}, file_name={file_name}, file_size={file_size_val}"
                    )
                    return

                # Check for duplicate filenames
                if file_name in seen_filenames:
                    self.send_error(400, f"Duplicate file_name detected: {file_name}")
                    return

                seen_filenames.add(file_name)
                test_case = f"{base_test_case}_{tool_used}"
                print(test_case)

            # Fetch ground truth
            gt_entries = get_ground_truth_paths(base_test_case)
            if not gt_entries:
                self.send_error(400, "No ground truth data found or query failed.")
                return

            # Build GT file list
            gt_files = []
            for row in gt_entries:
                gt_files.append({
                    "filename": row[0],
                    "deleted_timestamp": int(row[1]) if row[1] not in (None, "", "NULL") else None,
                    "modified_timestamp": int(row[2]) if row[2] not in (None, "", "NULL") else None,
                    "accessed_timestamp": int(row[3]) if row[3] not in (None, "", "NULL") else None,
                    "changed_timestamp": int(row[4]) if row[4] not in (None, "", "NULL") else None,
                    "fbks": row[5],
                    "size": int(row[6]) if row[6] not in (None, "", "NULL") else None,
                })

            # Precompute GT sizes (ignore None)
            gt_sizes = {row["size"] for row in gt_files if row["size"] is not None}

            matched_gt_files = set()
            matched_files = 0
            total_submitted = len(files)
            total_evaluated = 0  # files considered after skip logic
            rec_evaluated = 0    # recoverable evaluated (inode+size>0)

            null_metadata_fields_count = 0
            details = []
            all_meta_tp = all_meta_fp = all_meta_fn = 0
            name_match_count = 0

            matched_deleted_file_count = 0  # matched & recoverable
            matched_size_file_count = 0
            sigma_count = 0  # FAT "_" -> "X" name mapping with size equality

            matched_deleted_files = []  # only recoverable matches
            matched_size_files = []     # name+size exact matches list
            size_only_matches = []      # size matches ignoring filename

            # Skips tracking
            skipped_orphan_zero_size = 0
            skipped_orphans_excluded = 0
            rec_evaluated = 0

            # Exact name + size matches counter
            exact_name_size_match_count = 0

            # Evaluate each submitted file
            for file_entry in files:
                filename = file_entry.get("file_name")
                filesize = file_entry.get("file_size")
                filesize_str = str(filesize) if filesize is not None else None

                # ---------- Orphan handling ----------
                is_orphan = isinstance(filename, str) and "$OrphanFiles" in filename
                if is_orphan:
                    size_int_tmp = to_int(filesize)
                    if not include_orphans and (size_int_tmp is None or size_int_tmp == 0):
                        skipped_orphan_zero_size += 1
                        continue
                # ---------- End orphan handling ----------

                # File evaluated
                total_evaluated += 1
                

                # Recoverable?
                inode_val = file_entry.get("inode")
                is_recoverable = has_recoverable_inode(inode_val, filesize)
                if is_recoverable:
                    rec_evaluated += 1

                deleted_date = file_entry.get("deleted_timestamp")
                modified_date = file_entry.get("modified_timestamp")
                access_date = file_entry.get("accessed_timestamp")
                changed_date = file_entry.get("changed_timestamp")
                fbks = file_entry.get("fbks")

                matched = False
                matched_gt_file = None
                per_file_f1 = 0.0
                unmatched_fields = []
                matched_fields = []

                # --- size-only match ignoring filename ---
                if filesize is not None:
                    try:
                        if int(filesize) in gt_sizes:
                            size_only_matches.append({"submitted_filename": filename, "file_size": int(filesize)})
                    except (TypeError, ValueError):
                        if str(filesize) in {str(s) for s in gt_sizes}:
                            size_only_matches.append({"submitted_filename": filename, "file_size": filesize})

                # FAT name normalization
                if file_system.startswith("FAT"):
                    filename_for_comparison = filename
                    used_sigma_mapping = False
                    if isinstance(filename, str) and filename.startswith("_"):
                        filename_for_comparison = "X" + filename[1:]
                        used_sigma_mapping = True
                else:
                    filename_for_comparison = filename
                    used_sigma_mapping = False

                print(f"Comparing {filename_for_comparison} with ground truth filenames")

                # Exact GT row by filename equality
                gt_row = next((row for row in gt_files if row["filename"] == filename_for_comparison), None)

                if gt_row:
                    if file_system.startswith("FAT") and used_sigma_mapping:
                        if str(gt_row["size"]) == str(filesize_str):
                            sigma_count += 1

                    if check_meta:
                        # fbks intentionally ignored
                        meta_pairs = [
                            ("filename", filename_for_comparison, gt_row["filename"]),
                            ("deleted_date", deleted_date, gt_row["deleted_timestamp"]),
                            ("modified_date", modified_date, gt_row["modified_timestamp"]),
                            ("accessed_date", access_date, gt_row["accessed_timestamp"]),
                            ("changed_date", changed_date, gt_row["changed_timestamp"]),
                            ("file_size", filesize_str, str(gt_row["size"]) if gt_row["size"] is not None else None),
                        ]
                        print(meta_pairs)
                        # os._exit(1)
                        tp = fp = fn = 0
                        for field, submitted_val, gt_val in meta_pairs:
                            if gt_val in (None, "", "NULL"):
                                null_metadata_fields_count += 1
                                continue
                            if field in ["deleted_date", "modified_date", "accessed_date", "changed_date"]:
                                if not isinstance(submitted_val, int):
                                    self.send_error(400, f"{field} must be provided as an epoch integer timestamp")
                                    return
                            if str(submitted_val) == str(gt_val):
                                tp += 1
                                matched_fields.append(field)
                            else:
                                fp += 1
                                fn += 1
                                unmatched_fields.append(field)

                        all_meta_tp += tp
                        all_meta_fp += fp
                        all_meta_fn += fn

                        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                        per_file_f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

                        matched = tp > 0
                    else:
                        # name presence in GT = match
                        matched = True

                    if matched:
                        matched_files += 1
                        matched_gt_files.add(filename_for_comparison)
                        matched_gt_file = filename_for_comparison

                        # Append only if recoverable (inode + size > 0)
                        if is_recoverable:
                            matched_deleted_file_count += 1
                            matched_deleted_files.append({
                                "filename": filename_for_comparison,
                                "size": gt_row["size"],
                                "inode": inode_val
                            })

                        # Exact name + size equal
                        if str(filesize_str) == str(gt_row["size"]):
                            matched_size_file_count += 1
                            matched_size_files.append({"filename": filename_for_comparison, "size": gt_row["size"]})

                            # Exact name + size match for new Match metric
                            exact_name_size_match_count += 1

                        # Count name match only if inode exists
                        if is_recoverable or (inode_val is not None and str(inode_val).strip()):
                            if filename_for_comparison == gt_row["filename"]:
                                name_match_count += 1
                else:
                    if check_meta:
                        total_fields = 6  # filename + 4 timestamps + size
                        all_meta_fn += total_fields
                        unmatched_fields = ["filename", "deleted_date", "modified_date", "accessed_date", "changed_date", "file_size"]
                        per_file_f1 = 0.0
                    matched = False
                    matched_gt_file = None

                if check_meta:
                    details.append({
                        "submitted_file": filename,
                        "matched": matched,
                        "matched_gt_file": matched_gt_file,
                        "f1_score_per_file": per_file_f1,
                        "matched_meta_fields": matched_fields,
                        "unmatched_meta_fields": unmatched_fields if check_meta else []
                    })

            true_positives = matched_files
            false_positives = total_submitted - (matched_files + skipped_orphan_zero_size + skipped_orphans_excluded)
            false_negatives = len(gt_files) - len(matched_gt_files)

            if check_meta:
                overall_precision = all_meta_tp / (all_meta_tp + all_meta_fp) if (all_meta_tp + all_meta_fp) > 0 else 0.0
                overall_recall = all_meta_tp / (all_meta_tp + all_meta_fn) if (all_meta_tp + all_meta_fn) > 0 else 0.0
                overall_f1_score = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0.0
            else:
                overall_precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
                overall_recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
                overall_f1_score = 2 * overall_precision * overall_recall / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0.0

            insert_result_to_db(base_test_case, test_case, true_positives, false_positives, false_negatives, overall_precision, overall_recall, overall_f1_score)

            name_match = name_match_count - sigma_count  # preserve your Sigma adjustment

            response = {
                "tool_used": tool_used,
                "base_test_case": base_test_case,
                "include_orphans": include_orphans,
                "total_ground_truth_files": len(gt_files),
                "total_submitted_files": total_submitted,
                "total_evaluated_files(REC)": rec_evaluated,  # recoverable files only (inode+size>0)
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "precision": overall_precision,
                "recall": overall_recall,
                "AutoDFBench_score": overall_f1_score,

                # Size-only matches (ignores filename)
                "Size_match": len(size_only_matches),

                # Name + size exact matches
                "SS": exact_name_size_match_count,
                "GT_COUNT": len(gt_files),
                

                # Name matches requiring inode (with Sigma adjustment)
                "NAME_ONLY_Match": name_match,
                "Sigma": sigma_count,
                "Full": exact_name_size_match_count,
                "null_metadata_fields_ignored": null_metadata_fields_count,
                # Matched AND recoverable only
                "matched_deleted_file_count": matched_deleted_file_count,
                "matched_deleted_files": matched_deleted_files,
                "SS_NAME_files": matched_size_files,
                
                "details": details if check_meta else []
            }

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting server on port {port}...")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
