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
        cursor = conn.cursor()
        insert_query = """
            INSERT INTO test_results ( base_test_case, testCase, job_id, TP, FP, FN, `precision`, `recall`, F1 )
            VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (base_test_case, testcase, '0', tp, fp, fn, precision, recall, F1))
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Error: {err}")

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
            file_system = data.get("file_system", "")  # File system type (e.g., "FAT" or empty)
            check_meta = data.get("check_meta", False)

            if not base_test_case or not tool_used or not isinstance(files, list):
                self.send_error(400, "Missing or invalid fields: base_test_case, tool_used, files")
                return

            seen_filenames = set()
            for file_entry in files:
                file_name = file_entry.get("file_name")
                if not file_name:
                    self.send_error(400, "Each file must have a file_name")
                    return
                if file_name in seen_filenames:
                    self.send_error(400, f"Duplicate file_name detected: {file_name}")
                    return
                seen_filenames.add(file_name)

            test_case = f"{base_test_case}_{tool_used}"
            print(test_case)

            # Fetch ground truth data from the database
            gt_entries = get_ground_truth_paths(base_test_case)
            if not gt_entries:
                self.send_error(400, "No ground truth data found or query failed.")
                return

            # All the ground truth files with their size and filenames
            gt_files = [{"filename": row[0], "size": row[6]} for row in gt_entries]

            matched_gt_files = set()
            matched_files = 0
            total_submitted = len(files)
            null_metadata_fields_count = 0
            details = []
            all_meta_tp = all_meta_fp = all_meta_fn = 0

            matched_deleted_file_count = 0  # Counter for matched deleted files
            matched_size_file_count = 0  # Counter for matched files where size is the same
            sigma_count = 0  # Counter for sigma (matching files with size for FAT and "_")

            matched_deleted_files = []  # List to store GT file name and size of matched deleted files
            matched_size_files = []  # List to store GT file name and size of matched files with same size

            for file_entry in files:
                filename = file_entry.get("file_name")
                filesize = str(file_entry.get("file_size")) if file_entry.get("file_size") is not None else None
                deleted_date = file_entry.get("deleted_timestamp")
                modified_date = file_entry.get("modified_timestamp")
                access_date = file_entry.get("accessed_timestamp")
                changed_date = file_entry.get("changed_timestamp")
                fbks = file_entry.get("fbks")

                matched = False
                matched_gt_file = None
                per_file_f1 = 0.0
                unmatched_fields = []

                # Adjust the filename comparison logic based on the file system type
                if file_system == "FAT":
                    # If file_system is FAT, replace the first character "_" with "X"
                    filename_for_comparison = filename
                    if filename.startswith("_"):
                        filename_for_comparison = "X" + filename[1:]  # Replace "_" with "X"
                        # Check if the size matches for sigma count
                        gt_row = next((row for row in gt_files if row["filename"] == filename_for_comparison and str(row["size"]) == filesize), None)
                        if gt_row:
                            sigma_count += 1  # Increment sigma if size matches
                else:
                    filename_for_comparison = filename  # Compare the full filename if it's not FAT or empty

                print(f"Comparing {filename_for_comparison} with ground truth filenames")
               

                # Look for matching GT file (after adjusting for FAT file system)
                gt_row = next((row for row in gt_files if row["filename"] == filename_for_comparison), None)
                if gt_row:
                    gt_deleted, gt_modified, gt_accessed, gt_changed, gt_fbks, gt_size = gt_row["filename"], gt_row.get("modified_timestamp", None), gt_row.get("accessed_timestamp", None), gt_row.get("changed_timestamp", None), gt_row.get("fbks", None), gt_row["size"]

                    if check_meta:
                        meta_pairs = [
                            ("deleted_date", deleted_date, gt_deleted),
                            ("modified_date", modified_date, gt_modified),
                            ("accessed_date", access_date, gt_accessed),
                            ("changed_date", changed_date, gt_changed),
                            ("fbks", fbks, gt_fbks),
                            ("file_size", filesize, str(gt_size) if gt_size is not None else None)
                        ]

                        tp = fp = fn = 0
                        for field, submitted_val, gt_val in meta_pairs:
                            if gt_val is None or gt_val == "":
                                null_metadata_fields_count += 1
                                continue
                            if field in ["deleted_date", "modified_date", "accessed_date", "changed_date"]:
                                if not isinstance(submitted_val, int):
                                    self.send_error(400, f"{field} must be provided as an epoch integer timestamp")
                                    # return

                            if str(submitted_val) == str(gt_val):
                                tp += 1
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
                        matched = filename_for_comparison in [row["filename"] for row in gt_files]  # Compare full filename for non-FAT systems

                    if matched:
                        matched_files += 1
                        matched_gt_files.add(filename)
                        matched_gt_file = filename

                        # Add matched deleted file with GT size
                        matched_deleted_file_count += 1
                        matched_deleted_files.append({"filename": filename, "size": gt_size})

                        # Add matched size file if sizes are the same
                        if str(filesize) == str(gt_size):
                            matched_size_file_count += 1
                            matched_size_files.append({"filename": filename, "size": gt_size})

                if check_meta:
                    details.append({
                        "submitted_file": filename,
                        "matched": matched,
                        "matched_gt_file": matched_gt_file,
                        "f1_score_per_file": per_file_f1,
                        "unmatched_meta_fields": unmatched_fields
                    })
            match_count = matched_deleted_file_count - sigma_count
            
            true_positives = matched_files
            false_positives = total_submitted - matched_files
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

            response = {
                "tool_used": tool_used,
                "base_test_case": base_test_case,
                "total_ground_truth_files": len(gt_files),
                "total_submitted_files": total_submitted,
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "precision": overall_precision,
                "recall": overall_recall,
                "f1_score": overall_f1_score,
                "SS": len(matched_size_files),  # Size matched file name and size
                "Full":len(matched_size_files),
                "Match": match_count,
                "Sigma": sigma_count,  # Output the sigma count
                "null_metadata_fields_ignored": null_metadata_fields_count,
                "matched_deleted_file_count": matched_deleted_file_count,
                "matched_size_file_count": matched_size_file_count,
                "Del": gt_files,  # All GT files (filename, size)
                "Full": matched_size_files,  # Size matched file name and size
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
