#!/usr/bin/env python3
import argparse, json, sys, os, tempfile, shutil, csv
from typing import List, Dict, Any, Iterable, Union

# ---------- CONFIG: CSV output path is a VARIABLE (edit as you like) ----------
CSV_OUTPUT_PATH = "./DFR_results/dfr_autodfbench_summary.csv"

# Desired CSV schema & order
CSV_FIELDS = [
    "base_test_case",
    "total_submitted_files",
    "AutoDFBench_score",
    "SS",
    "First",
    "Full",
    "Match",
    "Over",
    "Mutli",  # CSV column 'Mutli' maps from JSON 'Multi' or 'Mutli'
]

def _to_int(x):
    try:
        return int(x)
    except Exception:
        return 0

def _to_float(x):
    try:
        return float(x)
    except Exception:
        return 0.0

def normalize_record(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and normalise a single JSON record into the CSV schema.
    Falls back sensibly if a field is missing. Maps JSON 'Multi' -> CSV 'Mutli'.
    """
    row = {}
    row["base_test_case"]        = d.get("base_test_case", "")
    row["total_submitted_files"] = _to_int(d.get("total_submitted_files", d.get("total_submitted_files_considered", 0)))
    row["AutoDFBench_score"]     = _to_float(d.get("AutoDFBench_score", 0))
    row["SS"]                    = _to_int(d.get("SS", 0))
    row["First"]                 = _to_int(d.get("First", 0))
    row["Full"]                  = _to_int(d.get("Full", 0))
    row["Match"]                 = _to_int(d.get("Match", 0))
    row["Over"]                  = _to_int(d.get("Over", 0))

    # JSON might have "Multi" (correct spelling) – map to CSV column "Mutli"
    multi_val = d.get("Mutli", d.get("Multi", 0))
    row["Mutli"]                 = _to_int(multi_val)
    return row

def load_json(path: str) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    if path == "-" or not path:
        data = sys.stdin.read()
        return json.loads(data)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def ensure_rows(records: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Accepts either a single object or a list of objects and returns a list of normalised rows.
    """
    rows = []
    if isinstance(records, dict):
        rows.append(normalize_record(records))
    elif isinstance(records, list):
        for rec in records:
            if isinstance(rec, dict):
                rows.append(normalize_record(rec))
    else:
        raise ValueError("JSON must be an object or a list of objects.")
    return rows

def read_existing_csv(csv_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        out = []
        for r in reader:
            out.append({k: r.get(k, "") for k in CSV_FIELDS})
        return out

def upsert_rows(existing: List[Dict[str, Any]], incoming: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Update by base_test_case if it exists; otherwise append.
    """
    index = {row.get("base_test_case", ""): i for i, row in enumerate(existing)}
    for row in incoming:
        key = row.get("base_test_case", "")
        if key in index and key != "":
            i = index[key]
            for field in CSV_FIELDS:
                existing[i][field] = row.get(field, existing[i].get(field, ""))
        else:
            existing.append(row)
            if key != "":
                index[key] = len(existing) - 1
    return existing

def write_csv_atomic(csv_path: str, rows: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".csv", dir=os.path.dirname(csv_path) or ".")
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k, "") for k in CSV_FIELDS})
        shutil.move(tmp_path, csv_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def main():
    p = argparse.ArgumentParser(description="Append/update AutoDFBench JSON summary into a CSV.")
    p.add_argument("json_input", help="Path to JSON file (or '-' for STDIN).")
    args = p.parse_args()

    try:
        data = load_json(args.json_input)
        new_rows = ensure_rows(data)
    except Exception as e:
        print(f"ERROR: failed to read/parse JSON: {e}", file=sys.stderr)
        sys.exit(1)

    existing = read_existing_csv(CSV_OUTPUT_PATH)
    combined = upsert_rows(existing, new_rows)
    write_csv_atomic(CSV_OUTPUT_PATH, combined)
    print(f"Updated: {CSV_OUTPUT_PATH} ({len(combined)} row(s))")

if __name__ == "__main__":
    main()
