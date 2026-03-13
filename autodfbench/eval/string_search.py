# autodfbench/eval/string_search.py

import re
from autodfbench.db import get_ss_gt_map, insert_result_to_db
from autodfbench.eval.metrics import compute_metrics
from pathlib import Path
import os


def evaluate_string_search(payload: dict) -> dict:
    write_db = payload.get("write_db", True)
    base_test_case = str(payload.get("base_test_case", "")).strip()
    tool_used = str(payload.get("tool_used", "")).strip()
    found_list = payload.get("file_contents_found", [])
    os_type = str(payload.get("os", "")).strip()

    if not base_test_case:
        raise ValueError("Missing 'base_test_case'")
    if not tool_used:
        raise ValueError("Missing 'tool_used'")
    if not isinstance(found_list, list):
        raise ValueError("'file_contents_found' must be an array")
    if not os_type:
        raise ValueError("Missing 'os'")

    # Extract 4-digit line numbers
    line_re = re.compile(r"\b(\d{4})\b")
    submitted = set()
    for s in found_list:
        if isinstance(s, str):
            m = line_re.search(s)
            if m:
                submitted.add(m.group(1))

    
    gt_lines, line_to_type = get_ss_gt_map(base_test_case, os_type)
    if not gt_lines:
        raise ValueError("Invalid test case or no GT rows for cftt_task='string_search'")

    matched = submitted & gt_lines
    fp_set = submitted - gt_lines
    fn_set = gt_lines - submitted

    tp, fp, fn = len(matched), len(fp_set), len(fn_set)
    precision, recall, f1 = compute_metrics(tp, fp, fn)

    # optional: write to DB (you can disable in CLI via a flag later)
    test_case = f"{base_test_case}_{tool_used}"
    if write_db:
        insert_result_to_db(base_test_case, test_case, tp, fp, fn, precision, recall, f1)

    # Per-type (TP only) – keep if you want it in report
    type_counts = {"active": 0, "deleted": 0, "unallocated": 0}
    for ln in matched:
        t = (line_to_type.get(ln, "") or "").lower()
        if t in ("unalloc", "unalocated", "un-allocated"):
            t = "unallocated"
        if t in type_counts:
            type_counts[t] += 1

    return {
        "base_test_case": base_test_case,
        "tool_used": tool_used,
        "total_gt_lines": len(gt_lines),
        "total_submitted_lines": len(submitted),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "hit_counts_by_type": type_counts,
    }
