# AutoDFBench Windows Registry Recovery Evaluation API

## Endpoint
`POST /api/v1/windows-registry/evaluate` (port 8003)

### Test data
The test cases use the NIST CFReDS 2017 Windows registry hive files:

| Group | Test cases | What it covers |
|---|---|---|
| Normal registry | `NR-01` … `NR-07` | data types, tree structures, deep trees, big data, non-ASCII names |
| Deleted / changed data | `NRD-01` … `NRD-16` | deleted keys and values, changed names and data |
| Manipulated registry | `MR-01` … `MR-15` | hidden keys, values, names and data, flag tricks |
| Corrupted registry | `CR-01` … `CR-07` | partial hives: single hive bins, last half, fragments |

Each test case has one ground-truth CSV in `Data/windows_registry/`, named after the hive (e.g. `[nr]-02-1_v15.hive.csv`).
The `file_name` column of the `ground_truth` table (`cftt_task='windows_registry'`) links a test case to its CSV.

### Ground-truth sets
| Set | Folder | Contents |
|---|---|---|
| `1.0` (default) | `Data/windows_registry/` | The ground truth used for the AutoDFBench 1.0 paper. |
| `1.1` | `Data/windows_registry_v1.1/` | Replaces three CSVs; every other test case uses its `1.0` file. |

Set `1.1` corrects two ground-truth files whose walk did not end where the hive does:

| Test case | CSV | `1.0` | `1.1` |
|---|---|---|---|
| `MR-08` (key loop) | `[mr]-08_v15.hive.csv` (and `_v13`) | 199,259 keys: the walk kept following the subkey reference that points back up the tree | 534 keys: each key listed once |
| `NR-03-3` (deep tree) | `[nr]-03-3_v13.hive.csv` | 988 keys, down to depth 987, where the walk stopped | 513 keys: the root and 512 levels below it, the documented Windows limit for registry tree depth |

Choose the set with the `gt_set` field. Results scored against set `1.0` stay comparable with the paper.

The `1.1` files are built from the NIST hives with `tools/build_registry_gt.py`, which uses Regipy and writes the same CSV format as set `1.0`:
```bash
pip install regipy
python tools/build_registry_gt.py --hives /path/to/win_REG
```
For hives without a loop or a tree deeper than 512 levels, the tool's output is identical to the `1.0` files.

### Parameters (multipart/form-data)
| Field | Type | Description |
|---|---|---|
| base_test_case | string | Test case name (e.g. `NR-02-1`) |
| tool_used | string | Name of the tool that produced the CSV |
| job_id | string | Optional run identifier (default `0`) |
| write_db | bool | Store the result in the results database (default `true`) |
| gt_set | string | Ground-truth set: `1.0` (default, as in the paper) or `1.1` (see above) |
| files | file | Exactly one `.csv` file with the tool's output |

### Submitted CSV format
- A header row with at least the columns **`PATH`** and **`VALUE`**. Other columns, such as `TYPE` and `MTIME`, are allowed but not scored.
- One row per registry entry.
- `PATH` is written as in the ground truth: `/` for the root key and `/` between key names (e.g. `/0x02_TYPE1_TREE/Node_1`). Key names are compared exactly as written, including case.
- Rows whose `PATH` contains `FILE_INFO` or `PROCESSING_SUMMARY` are treated as metadata and ignored.

Example:
```csv
PATH,TYPE,VALUE,MTIME
/,KEY,,2017-09-25 14:21:12.516610+00:00
/0x02_TYPE1_TREE,KEY,,2017-09-25 14:21:12.532210+00:00
/0x02_TYPE1_TREE/Node_1,KEY,,2017-09-25 14:21:12.532210+00:00
```

### Scoring
As described in the AutoDFBench 1.0 paper (section 4.6.4):
- Each row of both CSVs becomes the string `PATH|VALUE`, with surrounding spaces removed. Duplicate rows count once.
- **TP:** a row in both the submitted CSV and the ground truth.
- **FP:** a row only in the submitted CSV.
- **FN:** a row only in the ground truth.
- Precision = TP / submitted rows, Recall = TP / ground-truth rows, and F1 is their harmonic mean.

A test case whose ground truth has no entries cannot be scored, and the API returns an error for it.

### Sample `curl` command
```bash
curl -X POST http://localhost:8003/api/v1/windows-registry/evaluate \
  -F "base_test_case=NR-02-1" \
  -F "tool_used=regipy_4.0" \
  -F "write_db=false" \
  -F "files=@./nr-02-1_output.csv"
```

### Response sample
```json
{
  "status": "success",
  "base_test_case": "NR-02-1",
  "tool_used": "regipy_4.0",
  "comparison_method": "path_value_only",
  "gt_set": "1.0",
  "true_positives": 16,
  "false_positives": 0,
  "false_negatives": 0,
  "precision": 1.0,
  "recall": 1.0,
  "f1_score": 1.0,
  "details": [{"submitted_file": "nr-02-1_output.csv", "total_submitted_entries": 16,
               "total_ground_truth_entries": 16, "similarity_score": 1.0,
               "matched_gt_file": "[nr]-02-1_v15.hive.csv", "gt_set": "1.0"}]
}
```

### Known ground-truth limitations
- **Keys only:** the current ground-truth CSVs list registry keys only (`VALUE` is empty), so value rows in a submission count as FPs.
- **Not scorable:** `CR-01`, `CR-05`, `CR-06` and `CR-07` have no entries (their hives could not be parsed when the ground truth was built).
- **`ugrd-nr`** has three ground-truth files and therefore returns an error.
- **Results database:** results scored against a set other than `1.0` are stored with `_gt<set>` added to the test case name (e.g. `MR-08_mytool_gt1.1`).
