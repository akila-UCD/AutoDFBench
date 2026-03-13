#!/usr/bin/env python3
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from autodfbench.eval.deleted_file_recovery import evaluate_deleted_file_recovery



class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def _json_error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}, ensure_ascii=False).encode("utf-8"))

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path != "/api/v1/deleted_file_recovery/evaluate":
            return self._json_error(404, "Endpoint not found")

        if not (self.headers.get("Content-Type", "").startswith("application/json")):
            return self._json_error(400, "Content-Type must be application/json")

        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            resp = evaluate_deleted_file_recovery(payload)
        except ValueError as e:
            return self._json_error(400, str(e))
        except Exception as e:
            return self._json_error(500, f"Internal error: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(resp, indent=2, ensure_ascii=False).encode("utf-8"))


def run(port=8000):
    httpd = HTTPServer(("", port), SimpleHTTPRequestHandler)
    print(f"Starting server on port {port}...")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
