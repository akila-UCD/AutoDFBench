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
            SELECT * 
            FROM ground_truth 
            WHERE base_test_case = %s AND cftt_task = 'file_carving'
        """
        cursor.execute(query, (base_test_case,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None


# Function to insert the result into the database
def insert_result_to_db(base_test_case, testcase, tp,fp,fn,precision,recall, F1):
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
        if self.path == "/api/v1/file-carving/evaluate":
            content_type = self.headers.get('content-type')
            if not content_type:
                self.send_error(400, "Content-Type header is missing")
                return

            ctype, pdict = cgi.parse_header(content_type)
            if ctype != 'multipart/form-data':
                self.send_error(400, "Content-Type must be multipart/form-data")
                return

            pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
            pdict['CONTENT-LENGTH'] = int(self.headers['Content-Length'])
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'},
                keep_blank_values=True
            )

            graphic_file_carving_source_path = get_confgs('graphic_file_carving_source_path')
            
            base_test_case = form.getvalue("base_test_case")
            too_used = form.getvalue("tool_used")
            test_case = f"{base_test_case}_{too_used}"


            files = form['files']
            if not isinstance(files, list):
                files = [files]

            ground_truth_paths = get_ground_truth_paths(base_test_case)
            if len(ground_truth_paths) == 0 :
                self.send_error(400, "Invalid Test Case")
                return
            
            gt_filenames = set(gt[6] for gt in ground_truth_paths)

            matched_gt_files = set()
            matched_files = 0
            total_submitted = len(files)

            details = []

            for file_item in files:
                filename = os.path.basename(file_item.filename)
                file_path = UPLOAD_DIR / filename

                with open(file_path, 'wb') as f:
                    shutil.copyfileobj(file_item.file, f)

                matched = False
                matched_gt_name = None

                for gt in ground_truth_paths:
                    gt_file_name = gt[6]
                    gt_file_path = Path(graphic_file_carving_source_path[2]) / gt_file_name

                    score = ImageCompare.compute_visibility(file_path, gt_file_path)
                    print(f"Comparing: {file_path} ↔ {gt_file_path} = Score: {score}")

                    if score == 100:
                        matched = True
                        matched_files += 1
                        matched_gt_files.add(gt_file_name)
                        matched_gt_name = gt_file_name
                        break  # stop comparing if exact match found

                details.append({
                    "submitted_file": filename,
                    "matched": matched,
                    "matched_gt_file": matched_gt_name
                })

            true_positives = matched_files
            false_positives = total_submitted - matched_files
            false_negatives = len(gt_filenames - matched_gt_files)

            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
            f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

            insert_result_to_db(base_test_case, test_case, true_positives,false_positives,false_negatives,precision,recall, f1_score)
            response = {
                "base_test_case": base_test_case,
                "total_ground_truth_files": len(ground_truth_paths),
                "total_submitted_files": total_submitted,
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "precision": precision,
                "recall": recall,
                "f1_score": f1_score,
                "details": details
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
