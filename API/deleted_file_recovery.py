#!/usr/bin/env python3
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
import math
import re
import csv
from dotenv import load_dotenv

load_dotenv()

# Add support directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../support')))
from ImageCheck import ImageCheck
from ImageCompare import ImageCompare

TEMP_UPLOAD_PATH = os.getenv('TEMP_FILE_UPLOAD_PATH', '/tmp')
UPLOAD_DIR = Path(TEMP_UPLOAD_PATH)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# === Results directory for saving API outputs ===
RESULTS_DIR = Path("./dfr_tests")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def _safe_filename(name: str) -> str:
    s = (name or "").replace(os.sep, "_").replace("/", "_").replace("\\", "_")
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s.strip("_") or "result"

def _save_response_json(test_case: str, payload: dict) -> None:
    try:
        fname = RESULTS_DIR / f"{_safe_filename(test_case)}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(f"[INFO] Saved JSON report: {fname}")
    except Exception as e:
        print(f"[WARN] Failed to save JSON report for {test_case}: {e}", file=sys.stderr)

def _append_summary_csv(base_test_case: str,
                        total_submitted_files: int,
                        auto_dfbench_score: float,
                        rec:int,
                        ss: int,
                        first: int,
                        full: int,
                        match: int,
                        over: int,
                        multi: int) -> None:
    """
    Append a one-line summary to ./dfr_tests/summary.csv.
    Header EXACTLY as requested (note 'Mutli' spelling preserved).
    """
    try:
        csv_path = RESULTS_DIR / "summary.csv"
        file_exists = csv_path.exists() and csv_path.stat().st_size > 0
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "base_test_case",
                    "total_submitted_files",
                    "AutoDFBench_score",
                    "REC",
                    "SS",
                    "First",
                    "Full",
                    "Match",
                    "Over",
                    "Mutli"  # keep exact spelling from requirement
                ])
            writer.writerow([
                base_test_case,
                total_submitted_files,
                float(auto_dfbench_score),
                int(rec),
                int(ss),
                int(first),
                int(full),
                int(match),
                int(over),
                int(multi)
            ])
        print(f"[INFO] Appended summary CSV: {csv_path}")
    except Exception as e:
        print(f"[WARN] Failed to append summary CSV: {e}", file=sys.stderr)

# =======================
# MySQL configuration
# =======================
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

NO_OVERWITE_TESTS = ['DFR-01/fat-01','DFR-02/fat-02', 'DFR-03/fat-03','DFR-05/fat-05','DFR-05/fat-0-braid5',
                     'DFR-05/fat-05-nest','DFR-06/fat-06','DFR-09/fat-09','DFR-11/fat-11','DFR-01/xfat-01','DFR-02/xfat-02',
                     'DFR-03/xfat-03','DFR-05/xfat-05','DFR-05/xfat-05-braid','DFR-05/xfat-05-nest','DFR-06/xfat-06',
                     'DFR-09/xfat-09','DFR-011/xfat-11','DFR-01/ntfs-01','DFR-02/ntfs-02','DFR-03/ntfs-03','DFR-05/ntfs-05',
                     'DFR-06/ntfs-06','DFR-09/ntfs-09','DFR-11/ntfs-11','DFR-01/ext-01','DFR-02/ext-02','DFR-03/ext-03','DFR-05/ext-05',
                     'DFR-06/ext-06','DFR-09/ext-09','DFR-11/ext-11'
                     ]

OVERWITE_TESTS = [
    'DFR-07/fat-07','DFR-07/fat-07-one','DFR-07/fat-07-two','DFR-08/fat-08','DFR-10/fat-10','DFR-12/fat-12','DFR-13/fat-13',
    'DFR-07/xfat-07','DFR-07/xfat-07-one','DFR-07/xfat-07-two','DFR-08/fat-08','DFR-10/fat-10','DFR-12/fat-12','DFR-13/fat-13',
    'DFR-07/ntfs-07','DFR-07/ntfs-07-one','DFR-07/ntfs-07-two','DFR-08/ntfs-08','DFR-10/ntfs-10','DFR-12/ntfs-12','DFR-13/ntfs-13',
    'DFR-07/ext-07','DFR-07/ext-07-one','DFR-07/ext-07-two','DFR-08/ext-08','DFR-10/ext-10','DFR-12/ext-12','DFR-13/ext-13',
]

