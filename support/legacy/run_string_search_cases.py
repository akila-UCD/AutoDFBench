#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import requests

API_DEFAULT = "http://localhost:8000/api/v1/string-search/evaluate"

def run_extract(python_exec: str, script_path: Path, image_path: Path, case_string: str, base_test_case: str) -> dict:
    """
    Runs:
      python3 support/string_search_extract.py <image> "<Case/String>" --base-test-case "<testcase>" --tool-used "IPED Version 3.18.13"
    Returns parsed JSON (dict). Raises on failure.
    """
    cmd = [
        python_exec,
        str(script_path),
        str(image_path),
        case_string,
        "--base-test-case", base_test_case,
        "--tool-used", "IPED Version 3.18.13",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Extractor failed for {base_test_case}: {proc.stderr.strip() or proc.stdout.strip()}")
    out = (proc.stdout or "").strip()
    if not out:
        raise ValueError(f"No JSON output from extractor for {base_test_case}")
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from extractor for {base_test_case}: {e}\nOutput was:\n{out[:1000]}")

def post_to_api(api_url: str, payload: dict) -> dict:
    """
    POST the JSON to the evaluation API; return parsed JSON response.
    """
    headers = {"Content-Type": "application/json"}
    r = requests.post(api_url, headers=headers, data=json.dumps(payload))
    r.raise_for_status()
    return r.json()

def ensure_cols(df: pd.DataFrame):
    # Add columns if they don't exist yet
    for col in ["Active Hits", "Deleted Hits", "Unallocated Hits", "f1_score"]:
        if col not in df.columns:
            df[col] = pd.NA
    return df

def main():
    ap = argparse.ArgumentParser(description="Run all string-search test cases, call evaluation API, and update CSV.")
    ap.add_argument("--csv", required=True, help="Path to the CSV containing 'Test Case' and 'Case/String' columns.")
    ap.add_argument("--image", required=True, help="Path to the disk image (e.g., ss-win-07-25-18.dd).")
    ap.add_argument("--python", default="python3", help="Python executable to run string_search_extract.py (default: python3).")
    ap.add_argument("--script", default="support/string_search_extract.py", help="Path to string_search_extract.py.")
    ap.add_argument("--api-url", default=API_DEFAULT, help=f"Evaluation API URL (default: {API_DEFAULT})")
    ap.add_argument("--os", default="windows", help='OS tag to include in payload (default: "windows").')
    ap.add_argument("--save-json-dir", default=None, help="Optional dir to save request/response JSON per test case.")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    image_path = Path(args.image)
    script_path = Path(args.script)

    if not csv_path.exists():
        print(f"[ERROR] CSV not found: {csv_path}", file=sys.stderr); sys.exit(1)
    if not image_path.exists():
        print(f"[ERROR] Image not found: {image_path}", file=sys.stderr); sys.exit(1)
    if not script_path.exists():
        print(f"[ERROR] Extractor script not found: {script_path}", file=sys.stderr); sys.exit(1)

    df = pd.read_csv(csv_path)
    # Validate required columns
    for required in ["Test Case", "Case/String"]:
        if required not in df.columns:
            print(f"[ERROR] CSV missing required column: '{required}'", file=sys.stderr); sys.exit(1)

    df = ensure_cols(df)

    save_dir = Path(args.save_json_dir) if args.save_json_dir else None
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    for idx, row in df.iterrows():
        base_test_case = str(row["GT_TestCase"]).strip()
        case_string = str(row["Case/String"]).strip()

        if not base_test_case or not case_string:
            print(f"[WARN] Skipping row {idx} due to empty Test Case or Case/String.", file=sys.stderr)
            continue

        try:
            # 1) run extractor
            extract_json = run_extract(args.python, script_path, image_path, case_string, base_test_case)

            # Inject OS (as you specified)
            extract_json["os"] = args.os

            if save_dir:
                (save_dir / f"jsons/{base_test_case}_extract.json").write_text(json.dumps(extract_json, ensure_ascii=False, indent=2))

            # 2) POST to API
            resp = post_to_api(args.api_url, extract_json)

            if save_dir:
                (save_dir / f"jsons/{base_test_case}_eval.json").write_text(json.dumps(resp, ensure_ascii=False, indent=2))

            # 3) Update CSV fields from response
            # hit_counts_by_type might be missing; handle safely
            h = resp.get("hit_counts_by_type", {}) or {}
            df.at[idx, "Active Hits"] = h.get("active")
            df.at[idx, "Deleted Hits"] = h.get("deleted")
            df.at[idx, "Unallocated Hits"] = h.get("unallocated")
            df.at[idx, "f1_score"] = resp.get("f1_score")

            print(f"[OK] {base_test_case}: TP={resp.get('true_positives')} FP={resp.get('false_positives')} FN={resp.get('false_negatives')} F1={resp.get('f1_score')}")

        except Exception as e:
            print(f"[ERR] {base_test_case}: {e}", file=sys.stderr)
            # leave row as-is and continue

    # Save the CSV **in place**
    df.to_csv(csv_path, index=False)
    print(f"[DONE] Updated CSV saved to {csv_path}")

if __name__ == "__main__":
    main()
