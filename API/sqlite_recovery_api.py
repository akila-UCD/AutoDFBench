#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from dotenv import load_dotenv

from autodfbench.eval.sqlite_recovery import evaluate_sqlite_recovery

load_dotenv()


class SQLiteRecoveryHandler(BaseHTTPRequestHandler):
    def _json_error(self, code: int, message: str):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode("utf-8"))

    def do_POST(self):
        # ✅ Single endpoint (same)
        if self.path != "/api/v1/sqlite-recovery/evaluate":
            return self._json_error(404, "Endpoint not found")

        # --- Content-Type ---
        content_type = self.headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            return self._json_error(400, "Content-Type must be application/json")

        # --- Read body ---
        try:
            content_length = int(self.headers.get("Content-Length", 0) or 0)
        except Exception:
            return self._json_error(400, "Invalid Content-Length")

        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return self._json_error(400, "Invalid JSON")

        # --- Evaluate using shared logic ---
        try:
            resp = evaluate_sqlite_recovery(data)
        except ValueError as e:
            return self._json_error(400, str(e))
        except LookupError as e:
            return self._json_error(404, str(e))
        except Exception as e:
            return self._json_error(500, f"Internal error: {e}")

        # --- Response ---
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp, indent=2).encode("utf-8"))


def run(port: int = 8001):
    server_address = ("", port)
    httpd = HTTPServer(server_address, SQLiteRecoveryHandler)
    print(f"SQLite Forensic Evaluation Server running on port {port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
