# autodfbench/eval/deleted_file_recovery.py
import os
import re
import csv
import json
import sys
import unicodedata
from pathlib import Path

from autodfbench.db_dfr import get_ground_truth_paths, insert_result_to_db

# ---------- Force UTF-8 stdio so prints/logging don't crash on non-ASCII ----------
def _force_utf8_stdio():
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_force_utf8_stdio()

# -------------------- Test sets (kept from your API) --------------------
NO_OVERWITE_TESTS = [
    "DFR-01/fat-01","DFR-02/fat-02","DFR-03/fat-03","DFR-05/fat-05","DFR-05/fat-0-braid5",
    "DFR-05/fat-05-nest","DFR-06/fat-06","DFR-09/fat-09","DFR-11/fat-11","DFR-01/xfat-01","DFR-02/xfat-02",
    "DFR-03/xfat-03","DFR-05/xfat-05","DFR-05/xfat-05-braid","DFR-05/xfat-05-nest","DFR-06/xfat-06",
    "DFR-09/xfat-09","DFR-011/xfat-11","DFR-01/ntfs-01","DFR-02/ntfs-02","DFR-03/ntfs-03","DFR-05/ntfs-05",
    "DFR-06/ntfs-06","DFR-09/ntfs-09","DFR-11/ntfs-11","DFR-01/ext-01","DFR-02/ext-02","DFR-03/ext-03","DFR-05/ext-05",
    "DFR-06/ext-06","DFR-09/ext-09","DFR-11/ext-11",
]

OVERWITE_TESTS = [
    "DFR-07/fat-07","DFR-07/fat-07-one","DFR-07/fat-07-two","DFR-08/fat-08","DFR-10/fat-10","DFR-12/fat-12","DFR-13/fat-13",
    "DFR-07/xfat-07","DFR-07/xfat-07-one","DFR-07/xfat-07-two","DFR-08/fat-08","DFR-10/fat-10","DFR-12/fat-12","DFR-13/fat-13",
    "DFR-07/ntfs-07","DFR-07/ntfs-07-one","DFR-07/ntfs-07-two","DFR-08/ntfs-08","DFR-10/ntfs-10","DFR-12/ntfs-12","DFR-13/ntfs-13",
    "DFR-07/ext-07","DFR-07/ext-07-one","DFR-07/ext-07-two","DFR-08/ext-08","DFR-10/ext-10","DFR-12/ext-12","DFR-13/ext-13",
]

FILE_SIZE_TESTS = [
    "DFR-01/fat-01","DFR-07/fat-07","DFR-011/fat-11",
    "DFR-01/ntfs-01","DFR-07/ntfs-07","DFR-011/ntfs-11",
    "DFR-01/ext-01","DFR-07/ext-07","DFR-011/ext-11",
]

MAC_TIME_TESTS = ["DFR-01/fat-01","DFR-01/ntfs-01","DFR-01/ext-01"]

NON_LATIN_CHAR_TETS = ["DFR-04/fat-04","DFR-04/ext-04","DFR-04/ntfs-04"]

RECYCLE_DEL_TESTS = ["DFR-01/ext-01-recycle","DFR-01/fat-01-recycle","DFR-01/ntfs-01-recycle"]

SPECAIL_NTFS_TEST = ["DFR-11/ntfs-11-compress","DFR-11/ntfs-11-mft"]

SPECAIL_OBJECTS_TESTS = ["DFR-14/fat-14","DFR-14/ntfs-14","DFR-14/ext-14"]


# -------------------- Report helpers (optional) --------------------
def _safe_filename(name: str) -> str:
    s = (name or "").replace(os.sep, "_").replace("/", "_").replace("\\", "_")
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s.strip("_") or "result"

