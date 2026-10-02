def _norm(val):
    """Normalise a row id so 253, "253" and 253.0 compare equal."""
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    try:
        f = float(s)
        return str(int(f)) if f.is_integer() else str(f)
    except ValueError:
        return s.lower()


def content_recovery(input_data, ground_truth_rows):
    """
    Compare recovered SQLite row ids (input_data["file_line"]) against the
    ground truth rows for the same file.

    Matching is set based: order does not matter, each ground-truth row can be
    matched once, and duplicate predictions count as false positives.
      TP = predicted ids found in the ground truth
      FP = predicted ids not in the ground truth (or repeated)
      FN = ground-truth ids that were not predicted
    """
    expected_file_lines = [row.get("file_line") for row in ground_truth_rows]
    expected = {_norm(v) for v in expected_file_lines} - {None}

    matched = set()
    detailed_matches = []
    tp = fp = 0

    for idx, predicted_val in enumerate(input_data["file_line"]):
        key = _norm(predicted_val)
        match = key is not None and key in expected and key not in matched
        if match:
            matched.add(key)
            tp += 1
        else:
            fp += 1

        detailed_matches.append({
            "index": idx,
            "predicted": predicted_val,
            "match": match
        })

    fn = len(expected - matched)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "Precision": precision,
        "Recall": recall,
        "F1-Score": f1,
        "input_data": input_data,
        "expected_file_lines": expected_file_lines,
        "missed_file_lines": sorted(expected - matched, key=lambda x: (len(x), x)),
        "detailed_matches": detailed_matches
    }
