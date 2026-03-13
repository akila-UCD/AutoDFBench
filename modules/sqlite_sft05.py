

def table_statements(input_data, ground_truth):
    """
        Compare extracted SQLite attributes (input_data) against ground_truth.
        Returns Precision, Recall, F1-Score, and per-key comparison info.
        """

    def is_number(val):
        """Check if value is an int or float"""
        try:
            float(val)
            return True
        except (ValueError, TypeError):
            return False

    tp = fp = fn = 0
    detailed_matches = {}

    # Only iterate over keys present in input_data
    for key, predicted in input_data.items():
        expected = ground_truth.get(key)

        # Skip comparison if expected is None or empty → counts as match
        if expected is None or str(expected).strip() == "":
            tp += 1
            detailed_matches[key] = {
                "predicted": predicted,
                "expected": expected,
                "match": True
            }
            continue

        match = False
        # Numeric comparison
        if is_number(predicted) and is_number(expected):
            match = float(predicted) == float(expected)
        else:
            # Case-insensitive substring match for strings
            match = str(expected).lower() in str(predicted).lower()

        if match:
            tp += 1
        else:
            fp += 1

        detailed_matches[key] = {
            "predicted": predicted,
            "expected": expected,
            "match": match
        }

    # FN = number of extracted keys minus TP
    fn = len(input_data) - tp

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "Precision": precision,
        "Recall": recall,
        "F1-Score": f1,
        "input_data": input_data,
        "ground_truth": ground_truth,
        "detailed_matches": detailed_matches
    }
