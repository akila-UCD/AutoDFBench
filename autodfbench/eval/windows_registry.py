# autodfbench/eval/windows_registry.py
import os
from pathlib import Path
import json

from autodfbench.db_windows_registry import (
    get_configs, get_ground_truth_paths, insert_result_to_db
)

def compare_csv_files_detailed(submitted_csv_path, gt_file_path):
    """
    Compare CSV files based on PATH and VALUE columns only.
    (Same logic as api_v2.py)
    """
    try:
        import pandas as pd

        # Read CSV files with robust error handling
        try:
            submitted_df = pd.read_csv(submitted_csv_path, dtype=str, keep_default_na=False)
        except Exception:
            return None

        try:
            gt_df = pd.read_csv(gt_file_path, dtype=str, keep_default_na=False)
        except Exception:
            return None

        # Normalize column names (strip whitespace)
        submitted_df.columns = submitted_df.columns.str.strip()
        gt_df.columns = gt_df.columns.str.strip()

        required_columns = ['PATH', 'VALUE']
        for col in required_columns:
            if col not in submitted_df.columns:
                return None
            if col not in gt_df.columns:
                return None

        # Clean data - remove metadata and summary rows
        submitted_clean = submitted_df[
            ~submitted_df['PATH'].str.contains('FILE_INFO|PROCESSING_SUMMARY', na=False, case=False, regex=True)
        ].copy()

        gt_clean = gt_df[
            ~gt_df['PATH'].str.contains('FILE_INFO|PROCESSING_SUMMARY', na=False, case=False, regex=True)
        ].copy()

        def create_comparison_key(row):
            try:
                path = str(row['PATH']).strip() if pd.notna(row['PATH']) else ""
                value = str(row['VALUE']).strip() if pd.notna(row['VALUE']) else ""
                return f"{path}|{value}"
            except Exception:
                return ""

        submitted_keys = set()
        for _, row in submitted_clean.iterrows():
            key = create_comparison_key(row)
            if key:
                submitted_keys.add(key)

        gt_keys = set()
        for _, row in gt_clean.iterrows():
            key = create_comparison_key(row)
            if key:
                gt_keys.add(key)

        intersection = submitted_keys & gt_keys
        true_positives = len(intersection)
        false_positives = len(submitted_keys - gt_keys)
        false_negatives = len(gt_keys - submitted_keys)

        precision = true_positives / len(submitted_keys) if len(submitted_keys) > 0 else 0.0
        recall = true_positives / len(gt_keys) if len(gt_keys) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        union_size = len(submitted_keys | gt_keys)
        similarity_score = true_positives / union_size if union_size > 0 else 0.0

        return {
            'true_positives': true_positives,
            'false_positives': false_positives,
            'false_negatives': false_negatives,
            'total_submitted': len(submitted_clean),
            'total_ground_truth': len(gt_clean),
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'similarity_score': similarity_score
        }

    except Exception:
        return None


def evaluate_windows_registry(payload: dict) -> dict:
    """
    Shared evaluator: API + CSV/CI.

    payload expects:
      - base_test_case (str)
      - tool_used (str)
      - job_id (optional)
      - submitted_csv_bytes (bytes) OR submitted_csv_path (str)
      - upload_dir (optional Path/str)
      - write_db (optional bool, default True)
    """
    base_test_case = payload.get("base_test_case")
    tool_used = payload.get("tool_used")
    job_id = str(payload.get("job_id", "0"))

    if not base_test_case or not tool_used:
        raise ValueError("Missing required parameters: base_test_case, tool_used")

    write_db = bool(payload.get("write_db", True))

    upload_dir = Path(payload.get("upload_dir") or os.getenv("TEMP_FILE_UPLOAD_PATH", "/tmp"))
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Config: registry source path
    # registry_source_config = get_configs('windows_registry_source_path')
    main_path = os.getenv("MAIN_PATH", "/")
    registry_source_config = main_path + '/Data/windows_registry'
    if not registry_source_config:
        raise ValueError("Registry source path not configured")
    registry_source_path = registry_source_config[2]  # value column

    # GT: exactly one GT CSV expected
    ground_truth_paths = get_ground_truth_paths(base_test_case)
   
    if not ground_truth_paths:
        raise ValueError(f"Invalid Test Case: {base_test_case}")
    if len(ground_truth_paths) != 1:
        raise ValueError("Exactly one ground truth file expected per test case")

    gt_file_name = ground_truth_paths[0][6]  # file_name column
    
    gt_file_path = Path(registry_source_config) / gt_file_name
    print(gt_file_path)
    if not gt_file_path.exists():
        raise ValueError(f"Ground truth file not found: {gt_file_name}")

    test_case = f"{base_test_case}_{tool_used}"

    # Save submitted CSV (from bytes or path)
    submitted_csv_path = None
    cleanup_after = False

    if payload.get("submitted_csv_path"):
        submitted_csv_path = Path(payload["submitted_csv_path"])
        if not submitted_csv_path.exists():
            raise ValueError(f"Submitted CSV not found: {submitted_csv_path}")
    else:
        submitted_bytes = payload.get("submitted_csv_bytes")
        submitted_filename = payload.get("submitted_filename") or f"{test_case}.csv"
        if not submitted_bytes:
            raise ValueError("No CSV content provided")
        if not str(submitted_filename).lower().endswith(".csv"):
            raise ValueError("Only CSV files are allowed")

        submitted_csv_path = upload_dir / os.path.basename(str(submitted_filename))
        with open(submitted_csv_path, "wb") as f:
            f.write(submitted_bytes)
        cleanup_after = True

    # Basic CSV validation: must contain PATH header
    try:
        with open(submitted_csv_path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if not first_line or "PATH" not in first_line:
                raise ValueError("Invalid CSV format. Expected headers including PATH column")
    except Exception as e:
        raise ValueError(f"Cannot read CSV file: {e}")

    # Compare
    comparison_result = compare_csv_files_detailed(submitted_csv_path, gt_file_path)
    if not comparison_result:
        raise ValueError("CSV comparison failed - see server logs for details")

    tp = comparison_result["true_positives"]
    fp = comparison_result["false_positives"]
    fn = comparison_result["false_negatives"]
    precision = comparison_result["precision"]
    recall = comparison_result["recall"]
    f1_score = comparison_result["f1_score"]

    details = [{
        "submitted_file": submitted_csv_path.name,
        "file_type": "csv",
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "total_submitted_entries": comparison_result["total_submitted"],
        "total_ground_truth_entries": comparison_result["total_ground_truth"],
        "similarity_score": comparison_result["similarity_score"],
        "matched_gt_file": gt_file_name
    }]

    # Insert DB (same behaviour as api_v2.py: do not fail request if insert fails)
    if write_db:
        try:
            insert_result_to_db(base_test_case, test_case, job_id, tp, fp, fn, precision, recall, f1_score)
        except Exception:
            pass

    # Cleanup temp
    if cleanup_after:
        try:
            os.remove(submitted_csv_path)
        except Exception:
            pass

    return {
        "status": "success",
        "base_test_case": base_test_case,
        "tool_used": tool_used,
        "job_id": job_id,
        "api_version": "v1_modular",
        "input_format": "csv",
        "comparison_method": "path_value_only",
        "total_ground_truth_files": 1,
        "total_submitted_files": 1,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
        "evaluation_level": "registry_entry_level",
        "details": details
    }
