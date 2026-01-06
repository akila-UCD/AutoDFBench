# autodfbench/eval/file_carving.py
from __future__ import annotations

import os
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image

# Import your support module
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../support")))
from ImageCheck import ImageCheck  # noqa

# DB helpers (use your existing db.py if you have it; else keep local)
from autodfbench.db import get_db_connection, insert_result_to_db


def _safe_div(a, b):
    return a / b if b else 0.0


def _int(v, default):
    try:
        return int(v)
    except Exception:
        return default


def _float(v, default):
    try:
        return float(v)
    except Exception:
        return default


def _decode_check(path: Path):
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            im.load()
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _quality_label_bytes(decodes: bool, byte_similarity: float | None,
                         q_major_pct: float, q_complete_pct: float) -> str:
    if not decodes:
        return "Failed to display"
    if byte_similarity is None:
        return "Incomplete – major flaws"
    if byte_similarity < q_major_pct:
        return "Incomplete – major flaws"
    if q_major_pct <= byte_similarity < q_complete_pct:
        return "Usable – minor flaws"
    return "Complete no flaws"


def get_ground_truth_paths_file_carving(base_test_case: str) -> List[Tuple]:
    """
    Pull GT rows for file_carving.
    Your original code used SELECT * and then row[6] for filename.
    Keep the same behaviour to avoid breaking your DB schema.
    """
    conn = get_db_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT *
            FROM ground_truth
            WHERE base_test_case=%s AND cftt_task='file_carving'
            """,
            (base_test_case,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []


def evaluate_file_carving(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Shared evaluator for:
      - API (multipart upload)
      - CSV (paths)
    In CSV mode, provide 'carved_files' as list of file paths.
    """
    base_test_case = str(payload.get("base_test_case", "")).strip()
    tool_used = str(payload.get("tool_used", "")).strip()
    if not base_test_case:
        raise ValueError("Missing 'base_test_case'")
    if not tool_used:
        raise ValueError("Missing 'tool_used'")

    test_case = f"{base_test_case}_{tool_used}"

    # Params
    source_dir = Path(payload.get("source_dir") or os.getenv("CARVING_SOURCE_DIR", "Data/source"))
    block_size = _int(payload.get("block_size"), 512)
    stride = _int(payload.get("stride"), block_size)
    include_partial = bool(payload.get("include_partial", True))
    ignore_zero = bool(payload.get("ignore_zero", True))
    byte_sim_threshold = _float(payload.get("byte_similarity_threshold"), 0.2)

    # pHash selection
    gt_select_strategy = str(payload.get("gt_select_strategy") or os.getenv("GT_SELECT_STRATEGY", "phash_first")).lower()
    phash_top_k = _int(payload.get("phash_top_k"), _int(os.getenv("PHASH_TOP_K", "3"), 3))
    phash_hash_size = _int(payload.get("phash_hash_size"), _int(os.getenv("PHASH_HASH_SIZE", "8"), 8))
    phash_highfreq = _int(payload.get("phash_highfreq"), _int(os.getenv("PHASH_HIGHFREQ", "4"), 4))

    # quality thresholds (pct represented as fractions in your current code)
    q_complete_pct = _float(payload.get("q_complete_pct"), _float(os.getenv("Q_SIM_COMPLETE_PCT", "0.5"), 0.5))
    q_major_pct = _float(payload.get("q_major_pct"), _float(os.getenv("Q_SIM_MAJOR_PCT", "0.1"), 0.1))

    write_db = bool(payload.get("write_db", False))

    carved_files = payload.get("carved_files")
    if not isinstance(carved_files, list) or not carved_files:
        raise ValueError("Missing 'carved_files' (list of file paths)")

    # Ground truth
    gt_rows = get_ground_truth_paths_file_carving(base_test_case) or []
    if not gt_rows:
        raise ValueError("Invalid test case or no GT for cftt_task='file_carving'")

    gt_filenames = []
    for row in gt_rows:
        try:
            gt_filenames.append(str(row[6]))
        except Exception:
            gt_filenames.append(str(row[-1]))

    details = []
    tp = fp = 0

    for sub_path_str in carved_files:
        sub_path = Path(str(sub_path_str))
        sub_name = sub_path.name
        if not sub_path.exists():
            fp += 1
            details.append({
                "submitted_file": sub_name,
                "error": f"file not found: {sub_path}",
            })
            continue

        # pHash for submission
        sub_phash = ImageCheck.phash_hex(str(sub_path), hash_size=phash_hash_size, highfreq_factor=phash_highfreq)

        phash_table = []
        for gt_name in gt_filenames:
            gt_path = source_dir / gt_name
            if not gt_path.exists():
                continue
            gt_hash = ImageCheck.phash_hex(str(gt_path), hash_size=phash_hash_size, highfreq_factor=phash_highfreq)
            dist = ImageCheck.phash_hamming(sub_phash, gt_hash) if sub_phash and gt_hash else None
            phash_table.append((gt_name, gt_hash, dist))

        phash_candidates = [t for t in phash_table if t[2] is not None]
        phash_candidates.sort(key=lambda x: x[2])

        def _report_for(gt_name: str):
            gt_path = source_dir / gt_name
            return ImageCheck.block_hash_compare(
                orig_path=str(gt_path),
                carved_path=str(sub_path),
                block_size=block_size,
                stride=stride,
                include_partial=include_partial,
                ignore_zero=ignore_zero,
            )

        best_gt_name = None
        phash_distance = None
        selected_by = None
        compare_report = None

        if gt_select_strategy == "phash_first" and phash_candidates:
            best_gt_name, _, phash_distance = phash_candidates[0]
            selected_by = "phash"
            compare_report = _report_for(best_gt_name)
        elif gt_select_strategy == "hybrid" and phash_candidates:
            topk = phash_candidates[:max(1, phash_top_k)]
            selected_by = "phash_hybrid"
            best_score = -1.0
            for gt_name, _, dist in topk:
                rep = _report_for(gt_name)
                seq_aligned = rep.get("sequential_bytes", {}).get("aligned", {})
                byte_sim = seq_aligned.get("byte_similarity")
                if isinstance(byte_sim, (int, float)):
                    score = float(byte_sim)
                else:
                    idx = rep["indexing"]; m = rep["matching"]
                    score = _safe_div(m.get("matched_orig_blocks", 0), idx.get("original_blocks", 0))
                if score > best_score:
                    best_score = score
                    compare_report = rep
                    best_gt_name = gt_name
                    phash_distance = dist
        else:
            selected_by = "blocks"
            best_recall_blocks = -1.0
            for gt_name in gt_filenames:
                rep = _report_for(gt_name)
                idx = rep["indexing"]; m = rep["matching"]
                recall_blocks = _safe_div(m.get("matched_orig_blocks", 0), idx.get("original_blocks", 0))
                if recall_blocks > best_recall_blocks:
                    best_recall_blocks = recall_blocks
                    compare_report = rep
                    best_gt_name = gt_name

        decodes, decode_error = _decode_check(sub_path)

        byte_similarity_lock = None
        byte_similarity_algn = None
        if compare_report and "sequential_bytes" in compare_report:
            seq = compare_report["sequential_bytes"] or {}
            bs_lock = seq.get("byte_similarity")
            if isinstance(bs_lock, (int, float)):
                byte_similarity_lock = float(bs_lock)
            bs_algn = (seq.get("aligned") or {}).get("byte_similarity")
            if isinstance(bs_algn, (int, float)):
                byte_similarity_algn = float(bs_algn)

        quality_sim = byte_similarity_algn if byte_similarity_algn is not None else byte_similarity_lock
        quality = _quality_label_bytes(decodes, quality_sim, q_major_pct, q_complete_pct)

        # TP logic: decodes + lockstep similarity > threshold
        if decodes and (byte_similarity_lock is not None) and (byte_similarity_lock > byte_sim_threshold):
            tp += 1
        else:
            fp += 1

        metrics = None
        if compare_report:
            m = compare_report["matching"]
            seq = compare_report.get("sequential_bytes", {}) or {}
            seq_al = seq.get("aligned") or {}
            idx = compare_report["indexing"]
            recall_blocks = _safe_div(m.get("matched_orig_blocks", 0), idx.get("original_blocks", 0))
            metrics = {
                "block_match_rate": m.get("block_match_rate"),
                "recall_blocks": round(recall_blocks, 6),
                "byte_similarity": (None if byte_similarity_lock is None else round(byte_similarity_lock, 6)),
                "byte_similarity_aligned": (None if byte_similarity_algn is None else round(byte_similarity_algn, 6)),
                "bytes_compared": seq.get("total_bytes_compared"),
                "diff_byte_count": seq.get("diff_byte_count"),
                "aligned_bytes_compared": seq_al.get("total_bytes_compared"),
                "aligned_diff_byte_count": seq_al.get("diff_byte_count"),
            }

        details.append({
            "submitted_file": sub_name,
            "matched_gt_file": best_gt_name,
            "selected_by": selected_by,
            "byte_similarity_threshold": byte_sim_threshold,
            "quality_by": "aligned" if byte_similarity_algn is not None else "lockstep",
            "quality_thresholds_pct": {"minor": q_major_pct, "complete": q_complete_pct},
            "metrics": metrics,
            "file_scores": {
                "error_check": {
                    "decodes": decodes, 
                    "decode_error": decode_error},
                "quality_label": quality
            },
            "phash": {
                "hash_size": phash_hash_size,
                "highfreq": phash_highfreq,
                "hamming_distance": phash_distance,
            },
        })

    fn = max(len(gt_filenames) - tp, 0)
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)

    if write_db:
        insert_result_to_db(base_test_case, test_case, tp, fp, fn, precision, recall, f1)

    return {
        "base_test_case": base_test_case,
        "test_case": test_case,
        "tool_used": tool_used,
        "counts": {
            "total_ground_truth_files": len(gt_filenames),
            "total_submitted_files": len(carved_files),
            "tp": tp, "fp": fp, "fn": fn,
        },
        "scores": {
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        },
        "details": details,
        "params": {
            "source_dir": str(source_dir),
            "block_size": block_size,
            "stride": stride,
            "include_partial": include_partial,
            "ignore_zero": ignore_zero,
            "byte_similarity_threshold": byte_sim_threshold,
            "gt_select_strategy": gt_select_strategy,
            "phash": {"hash_size": phash_hash_size, "highfreq": phash_highfreq, "top_k": phash_top_k},
            "quality_thresholds_pct": {"minor": q_major_pct, "complete": q_complete_pct},
        }
    }
