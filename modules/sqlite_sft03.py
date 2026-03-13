

def content_recovery(input_data, ground_truth_rows):
    """
    Compare extracted SQLite attributes (input_data) against ground_truth rows.
    ground_truth_rows is a list of dicts from DB (each row).
    input_data is a list of values (like [253, 1285, 1154,...]).
    """

    tp = fp = fn = 0
    detailed_matches = []

    # --- Extract all file_line values from DB rows ---
    # Assuming ground_truth_rows is a list of dicts with a column "file_line"
    expected_file_lines = [row.get("file_line") for row in ground_truth_rows]

    # --- Compare input_data list to file_line values ---
    for idx, predicted_val in enumerate(input_data["file_line"]):
        if idx < len(expected_file_lines):
            expected_val = expected_file_lines[idx]
        else:
            expected_val = None  # no corresponding DB row

        match = False
        if expected_val is None or str(expected_val).strip() == "":
            tp += 1
            match = True
        else:
            # numeric comparison
            try:
                match = float(predicted_val) == float(expected_val)
            except (ValueError, TypeError):
                # string comparison ignoring case
                match = str(expected_val).lower() in str(predicted_val).lower()

        if match:
            tp += 1
        else:
            fp += 1

        detailed_matches.append({
            "index": idx,
            "predicted": predicted_val,
            "expected": expected_val,
            "match": match
        })

    # FN = total predictions minus TP
    fn = len(input_data["file_line"]) - tp

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "Precision": precision,
        "Recall": recall,
        "F1-Score": f1,
        "input_data": input_data,
        "expected_file_lines": expected_file_lines,
        "detailed_matches": detailed_matches
    }
