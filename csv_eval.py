#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

from autodfbench.eval.string_search import evaluate_string_search
from autodfbench.eval.deleted_file_recovery import evaluate_deleted_file_recovery
from autodfbench.eval.file_carving import evaluate_file_carving


def parse_bool(v, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def main():
    ap = argparse.ArgumentParser(
        description="AutoDFBench CSV evaluator (supports: string_search, deleted_file_recovery, file_carving)"
    )
    ap.add_argument("test_suite", help="string_search | deleted_file_recovery (or dfr) | file_carving")
    ap.add_argument("test_case_name", help="label for this batch run (e.g., SS-BATCH-01)")
    ap.add_argument("input_csv", help="CSV containing tool outputs")
    ap.add_argument("output_csv", help="CSV report to write")
    ap.add_argument("--include-summary", action="store_true", help="Append suite score summary row")
    args = ap.parse_args()

    suite = args.test_suite.strip().lower()
    if suite == "dfr":
        suite = "deleted_file_recovery"

    if suite not in ("string_search", "deleted_file_recovery", "file_carving"):
        raise ValueError("Unsupported test_suite. Use: string_search | deleted_file_recovery (or dfr) | file_carving")

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows_out = []
    suite_scores = []  # F1 per row for summary average

    with input_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no header row")

        for i, r in enumerate(reader, start=1):

            # -----------------------------
            # STRING SEARCH
            # -----------------------------
            if suite == "string_search":
                payload = {
                    "test_case_name": args.test_case_name,
                    "base_test_case": (r.get("base_test_case") or "").strip(),
                    "tool_used": (r.get("tool_used") or "").strip(),
                    "os": (r.get("os") or "").strip(),
                    "write_db": parse_bool(r.get("write_db"), default=False),
                }

                if not payload["base_test_case"]:
                    raise ValueError(f"Row {i}: missing base_test_case")
                if not payload["tool_used"]:
                    raise ValueError(f"Row {i}: missing tool_used")
                if not payload["os"]:
                    raise ValueError(f"Row {i}: missing os")

                fcf = r.get("file_contents_found", "[]")
                try:
                    payload["file_contents_found"] = json.loads(fcf)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Row {i}: invalid JSON in file_contents_found: {e}")

                result = evaluate_string_search(payload)

                f1 = float(result.get("f1_score", 0.0) or 0.0)
                suite_scores.append(f1)

                hit_counts = result.get("hit_counts_by_type") or {}
                rows_out.append({
                    "test_suite": "string_search",
                    "batch_run": args.test_case_name,
                    "test_case_name": result.get("base_test_case", payload["base_test_case"]),
                    "tool_used": result.get("tool_used", payload["tool_used"]),
                    "os": payload["os"],
                    "total_gt_lines": result.get("total_gt_lines", ""),
                    "total_submitted_lines": result.get("total_submitted_lines", ""),
                    "TP": result.get("true_positives", ""),
                    "FP": result.get("false_positives", ""),
                    "FN": result.get("false_negatives", ""),
                    "precision": result.get("precision", ""),
                    "recall": result.get("recall", ""),
                    "F1": result.get("f1_score", ""),
                    "active_hits": hit_counts.get("active", ""),
                    "deleted_hits": hit_counts.get("deleted", ""),
                    "unallocated_hits": hit_counts.get("unallocated", ""),
                    "is_summary": False,
                    "AutoDFBench_suite_score": "",
                })

            # -----------------------------
            # DELETED FILE RECOVERY
            # -----------------------------
            elif suite == "deleted_file_recovery":
                payload = {
                    "base_test_case": (r.get("base_test_case") or "").strip(),
                    "tool_used": (r.get("tool_used") or "").strip(),
                    "file_system": (r.get("file_system") or "").strip(),
                    "test_set": (r.get("test_set") or "").strip(),
                    "sector_size": int((r.get("sector_size") or "512").strip() or "512"),
                    "check_meta": parse_bool(r.get("check_meta"), default=False),
                    "write_db": parse_bool(r.get("write_db"), default=False),
                    "write_reports": False,  # IMPORTANT for CSV batch
                }

                if not payload["base_test_case"]:
                    raise ValueError(f"Row {i}: missing base_test_case")
                if not payload["tool_used"]:
                    raise ValueError(f"Row {i}: missing tool_used")
                if not payload["test_set"]:
                    raise ValueError(f"Row {i}: missing test_set")

                files_json = r.get("files_json", "[]")
                try:
                    payload["files"] = json.loads(files_json)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Row {i}: invalid JSON in files_json: {e}")

                result = evaluate_deleted_file_recovery(payload)

                f1 = float(result.get("F1", 0.0) or 0.0)
                suite_scores.append(f1)

                rows_out.append({
                    "test_suite": "deleted_file_recovery",
                    "batch_run": args.test_case_name,
                    "test_case_name": result.get("base_test_case", payload["base_test_case"]),
                    "tool_used": result.get("tool_used", payload["tool_used"]),
                    "file_system": payload.get("file_system", ""),
                    "test_set_used": result.get("test_set_used", ""),
                    "total_ground_truth_files": result.get("total_ground_truth_files", ""),
                    "total_submitted_files": result.get("total_submitted_files", ""),
                    "TP": result.get("true_positives", ""),
                    "FP": result.get("false_positives", ""),
                    "FN": result.get("false_negatives", ""),
                    "precision": result.get("precision", ""),
                    "recall": result.get("recall", ""),
                    "F1": result.get("F1", ""),
                    "AutoDFBench_score": result.get("AutoDFBench_score", ""),
                    "SS": result.get("SS", ""),
                    "First": result.get("First", ""),
                    "Full": result.get("Full", ""),
                    "Match": result.get("Match", ""),
                    "Over": result.get("Over", ""),
                    "Multi": result.get("Multi", ""),
                    "Size_match": result.get("Size_match", ""),
                    "is_summary": False,
                    "AutoDFBench_suite_score": "",
                })

            # -----------------------------
            # FILE CARVING (MINIMAL INPUT)
            # CSV columns required:
            #   base_test_case, tool_used, files_json  (JSON array of file paths)
            # -----------------------------
            elif suite == "file_carving":
                base_test_case = (r.get("base_test_case") or "").strip()
                tool_used = (r.get("tool_used") or "").strip()

                if not base_test_case:
                    raise ValueError(f"Row {i}: missing base_test_case")
                if not tool_used:
                    raise ValueError(f"Row {i}: missing tool_used")

                files_json = r.get("files_json", "[]")
                try:
                    file_paths = json.loads(files_json)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Row {i}: invalid JSON in files_json: {e}")

                if not isinstance(file_paths, list) or not file_paths:
                    raise ValueError(f"Row {i}: files_json must be a non-empty JSON array of file paths")

                payload = {
                    "base_test_case": base_test_case,
                    "tool_used": tool_used,
                    # evaluator expects this key name (as in the refactor plan)
                    "carved_files": file_paths,
                    "write_db": parse_bool(r.get("write_db"), default=False),
                }

                result = evaluate_file_carving(payload)

                f1 = float(result.get("scores", {}).get("f1", 0.0) or 0.0)
                suite_scores.append(f1)

                counts = result.get("counts", {}) or {}
                scores = result.get("scores", {}) or {}

                rows_out.append({
                    "test_suite": "file_carving",
                    "batch_run": args.test_case_name,
                    "test_case_name": result.get("base_test_case", base_test_case),
                    "tool_used": result.get("tool_used", tool_used),
                    "total_ground_truth_files": counts.get("total_ground_truth_files", ""),
                    "total_submitted_files": counts.get("total_submitted_files", ""),
                    "TP": counts.get("tp", ""),
                    "FP": counts.get("fp", ""),
                    "FN": counts.get("fn", ""),
                    "precision": scores.get("precision", ""),
                    "recall": scores.get("recall", ""),
                    "F1": scores.get("f1", ""),
                    "is_summary": False,
                    "AutoDFBench_suite_score": "",
                })

    # ---------- Summary row ----------
    if args.include_summary:
        suite_avg = round(sum(suite_scores) / len(suite_scores), 6) if suite_scores else 0.0

        if rows_out:
            summary_row = {k: "" for k in rows_out[0].keys()}
            summary_row["test_suite"] = suite
            summary_row["batch_run"] = args.test_case_name
            summary_row["test_case_name"] = "AUTO_DF_BENCH_SUITE_SCORE"
            summary_row["tool_used"] = rows_out[0].get("tool_used", "")
            summary_row["is_summary"] = True
            summary_row["AutoDFBench_suite_score"] = suite_avg
            rows_out.append(summary_row)

        print(f"[OK] AutoDFBench suite score (avg F1) = {suite_avg}")

    # ---------- Write output ----------
    if not rows_out:
        raise ValueError("No rows produced. Check your input CSV.")

    fieldnames = list(rows_out[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"[OK] Wrote {len(rows_out)} rows -> {output_path}")


if __name__ == "__main__":
    main()