FILE_SIZE_TESTS = [
    'DFR-01/fat-01','DFR-07/fat-07','DFR-011/fat-11',
    'DFR-01/ntfs-01','DFR-07/ntfs-07','DFR-011/ntfs-11',
    'DFR-01/ext-01','DFR-07/ext-07','DFR-011/ext-11',
]

MAC_TIME_TESTS = [
    'DFR-01/fat-01','DFR-01/ntfs-01','DFR-01/ext-01'
]

NON_LATIN_CHAR_TETS =[
    'DFR-04/fat-04','DFR-04/ext-04','DFR-04/ntfs-04'
]
RECYCLE_DEL_TESTS = [
    'DFR-01/ext-01-recycle', 'DFR-01/fat-01-recycle', 'DFR-01/ntfs-01-recycle'
]
SPECAIL_NTFS_TEST = [
    'DFR-11/ntfs-11-compress', 'DFR-11/ntfs-11-mft'
]
SPECAIL_OBJECTS_TESTS = [
    'DFR-14/fat-14','DFR-14/ntfs-14','DFR-14/ext-14'
]

# -------- DB helpers --------
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

def get_ground_truth_paths(base_test_case):
    """
    0:file_name, 1:deleted_time_stamp, 2:modify_time_stamp, 3:access_time_stamp,
    4:change_time_stamp, 5:block_count, 6:size, 7:dfr_blocks
    """
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor()
        query = """
            SELECT file_name, deleted_time_stamp, modify_time_stamp, access_time_stamp, change_time_stamp, block_count, size, dfr_blocks
            FROM ground_truth 
            WHERE LOWER(base_test_case) = LOWER(%s) AND cftt_task = 'deleted_file_recovery' AND type = 'deleted'
        """
        cursor.execute(query, (base_test_case,))
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# -------- Block & name helpers --------
RANGE_RE = re.compile(r'^\s*(\d+)\s*-\s*(\d+)\s*$')

def parse_blocks_list(v):
    """Normalise a blocks value into a list of string tokens for comparison."""
    if v is None:
        return []
    if isinstance(v, list):
        tokens = []
        for x in v:
            s = str(x).strip()
            if s != "":
                tokens.append(s)
        return tokens
    s = str(v).strip()
    if s == "":
        return []
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
        s = s[1:-1]
    parts = [p.strip() for p in (s.split(",") if "," in s else s.split())]
    return [p for p in parts if p]

def expand_block_tokens(tokens):
    """Expand 'A-B' ranges into inclusive sequences and keep stand-alone integers."""
    out = []
    for t in tokens or []:
        m = RANGE_RE.match(t)
        if m:
            a = int(m.group(1)); b = int(m.group(2))
            if a <= b:
                out.extend([str(n) for n in range(a, b + 1)])
            else:
                out.extend([str(n) for n in range(b, a + 1)])
        else:
            ts = t.strip()
            if ts.isdigit():
                out.append(ts)
    return out

def numeric_nonzero_unique_blocks(block_tokens):
    """Keep only numeric, non-zero, unique block numbers as ints, sorted."""
    nums = []
    for t in (block_tokens or []):
        ts = str(t).strip()
        if ts.isdigit():
            val = int(ts)
            if val != 0:
                nums.append(val)
    return sorted(set(nums))

def first_min_nonzero_block(tokens):
    """Return the smallest positive integer block, or None if none."""
    vals = []
    for t in (tokens or []):
        ts = str(t).strip()
        if ts.isdigit():
            v = int(ts)
            if v > 0:
                vals.append(v)
    return min(vals) if vals else None

def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            s = str(v).strip()
            return int(s)
        except Exception:
            return None

def names_equal(sub_name: str, gt_name: str, file_system: str) -> bool:
    """
    Name equivalence used for:
      - Match counter
      - F1 Name+Size rule
      - Weighted scoring 'name' component
    Rule:
      * For FAT (case-insensitive), ignore the first character and compare the remainder.
      * For others, compare exact string equality.
    """
    if sub_name is None or gt_name is None:
        return False
    s = str(sub_name).strip()
    g = str(gt_name).strip()
    if file_system and str(file_system).upper() == "FAT":
        if len(s) == 0 or len(g) == 0:
            return False
        return s[1:].upper() == g[1:].upper()
    return s == g

