#!/usr/bin/env python3
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from dotenv import load_dotenv

from autodfbench.utils.form_parser import parse_multipart_form_data
from autodfbench.eval.windows_registry import evaluate_windows_registry

load_dotenv()

TEMP_UPLOAD_PATH = os.getenv('TEMP_FILE_UPLOAD_PATH', '/tmp')
UPLOAD_DIR = Path(TEMP_UPLOAD_PATH)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class WindowsRegistryHandler(BaseHTTPRequestHandler):
    def send_json(self, code: int, data: dict):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, default=str).encode('utf-8'))

    def send_error_json(self, code: int, message: str, details=None):
        payload = {"status": "error", "message": message, "status_code": code}
        if details is not None:
            payload["details"] = details
        self.send_json(code, payload)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        # Keep endpoint aligned with your existing v1 routes
        if path != "/api/v1/windows-registry/evaluate":
            return self.send_error_json(404, f"Endpoint not found: {self.path}")

        content_type = self.headers.get('content-type', '')
        if 'multipart/form-data' not in content_type:
            return self.send_error_json(400, "Content-Type must be multipart/form-data")

        content_length = int(self.headers.get('Content-Length', 0) or 0)
        if content_length == 0:
            return self.send_error_json(400, "Empty request body")

        post_data = self.rfile.read(content_length)

        form_data, files = parse_multipart_form_data(self.headers, post_data)
        if form_data is None:
            return self.send_error_json(400, "Failed to parse multipart form data")

        base_test_case = form_data.get("base_test_case")
        tool_used = form_data.get("tool_used")
        job_id = form_data.get("job_id", "0")

        if not base_test_case or not tool_used:
            return self.send_error_json(400, "Missing required parameters: base_test_case, tool_used")

        uploaded_files = files.get("files", [])
        if not uploaded_files:
            return self.send_error_json(400, "No files uploaded")

        # Strict: exactly one submitted CSV
        if len(uploaded_files) != 1:
            return self.send_error_json(400, "Exactly one CSV file required per test case")

        f0 = uploaded_files[0]
        filename = f0.get("filename") or ""
        content = f0.get("content") or b""

        if not filename.lower().endswith(".csv"):
            return self.send_error_json(400, "Only CSV files are allowed")

        try:
            resp = evaluate_windows_registry({
                "base_test_case": base_test_case,
                "tool_used": tool_used,
                "job_id": job_id,
                "submitted_filename": filename,
                "submitted_csv_bytes": content,
                "upload_dir": str(UPLOAD_DIR),
                "write_db": True,   # API default
            })
            return self.send_json(200, resp)

        except ValueError as e:
            return self.send_error_json(400, str(e))
        except Exception as e:
            return self.send_error_json(500, f"Internal server error: {e}")


def run(port: int = 8000):
    print(f"Starting Windows Registry API on port {port}...")
    httpd = HTTPServer(("", port), WindowsRegistryHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