def _save_response_json(results_dir: Path, test_case: str, payload: dict) -> None:
    try:
        results_dir.mkdir(parents=True, exist_ok=True)
        fname = results_dir / f"{_safe_filename(test_case)}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def _append_summary_csv(
    results_dir: Path,
    test_set_used: str,
    base_test_case: str,
    total_submitted_files: int,
    tp: int,
    fp: int,
    fn: int,
    precision: float,
    recall: float,
    f1: float,
    ss: int,
    first: int,
    full: int,
    match: int,
    over: int,
    multi: int,
    size_match: int,
) -> None:
    try:
        results_dir.mkdir(parents=True, exist_ok=True)
        csv_name = f"summary_{_safe_filename(test_set_used)}.csv"
        csv_path = results_dir / csv_name
        file_exists = csv_path.exists() and csv_path.stat().st_size > 0

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "base_test_case","total_submitted_files","TP","FP","FN","precision","recall","F1",
                    "SS","First","Full","Match","Over","Multi","Size_match"
                ])
            writer.writerow([
                base_test_case, int(total_submitted_files),
                int(tp), int(fp), int(fn),
                float(precision), float(recall), float(f1),
                int(ss), int(first), int(full), int(match), int(over), int(multi), int(size_match)
            ])
    except Exception:
        pass


# -------------------- Core helpers (copied from your API) --------------------
RANGE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")

def parse_blocks_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip() != ""]
    s = str(v).strip()
    if s == "":
        return []
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
        s = s[1:-1]
    parts = [p.strip() for p in (s.split(",") if "," in s else s.split())]
    return [p for p in parts if p]

def expand_block_tokens(tokens):
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
    nums = []
    for t in (block_tokens or []):
        ts = str(t).strip()
        if ts.isdigit():
            val = int(ts)
            if val != 0:
                nums.append(val)
    return sorted(set(nums))

def first_min_nonzero_block(tokens):
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

# ----- Unicode name normalisation -----
_BIDI_INVIS = {
    "\u200e","\u200f","\u202a","\u202b","\u202c","\u202d","\u202e",
    "\u2066","\u2067","\u2068","\u2069","\ufeff","\u200b","\u200c","\u200d",
}

_TRANSLATE_MAP = {
    ord("\u0660"):"0", ord("\u0661"):"1", ord("\u0662"):"2", ord("\u0663"):"3",
    ord("\u0664"):"4", ord("\u0665"):"5", ord("\u0666"):"6", ord("\u0667"):"7",
    ord("\u0668"):"8", ord("\u0669"):"9",
    ord("\u06F0"):"0", ord("\u06F1"):"1", ord("\u06F2"):"2", ord("\u06F3"):"3",
    ord("\u06F4"):"4", ord("\u06F5"):"5", ord("\u06F6"):"6", ord("\u06F7"):"7",
    ord("\u06F8"):"8", ord("\u06F9"):"9",
    ord("\u06D4"): ".", ord("\u066B"): ".", ord("\u2024"): ".", ord("\uFF0E"): ".",
    ord("\uFF61"): ".", ord("\uFE52"): ".", ord("\u2219"): ".", ord("\u22C5"): ".",
    ord("\u00B7"): ".", ord("\u30FB"): ".",
}

def _is_arabic_cp(cp: int) -> bool:
    return ((0x0600 <= cp <= 0x06FF) or (0x0750 <= cp <= 0x077F) or (0x08A0 <= cp <= 0x08FF) or
            (0xFB50 <= cp <= 0xFDFF) or (0xFE70 <= cp <= 0xFEFF))

def _contains_arabic(s: str) -> bool:
    try:
        return any(_is_arabic_cp(ord(ch)) for ch in s)
    except Exception:
        return False

_ARABIC_TXT_SUFFIX_RE = re.compile(
    r'(?:[.\u06D4\u066B\u2024\uFF0E\uFF61\uFE52\u2219\u22C5\u00B7\u30FB])?'
    r'(?:t|T)(?:x|X)(?:t|T)'
    r'[0-9\u0660-\u0669\u06F0-\u06F9]+$'
)

