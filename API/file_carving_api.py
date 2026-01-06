#!/usr/bin/env python3
# API/file_carving_api.py
# File-carving evaluation API (multipart upload) that delegates ALL scoring to:
#   autodfbench.eval.file_carving.evaluate_file_carving
#
# This keeps API + CSV evaluation perfectly consistent.

from __future__ import annotations

import os
import shutil
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import cgi
import json

from dotenv import load_dotenv

# Shared evaluator (the core logic)
from autodfbench.eval.file_carving import evaluate_file_carving

load_dotenv()

# ---------- Paths ----------
SOURCE_DIR = Path(os.getenv("CARVING_SOURCE_DIR", "Data/source"))
SOURCE_DIR.mkdir(parents=True, exist_ok=True)

TEMP_UPLOAD_PATH = os.getenv("TEMP_FILE_UPLOAD_PATH", "/tmp")
UPLOAD_DIR = Path(TEMP_UPLOAD_PATH)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Small helpers ----------
def _int(v, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _float(v, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _bool(v, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _safe_filename(name: str) -> str:
    # prevent path traversal; keep only basename
    return os.path.basename(name or "").replace("\x00", "")


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def _json_error(self, code: int, message: str):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode("utf-8"))

    def do_POST(self):
        if self.path != "/api/v1/file-carving/evaluate":
            return self._json_error(404, "Endpoint not found")

        content_type = self.headers.get("content-type")
        if not content_type:
            return self._json_error(400, "Content-Type header is missing")

        ctype, pdict = cgi.parse_header(content_type)
        if ctype != "multipart/form-data":
            return self._json_error(400, "Content-Type must be multipart/form-data")

            graphic_file_carving_source_path = get_confgs('graphic_file_carving_source_path')
            
            base_test_case = form.getvalue("base_test_case")

            too_used = form.getvalue("tool_used")

            test_case = f"{base_test_case}_{too_used}"

        try:
            pdict["CONTENT-LENGTH"] = int(self.headers.get("Content-Length", "0") or "0")
        except Exception:
            return self._json_error(400, "Invalid Content-Length")

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST"},
            keep_blank_values=True,
        )

        # Required fields
        base_test_case = (form.getvalue("base_test_case") or "").strip()
        tool_used = (form.getvalue("tool_used") or "").strip()
        if not base_test_case or not tool_used:
            return self._json_error(400, "Missing base_test_case or tool_used")

        # Params (defaults same as your previous API)
        block_size = _int(form.getvalue("block_size"), 512)

        stride_val = form.getvalue("stride")
        stride = _int(stride_val, block_size) if stride_val is not None else block_size

        include_partial = _bool(form.getvalue("include_partial", "true"), default=True)
        ignore_zero = _bool(form.getvalue("ignore_zero", "true"), default=True)

        byte_sim_threshold = _float(form.getvalue("byte_similarity_threshold"), 0.2)

        gt_select_strategy = (form.getvalue("gt_select_strategy") or os.getenv("GT_SELECT_STRATEGY", "phash_first")).strip()
        phash_top_k = _int(form.getvalue("phash_top_k"), _int(os.getenv("PHASH_TOP_K", "3"), 3))
        phash_hash_size = _int(form.getvalue("phash_hash_size"), _int(os.getenv("PHASH_HASH_SIZE", "8"), 8))
        phash_highfreq = _int(form.getvalue("phash_highfreq"), _int(os.getenv("PHASH_HIGHFREQ", "4"), 4))

        q_complete_pct = _float(form.getvalue("q_complete_pct"), _float(os.getenv("Q_SIM_COMPLETE_PCT", "0.5"), 0.5))
        q_major_pct = _float(form.getvalue("q_major_pct"), _float(os.getenv("Q_SIM_MAJOR_PCT", "0.1"), 0.1))

        # Control flags
        # - API usually writes to DB. You can override by passing write_db=false.
        write_db = _bool(form.getvalue("write_db", "true"), default=True)

        # Optional: remove uploaded files after evaluation (keeps /tmp clean)
        cleanup_uploads = _bool(form.getvalue("cleanup_uploads", "true"), default=True)

        # Files field must exist
        if "files" not in form:
            return self._json_error(400, "No files were uploaded (field name should be 'files')")

        files_field = form["files"]
        files = files_field if isinstance(files_field, list) else [files_field]
        if not files:
            return self._json_error(400, "No files were uploaded")

        # Save uploads to disk (as API did before)
        saved_paths: list[Path] = []
        try:
            for file_item in files:
                filename = _safe_filename(getattr(file_item, "filename", "") or "")
                if not filename:
                    continue

                file_path = UPLOAD_DIR / filename
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(file_item.file, f)
                saved_paths.append(file_path)

            if not saved_paths:
                return self._json_error(400, "No valid files were uploaded")

                for gt in ground_truth_paths:
                    gt_file_name = gt[6]
                    gt_file_path = Path(graphic_file_carving_source_path[2]) / gt_file_name

                    score = ImageCompare.compute_visibility(file_path, gt_file_path)
                    print(f"Comparing: {file_path} ↔ {gt_file_path} = Score: {score}")

                    
                    hexScore = ImageCompare.block_compare(file_path, gt_file_path)
                    print(f"hexScore: {hexScore}")


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
                "tool_used": tool_used,
                "carved_files": [str(p) for p in saved_paths],

                # evaluator params
                "source_dir": str(SOURCE_DIR),
                "block_size": block_size,
                "stride": stride,
                "include_partial": include_partial,
                "ignore_zero": ignore_zero,
                "byte_similarity_threshold": byte_sim_threshold,

                "gt_select_strategy": gt_select_strategy,
                "phash_top_k": phash_top_k,
                "phash_hash_size": phash_hash_size,
                "phash_highfreq": phash_highfreq,

                "q_complete_pct": q_complete_pct,
                "q_major_pct": q_major_pct,

                "write_db": write_db,
            }

            response = evaluate_file_carving(payload)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode("utf-8"))

        except ValueError as e:
            return self._json_error(400, str(e))
        except Exception as e:
            return self._json_error(500, f"Internal error: {e}")
        finally:
            if cleanup_uploads:
                for p in saved_paths:
                    try:
                        p.unlink(missing_ok=True)  # Python 3.8+: on 3.8, missing_ok exists? (3.8 yes)
                    except TypeError:
                        # fallback for older versions
                        try:
                            if p.exists():
                                p.unlink()
                        except Exception:
                            pass
                    except Exception:
                        pass


def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port: int = 8000):
    httpd = server_class(("", port), handler_class)
    print(f"Starting file carving API on port {port}…")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