def find_name_row(filename: str, gt_rows: list, file_system: str):
    """
    Return a GT row matched by name according to names_equal().
    Preference: exact string equality first; otherwise apply names_equal (FAT first-char-ignored).
    """
    if filename is None:
        return None
    # exact match first
    for r in gt_rows:
        if filename == r["filename"]:
            return r
    # relaxed match (e.g., FAT ignore first char)
    for r in gt_rows:
        if names_equal(filename, r["filename"], file_system):
            return r
    return None

# =======================
# HTTP Handler
# =======================
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path != "/api/v1/deleted_file_recovery/evaluate":
            self.send_error(404, "Endpoint not found")
            return

        content_type = self.headers.get('Content-Type', '')
        if not content_type.startswith('application/json'):
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
        file_system = (data.get("file_system", "") or "")
        check_meta = data.get("check_meta", False)

        sector_size = to_int(data.get("sector_size") or data.get("sectorsize") or 512) or 512
        if sector_size <= 0:
            sector_size = 512

        if not base_test_case or not tool_used or not isinstance(files, list):
            self.send_error(400, "Missing or invalid fields: base_test_case, tool_used, files")
            return

        # ----- Weights for AutoDFBench_score (Full, Name, Size) -----
        w_conf = data.get("weights") or {}
        try:
            w_full = float(w_conf.get("full", 0.33))
            w_name = float(w_conf.get("name", 0.33))
            w_size = float(w_conf.get("size", 0.33))
        except Exception:
            w_full, w_name, w_size = 0.33, 0.33, 0.33
        w_sum = w_full + w_name + w_size
        if w_sum <= 0:
            w_full, w_name, w_size, w_sum = 0.33, 0.33, 0.33, 0.99
        w_full /= w_sum
        w_name /= w_sum
        w_size /= w_sum

        # Case sets (kept for validation of size and meta only)
        no_overwrite_set = {s.lower() for s in NO_OVERWITE_TESTS}
        overwrite_set    = {s.lower() for s in OVERWITE_TESTS}
        size_set         = {s.lower() for s in FILE_SIZE_TESTS + SPECAIL_OBJECTS_TESTS}
        mac_time_set     = {s.lower() for s in MAC_TIME_TESTS}

        is_no_overwrite_case = (base_test_case.lower() in no_overwrite_set)
        is_overwrite_case    = (base_test_case.lower() in overwrite_set)
        is_size_case         = (base_test_case.lower() in size_set)
        is_mac_time_case     = (base_test_case.lower() in mac_time_set)

        # ---- Validation (inode never required; do NOT force blocks presence) ----
        seen_filenames = set()
        for file_entry in files:
            file_name = file_entry.get("file_name")
            if file_name in (None, "", "NULL"):
                self.send_error(400, "file_name is required for each submitted file")
                return

            # size required only for FILE_SIZE_TESTS and SPECAIL_OBJECTS_TESTS
            if is_size_case:
                if file_entry.get("file_size") in (None, "", "NULL"):
                    self.send_error(400, "file_size is required for this test case")
                    return

            # timestamps required only for MAC_TIME_TESTS (when meta is checked)
            if is_mac_time_case and check_meta:
                for fld in ("deleted_timestamp", "modified_timestamp", "accessed_timestamp", "changed_timestamp"):
                    ts = file_entry.get(fld, None)
                    if ts is None or not isinstance(ts, int):
                        self.send_error(400, f"{fld} must be provided as an epoch integer timestamp for this test case")
                        return

            if file_name in seen_filenames:
                self.send_error(400, f"Duplicate file_name detected: {file_name}")
                return
            seen_filenames.add(file_name)

        test_case = f"{base_test_case}_{tool_used}"
        print(test_case)

        # ---- Ground truth ----
        gt_entries = get_ground_truth_paths(base_test_case)
        if gt_entries is None:
            self.send_error(400, "Ground truth query failed.")
            return
        if not gt_entries:
            self.send_error(400, "No ground truth data found.")
            return

        # Build GT rows and indices
        gt_rows = []
        gt_by_name = {}
        gt_first_blocks_set = set()
        gt_blocks_set_map = {}   # frozenset -> representative GT row
        first_block_map = {}     # first_block(int) -> [GT rows]

        for row in gt_entries:
            fname = row[0]
            gt_tokens_raw = parse_blocks_list(row[7])
            gt_tokens_exp = expand_block_tokens(gt_tokens_raw)
            gt_set = set(numeric_nonzero_unique_blocks(gt_tokens_exp))
            gt_first = first_min_nonzero_block(gt_tokens_exp)

            r = {
                "filename": fname,
                "deleted_timestamp": int(row[1]) if row[1] not in (None, "", "NULL") else None,
                "modified_timestamp": int(row[2]) if row[2] not in (None, "", "NULL") else None,
                "accessed_timestamp": int(row[3]) if row[3] not in (None, "", "NULL") else None,
                "changed_timestamp":  int(row[4]) if row[4] not in (None, "", "NULL") else None,
                "fbks": row[5],
                "size": int(row[6]) if row[6] not in (None, "", "NULL") else None,
                "blocks_tokens": gt_tokens_exp,
                "blocks_set": gt_set,
                "blocks_first": gt_first  # int or None
            }
            gt_rows.append(r)
            gt_by_name[fname] = r
            if gt_first is not None:
                gt_first_blocks_set.add(gt_first)
                first_block_map.setdefault(gt_first, []).append(r)
            fs = frozenset(gt_set)
            if fs and fs not in gt_blocks_set_map:
                gt_blocks_set_map[fs] = r  # keep first as representative

        gt_count = len(gt_rows)
        all_gt_have_blocks = all(len(r["blocks_tokens"]) > 0 for r in gt_rows)

        # ---------- Metrics ----------
        SS = 0            # submissions that HAVE blocks (non-zero numeric after expansion)
        Full = 0          # exact block-set match to any GT
        First = 0         # first (min positive) block equals some GT's first
        Match = 0         # filename equals some GT filename (FAT: ignore first char)
        Over = 0          # has more unique blocks than paired GT
        Multi = 0         # first matches but other blocks mismatch (not full)
        Size_match = 0

        matched_gt_names = set()  # for classical F1 mapping uniqueness
        FP_count = 0

        details = []
        total_submitted = len(files)

        for file_entry in files:
            filename = file_entry.get("file_name")
            filesize_i = to_int(file_entry.get("file_size"))

            # Parse submission blocks
            sub_tokens_raw = parse_blocks_list(file_entry.get("blocks"))
            sub_tokens_exp = expand_block_tokens(sub_tokens_raw)
            sub_set = set(numeric_nonzero_unique_blocks(sub_tokens_exp))
            sub_first_i = first_min_nonzero_block(sub_tokens_exp)
            fs = frozenset(sub_set) if sub_set else None

            # Counters per requested semantics
            has_blocks = len(sub_set) > 0
            if has_blocks:
                SS += 1

            # Name match (with FAT-relaxed rule)
            name_row = find_name_row(filename, gt_rows, file_system)
            got_Match = name_row is not None
            if got_Match:
                Match += 1

            full_match = bool(fs and fs in gt_blocks_set_map)
            if full_match:
                Full += 1

            first_match = bool(sub_first_i is not None and sub_first_i in gt_first_blocks_set)
            if first_match:
                First += 1

            # Determine pairing candidates for Over/Size/Multi (priority: name → full → all GTs with same first)
            pairing_candidates = []
            if name_row is not None:
                pairing_candidates.append(name_row)
            if full_match:
                pairing_candidates.append(gt_blocks_set_map[fs])
            if first_match:
                pairing_candidates.extend(first_block_map.get(sub_first_i, []))

            # Deduplicate candidates by filename order-preserving
            seen_fn = set()
            uniq_candidates = []
            for cand in pairing_candidates:
                fn = cand["filename"]
                if fn not in seen_fn:
                    uniq_candidates.append(cand)
                    seen_fn.add(fn)

            # Size_match logic (name → full → unique first)
            got_SizeMatch = False
            if filesize_i is not None:
                if name_row is not None and name_row["size"] is not None and name_row["size"] == filesize_i:
                    got_SizeMatch = True
                elif full_match:
                    rg = gt_blocks_set_map[fs]
                    if rg["size"] is not None and rg["size"] == filesize_i:
                        got_SizeMatch = True
                elif first_match:
                    cands = first_block_map.get(sub_first_i, [])
                    if len(cands) == 1:
                        rg = cands[0]
                        if rg["size"] is not None and rg["size"] == filesize_i:
                            got_SizeMatch = True
            if got_SizeMatch:
                Size_match += 1

            # Over logic: compare counts vs ANY plausible paired GT
            got_Over = False
            if has_blocks and uniq_candidates:
                for cand in uniq_candidates:
                    gt_len = len(cand["blocks_set"])
                    if gt_len > 0 and len(sub_set) > gt_len:
                        got_Over = True
                        break
            if got_Over:
                Over += 1

            # Multi logic: first matches some GT, NOT full, and mismatch beyond the first block
            got_Multi = False
            if first_match and not full_match and has_blocks:
                # Prefer name-matched GT if it shares same first; else any GT with same first
                cand_list = []
                if name_row is not None and name_row["blocks_first"] == sub_first_i:
                    cand_list = [name_row]
                else:
                    cand_list = first_block_map.get(sub_first_i, [])

                for cand in cand_list:
                    gt_set = cand["blocks_set"]
                    if not gt_set or sub_first_i not in gt_set:
                        continue
                    if gt_set != sub_set and ((gt_set - {sub_first_i}) != (sub_set - {sub_first_i})):
                        got_Multi = True
                        break
            if got_Multi:
                Multi += 1

            # ======== Classical F1 mapping: Full OR (Name+Size using FAT rule) ========
            mapped_gt_name = None

            # 1) Full (exact block-set)
            if full_match:
                mapped_gt_name = gt_blocks_set_map[fs]["filename"]

            # 2) Name + Size (counts even if blocks differ), name match uses names_equal()
            elif (name_row is not None
                  and filesize_i is not None
                  and name_row["size"] is not None
                  and name_row["size"] == filesize_i):
                mapped_gt_name = name_row["filename"]

            if mapped_gt_name is not None:
                matched_gt_names.add(mapped_gt_name)
                meets_f1 = True
            else:
                FP_count += 1
                meets_f1 = False

            details.append({
                "submitted_file": filename,
                "mapped_gt_for_f1": mapped_gt_name,
                "meets_f1": meets_f1,
                "flags": {
                    "Match": got_Match,
                    "SS": has_blocks,
                    "Full": full_match,
                    "First": first_match,
                    "Over": got_Over,
                    "Multi": got_Multi,
                    "Size_match": got_SizeMatch
                }
            })

        # ---------- Weighted AutoDFBench_score over Full + Name + Size ----------
        # Build per-submission caches we need for scoring
        subs_cache = []  # index-aligned with 'files'
        for file_entry in files:
            filename = file_entry.get("file_name")
            filesize_i = to_int(file_entry.get("file_size"))
            sub_tokens_raw = parse_blocks_list(file_entry.get("blocks"))
            sub_tokens_exp = expand_block_tokens(sub_tokens_raw)
            sub_set = set(numeric_nonzero_unique_blocks(sub_tokens_exp))
            sub_fs = frozenset(sub_set) if sub_set else None
            subs_cache.append({
                "name": filename,
                "size": filesize_i,
                "set": sub_set,
                "fs": sub_fs
            })

        # Precompute GT sets for quick access
        gt_cache = []
        for r in gt_rows:
            gt_cache.append({
                "name": r["filename"],
                "size": r["size"],
                "set": r["blocks_set"],
                "fs": frozenset(r["blocks_set"]) if r["blocks_set"] else None
            })

        # Build candidate (score, sub_idx, gt_idx, tie_break_key) list
        candidates = []
        for si, sub in enumerate(subs_cache):
            for gi, gt in enumerate(gt_cache):
                full = bool(sub["fs"] is not None and gt["fs"] is not None and sub["fs"] == gt["fs"] and len(gt["set"]) > 0)
                name = names_equal(sub["name"], gt["name"], file_system)  # FAT-aware name check
                size = (sub["size"] is not None and gt["size"] is not None and sub["size"] == gt["size"])
                score = (w_full * (1 if full else 0)) + (w_name * (1 if name else 0)) + (w_size * (1 if size else 0))
                if score > 0:
                    # tie-breaker: prefer Full, then Name, then Size, then larger set size (stabiliser)
                    tie = (1 if full else 0, 1 if name else 0, 1 if size else 0, len(sub["set"]))
                    candidates.append((score, si, gi, tie))

        # Greedy one-to-one selection by score (desc), with tie-breakers
        candidates.sort(key=lambda x: (x[0], x[3]), reverse=True)
        used_sub = set()
        used_gt = set()
        weighted_pairs = []  # (score, sub_idx, gt_idx, components)
        weighted_sum = 0.0

        for score, si, gi, tie in candidates:
            if si in used_sub or gi in used_gt:
                continue
            used_sub.add(si)
            used_gt.add(gi)
            sub = subs_cache[si]; gt = gt_cache[gi]
            comp_full = 1 if (sub["fs"] is not None and gt["fs"] is not None and sub["fs"] == gt["fs"] and len(gt["set"]) > 0) else 0
            comp_name = 1 if names_equal(sub["name"], gt["name"], file_system) else 0  # FAT-aware
            comp_size = 1 if (sub["size"] is not None and gt["size"] is not None and sub["size"] == gt["size"]) else 0
            weighted_pairs.append({
                "submitted_file": sub["name"],
                "gt_file": gt["name"],
                "score": score,
                "components": {
                    "full": comp_full,
                    "name": comp_name,
                    "size": comp_size
                }
            })
            weighted_sum += score

        # Normalise by GT count to keep score in [0,1]
        auto_dfbench_weighted = (weighted_sum / gt_count) if gt_count > 0 else 0.0

        # --- Classical F1 for reference / DB ---
        TP = len(matched_gt_names)
        FN = max(0, gt_count - TP)
        FP = max(0, FP_count)

        precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
        recall    = TP / (TP + FN) if (TP + FN) > 0 else 0.0
        f1_score  = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        # store to DB (keep classical F1 here)
        insert_result_to_db(base_test_case, f"{base_test_case}_{tool_used}", TP, FP, FN, precision, recall, f1_score)

        response = {
            "tool_used": tool_used,
            "base_test_case": base_test_case,

            "sector_size": sector_size,

            "total_ground_truth_files": gt_count,
            "total_ground_truth_files_considered": gt_count,
            "all_gt_have_dfr_blocks": all_gt_have_blocks,

            "total_submitted_files": total_submitted,

            # Classical metrics
            "true_positives": TP,
            "false_positives": FP,
            "false_negatives": FN,

            "precision": precision,
            "recall": recall,

            # Weighted score (Full/Name/Size with weights ~0.333 each by default)
            "AutoDFBench_score": auto_dfbench_weighted,
            "weights_used": {"full": w_full, "name": w_name, "size": w_size},
            "weighted_selected_pairs": weighted_pairs,

            # Requested counters
            "Rec": total_submitted,
            "SS": SS,           # submissions that HAVE blocks
            "Full": Full,       # exact block-set match
            "First": First,     # first block equals some GT first
            "Match": Match,     # filename equals GT filename (FAT: ignore first char)
            "Over": Over,       # more blocks than a plausible GT pairing
            "Multi": Multi,     # first matches, others mismatch (not full)
            "Size_match": Size_match,

            "GT_COUNT": gt_count,

            "details": details
        }

        # Persist JSON
        _save_response_json(f"{base_test_case}_{tool_used}", response)

        # Append CSV summary line (REC column: TP as before)
        _append_summary_csv(
            base_test_case=base_test_case,
            total_submitted_files=total_submitted,
            auto_dfbench_score=auto_dfbench_weighted,
            rec=TP,
            ss=SS,
            first=First,
            full=Full,
            match=Match,
            over=Over,
            multi=Multi
        )

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