def _strip_invisible(s: str) -> str:
    return "".join(ch for ch in s if ch not in _BIDI_INVIS)

def _map_compat_chars(s: str) -> str:
    return s.translate(_TRANSLATE_MAP)

def _norm_vis_base(name: str) -> str:
    if name is None:
        return None
    base = os.path.basename(str(name)).strip()
    base = unicodedata.normalize("NFC", base)
    base = _strip_invisible(base)
    base = _map_compat_chars(base)
    return base

def _arabic_stem(s: str) -> str:
    if not s:
        return s
    if _contains_arabic(s):
        return _ARABIC_TXT_SUFFIX_RE.sub("", s)
    return s

def names_equal(sub_name: str, gt_name: str, file_system: str) -> bool:
    s = _norm_vis_base(sub_name)
    g = _norm_vis_base(gt_name)
    if s is None or g is None:
        return False
    if _contains_arabic(s) or _contains_arabic(g):
        return _arabic_stem(s) == _arabic_stem(g)
    if (file_system or "").upper() == "FAT":
        if not s or not g:
            return False
        return s[1:].casefold() == g[1:].casefold()
    return s == g

def find_name_row(filename: str, gt_rows: list, file_system: str):
    if filename is None:
        return None
    for r in gt_rows:
        if names_equal(filename, r["filename"], file_system):
            return r
    return None

def find_size_row(filesize: int, gt_rows: list, matched_gt_names: set):
    if filesize is None:
        return None
    for r in gt_rows:
        if r["size"] is not None and r["size"] == filesize and r["filename"] not in matched_gt_names:
            return r
    return None

def find_name_size_row(filename: str, filesize: int, gt_rows: list, matched_gt_names: set, file_system: str):
    if filename is None or filesize is None:
        return None
    for r in gt_rows:
        if r["filename"] in matched_gt_names:
            continue
        if r["size"] is not None and r["size"] == filesize and names_equal(filename, r["filename"], file_system):
            return r
    return None

def find_mac_row(mod_ts: int, acc_ts: int, chg_ts: int, gt_rows: list, matched_gt_names: set):
    for r in gt_rows:
        if r["filename"] in matched_gt_names:
            continue
        if (r["modified_timestamp"] is not None and r["accessed_timestamp"] is not None and r["changed_timestamp"] is not None and
            mod_ts is not None and acc_ts is not None and chg_ts is not None and
            r["modified_timestamp"] == mod_ts and r["accessed_timestamp"] == acc_ts and r["changed_timestamp"] == chg_ts):
            return r
    return None


