# autodfbench/eval/sqlite_recovery.py
import sys
from pathlib import Path
import json

from autodfbench.db_sqlite_recovery import get_ground_truth

# Keep your existing evaluation functions and logic
from modules.sqlite_sft01 import parse_sqlite_header
from modules.sqlite_sft02 import content_of_sqlite_compair
from modules.sqlite_sft03 import content_recovery
from modules.sqlite_sft05 import table_statements

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .../AutoDFBench
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def evaluate_sqlite_recovery(payload: dict) -> dict:
    """
    Shared evaluator for API + CSV/CI (later).

    Required payload fields (same as current API):
      - task_id
      - base_test_case
      - file_name
      - extracted_data
    Optional:
      - sqlite_table_name (used by SFT02)
    """
    task_id = payload.get("task_id")
    base_test_case = payload.get("base_test_case")
    file_name = payload.get("file_name")
    sqlite_table_name = payload.get("sqlite_table_name")
    extracted_data = payload.get("extracted_data")

    if not task_id or not base_test_case or not file_name or extracted_data is None:
        raise ValueError("Missing required fields")

    # --- Dispatch (same logic as your API) ---
    if task_id == "SFT01":
        ground_truth = get_ground_truth(base_test_case, file_name)
        result = parse_sqlite_header(extracted_data, ground_truth)

    elif task_id == "SFT02":
        ground_truth = get_ground_truth(
            base_test_case,
            file_name,
            sqlite_table_name=sqlite_table_name
        )
        result = content_of_sqlite_compair(extracted_data, ground_truth)

    elif task_id == "SFT03":
        ground_truth = get_ground_truth(
            base_test_case,
            file_name,
            like_base=True,
            fetch_many=True
        )
        result = content_recovery(extracted_data, ground_truth)

    elif task_id == "SFT05":
        ground_truth = get_ground_truth(
            base_test_case,
            file_name,
            like_base=True,
            select_columns="base_test_case,file_name,sqlite_cmd"
        )
        result = table_statements(extracted_data, ground_truth)

    else:
        raise ValueError("Invalid task_id")

    if not ground_truth:
        # keep the same semantics as your API: 404 in API layer
        raise LookupError("Ground truth not found")

    return {
        "task_id": task_id,
        "base_test_case": base_test_case,
        "file_name": file_name,
        "evaluation": result
    }
