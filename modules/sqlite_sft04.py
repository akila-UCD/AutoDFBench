import os


def _name(val):
    """Compare file names only: no folder, case-insensitive ("C:\\x\\A.sqlite-journal" == "a.sqlite-journal")."""
    return os.path.basename(str(val).strip().replace("\\", "/")).casefold()


def source_file_check(input_data, ground_truth):
    """
    SFT-04: compare the source file the tool reports for the recovered data elements against the
    ground-truth source file (ground_truth["gt_file"]).

    input_data["source_file"] is one file name or a list of file names.
      TP = a reported name that matches the ground-truth source file
      FP = a reported name that does not match (or repeats a match)
      FN = 0, as SFT-04 checks a true / false condition on the reported name
    """
    reported = input_data.get("source_file") if isinstance(input_data, dict) else input_data
    if isinstance(reported, str):
        reported = [reported]
    reported = [r for r in (reported or []) if str(r).strip()]
    if not reported:
        raise ValueError("extracted_data.source_file must be a file name or a list of file names")

    expected = _name(ground_truth["gt_file"])
    tp = fp = 0
    matched = False
    detailed_matches = []
    for predicted in reported:
        match = _name(predicted) == expected and not matched
        if match:
            matched = True
            tp += 1
        else:
            fp += 1
        detailed_matches.append({"predicted": predicted, "match": match})
    fn = 0

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
        "expected_source_file": ground_truth["gt_file"],
        "detailed_matches": detailed_matches
    }