# -------------------- Evaluator entry point --------------------
def evaluate_deleted_file_recovery(payload: dict) -> dict:
    """
    Shared evaluator for API + CSV/CI.

    Required payload fields (API-compatible):
      - base_test_case: str
      - tool_used: str
      - test_set: one of allowed keys
      - files: list of {file_name, blocks, file_size?, modified_timestamp?, accessed_timestamp?, changed_timestamp? ...}
    Optional:
      - file_system: "FAT"/"NTFS"/"EXT"/...
      - check_meta: bool
      - sector_size: int
      - weights: dict (diagnostics only)
      - write_db: bool (default True)
      - write_reports: bool (default True)
      - results_dir: str (override)
    """
    base_test_case = payload.get("base_test_case")
    tool_used = payload.get("tool_used")
    files = payload.get("files", [])
    file_system = (payload.get("file_system", "") or "")
    check_meta = bool(payload.get("check_meta", False))

    test_set_raw = (payload.get("test_set") or "").strip().upper()
    ALLOWED_TEST_SETS = {
        "NO_OVERWITE_TESTS",
        "OVERWITE_TESTS",
        "FILE_SIZE_TESTS",
        "MAC_TIME_TESTS",
        "SPECAIL_OBJECTS_TESTS",
        "NON_LATIN_CHAR_TETS",
        "SPECAIL_NTFS_TEST",
        "RECYCLE_DEL_TESTS",
    }
    if not test_set_raw:
        raise ValueError("Field 'test_set' is required and must be one of: " + ", ".join(sorted(ALLOWED_TEST_SETS)))
    if test_set_raw not in ALLOWED_TEST_SETS:
        raise ValueError(f"Invalid 'test_set': {test_set_raw}. Allowed: " + ", ".join(sorted(ALLOWED_TEST_SETS)))

    if not base_test_case or not tool_used or not isinstance(files, list):
        raise ValueError("Missing or invalid fields: base_test_case, tool_used, files")

    write_db = bool(payload.get("write_db", True))
    write_reports = bool(payload.get("write_reports", True))
    results_dir = Path(payload.get("results_dir") or "./dfr_tests")

    sector_size = to_int(payload.get("sector_size") or payload.get("sectorsize") or 512) or 512
    if sector_size <= 0:
        sector_size = 512

    # Diagnostic weights input (ordering only)
    w_conf = payload.get("weights") or {}
    try:
        w_full = float(w_conf.get("full", 0.33))
        w_name = float(w_conf.get("name", 0.33))
        w_size = float(w_conf.get("size", 0.33))
    except Exception:
        w_full, w_name, w_size = 0.33, 0.33, 0.33
    w_sum = w_full + w_name + w_size
    if w_sum <= 0:
        w_full, w_name, w_size, w_sum = 0.33, 0.33, 0.33, 0.99
    w_full /= w_sum; w_name /= w_sum; w_size /= w_sum

    # MAC-time weights (diagnostics)
    try:
        w_mod = float(w_conf.get("modify_time_stamp", 1.0/3.0))
        w_acc = float(w_conf.get("access_time_stamp", 1.0/3.0))
        w_chg = float(w_conf.get("change_time_stamp", 1.0/3.0))
    except Exception:
        w_mod, w_acc, w_chg = 1.0/3.0, 1.0/3.0, 1.0/3.0
    w_mac_sum = w_mod + w_acc + w_chg
    if w_mac_sum <= 0:
        w_mod, w_acc, w_chg, w_mac_sum = 1.0, 1.0, 1.0, 3.0
    w_mod /= w_mac_sum; w_acc /= w_mac_sum; w_chg /= w_mac_sum

    # Logic flags
    test_set_key = test_set_raw
    test_set_used = test_set_key

    is_pure_size_f1_case       = (test_set_key == "FILE_SIZE_TESTS")
    is_mac_time_case           = (test_set_key == "MAC_TIME_TESTS")
    is_non_latin_case          = (test_set_key == "NON_LATIN_CHAR_TETS")
    is_special_ntfs_case       = (test_set_key == "SPECAIL_NTFS_TEST")
    is_special_objects_case    = (test_set_key == "SPECAIL_OBJECTS_TESTS")
    is_name_size_case          = (is_special_ntfs_case or is_special_objects_case)
    is_default_full_match_case = (test_set_key in {"NO_OVERWITE_TESTS", "OVERWITE_TESTS", "RECYCLE_DEL_TESTS"})
    is_size_validation = (test_set_key == "FILE_SIZE_TESTS")

    # Validate submissions
    seen_filenames = set()
    for file_entry in files:
        file_name = file_entry.get("file_name")
        if file_name in (None, "", "NULL"):
            raise ValueError("file_name is required for each submitted file")

        if is_size_validation or is_name_size_case:
            if file_entry.get("file_size") in (None, "", "NULL"):
                raise ValueError("file_size is required for FILE_SIZE_TESTS and SPECAIL_* tests")

        if is_mac_time_case and check_meta:
            for fld in ("deleted_timestamp", "modified_timestamp", "accessed_timestamp", "changed_timestamp"):
                ts = file_entry.get(fld, None)
                if ts is None or not isinstance(ts, int):
                    raise ValueError(f"{fld} must be provided as an epoch int for MAC_TIME_TESTS when check_meta is true")

        if file_name in seen_filenames:
            raise ValueError(f"Duplicate file_name detected: {file_name}")
        seen_filenames.add(file_name)

    # Ground truth
    gt_entries = get_ground_truth_paths(base_test_case)
    if gt_entries is None:
        raise ValueError("Ground truth query failed.")
    if not gt_entries:
        raise ValueError("No ground truth data found.")

    # Build GT rows and indices
    gt_rows = []
    gt_first_blocks_set = set()
    gt_blocks_set_map = {}
    first_block_map = {}

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
            "blocks_first": gt_first,
        }
        gt_rows.append(r)
        if gt_first is not None:
            gt_first_blocks_set.add(gt_first)
            first_block_map.setdefault(gt_first, []).append(r)
        fs = frozenset(gt_set)
        if fs and fs not in gt_blocks_set_map:
            gt_blocks_set_map[fs] = r

    gt_count = len(gt_rows)
    all_gt_have_blocks = all(len(r["blocks_tokens"]) > 0 for r in gt_rows)

    # Metrics counters
    SS = Full = First = Match = Over = Multi = Size_match = 0
    matched_gt_names = set()
    FP_count = 0
    details = []
    total_submitted = len(files)

    # Iterate submissions
    for file_entry in files:
        filename = file_entry.get("file_name")
        filesize_i = to_int(file_entry.get("file_size"))

        sub_tokens_raw = parse_blocks_list(file_entry.get("blocks"))
        sub_tokens_exp = expand_block_tokens(sub_tokens_raw)
        sub_set = set(numeric_nonzero_unique_blocks(sub_tokens_exp))
        sub_first_i = first_min_nonzero_block(sub_tokens_exp)
        fs = frozenset(sub_set) if sub_set else None

        mod_i = to_int(file_entry.get("modified_timestamp"))
        acc_i = to_int(file_entry.get("accessed_timestamp"))
        chg_i = to_int(file_entry.get("changed_timestamp"))

        has_blocks = len(sub_set) > 0
        if has_blocks:
            SS += 1

        name_row = find_name_row(filename, gt_rows, file_system)
        if name_row is not None:
            Match += 1

        full_match = bool(fs and fs in gt_blocks_set_map)
        if full_match:
            Full += 1

        first_match = bool(sub_first_i is not None and sub_first_i in gt_first_blocks_set)
        if first_match:
            First += 1

        # candidates for diagnostics
        pairing_candidates = []
        if name_row is not None:
            pairing_candidates.append(name_row)
        if full_match:
            pairing_candidates.append(gt_blocks_set_map[fs])
        if first_match:
            pairing_candidates.extend(first_block_map.get(sub_first_i, []))

        seen_fn = set()
        uniq_candidates = []
        for cand in pairing_candidates:
            fn = cand["filename"]
            if fn not in seen_fn:
                uniq_candidates.append(cand)
                seen_fn.add(fn)

        # Size_match
        got_SizeMatch = False
        if filesize_i is not None:
            if is_pure_size_f1_case:
                if any(r["size"] is not None and r["size"] == filesize_i for r in gt_rows):
                    got_SizeMatch = True
            else:
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

        # Over
        got_Over = False
        if has_blocks and uniq_candidates:
            for cand in uniq_candidates:
                gt_len = len(cand["blocks_set"])
                if gt_len > 0 and len(sub_set) > gt_len:
                    got_Over = True
                    break
        if got_Over:
            Over += 1

        # Multi
        got_Multi = False
        if first_match and not full_match and has_blocks:
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

        # F1 mapping
        ns_row = None
        mapped_gt_name = None

        if is_mac_time_case:
            mac_row = find_mac_row(mod_i, acc_i, chg_i, gt_rows, matched_gt_names)
            if mac_row is not None:
                mapped_gt_name = mac_row["filename"]
        elif is_pure_size_f1_case:
            size_row = find_size_row(filesize_i, gt_rows, matched_gt_names)
            if size_row is not None:
                mapped_gt_name = size_row["filename"]
        elif is_non_latin_case:
            for r in gt_rows:
                if r["filename"] in matched_gt_names:
                    continue
                if names_equal(filename, r["filename"], file_system):
                    mapped_gt_name = r["filename"]
                    break
        elif is_name_size_case:
            ns_row = find_name_size_row(filename, filesize_i, gt_rows, matched_gt_names, file_system)
            if ns_row is not None:
                mapped_gt_name = ns_row["filename"]
        elif is_default_full_match_case:
            if full_match:
                mapped_gt_name = gt_blocks_set_map[fs]["filename"]
        else:
            if full_match:
                mapped_gt_name = gt_blocks_set_map[fs]["filename"]

        if mapped_gt_name is not None:
            matched_gt_names.add(mapped_gt_name)
            meets_f1_mapped = True
        else:
            FP_count += 1
            meets_f1_mapped = False

        flags_dict = {
            "Match": name_row is not None,
            "SS": has_blocks,
            "Full": full_match,
            "First": first_match,
            "Over": got_Over,
            "Multi": got_Multi,
            "Size_match": got_SizeMatch,
        }

        # details meets_f1
        if is_non_latin_case:
            meets_f1_detail = (name_row is not None)
            mapped_detail = name_row["filename"] if name_row is not None else None
        elif is_name_size_case:
            meets_f1_detail = (ns_row is not None)
            mapped_detail = ns_row["filename"] if ns_row is not None else None
        else:
            meets_f1_detail = meets_f1_mapped
            mapped_detail = mapped_gt_name

        details.append({
            "submitted_file": filename,
            "mapped_gt_for_f1": mapped_detail,
            "meets_f1": meets_f1_detail,
            "flags": flags_dict,
        })

    # Final F1
    if is_non_latin_case:
        TP = Match
        FP = max(0, total_submitted - TP)
        FN = max(0, gt_count - TP)
    else:
        TP = len(matched_gt_names)
        FN = max(0, gt_count - TP)
        FP = max(0, FP_count)

    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall    = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    f1_score  = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    testcase = f"{base_test_case}_{tool_used}"
    if write_db:
        insert_result_to_db(base_test_case, testcase, TP, FP, FN, precision, recall, f1_score)

    response = {
        "tool_used": tool_used,
        "base_test_case": base_test_case,
        "test_set_used": test_set_used,
        "sector_size": sector_size,
        "total_ground_truth_files": gt_count,
        "total_ground_truth_files_considered": gt_count,
        "all_gt_have_dfr_blocks": all_gt_have_blocks,
        "total_submitted_files": total_submitted,
        "true_positives": TP,
        "false_positives": FP,
        "false_negatives": FN,
        "precision": precision,
        "recall": recall,
        "F1": f1_score,
        "AutoDFBench_score": f1_score,
        "Rec": total_submitted,
        "SS": SS,
        "Full": Full,
        "First": First,
        "Match": Match,
        "Over": Over,
        "Multi": Multi,
        "Size_match": Size_match,
        "GT_COUNT": gt_count,
        "details": details,
        "weighted_selected_pairs": [],  # kept for API compatibility; you can re-add later if needed
    }

    if write_reports:
        _save_response_json(results_dir, testcase, response)
        _append_summary_csv(
            results_dir=results_dir,
            test_set_used=test_set_used,
            base_test_case=base_test_case,
            total_submitted_files=total_submitted,
            tp=TP, fp=FP, fn=FN,
            precision=precision, recall=recall, f1=f1_score,
            ss=SS, first=First, full=Full, match=Match, over=Over, multi=Multi, size_match=Size_match,
        )

    return response
