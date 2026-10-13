# AutoDFBench SQLite Data Recovery Evaluation API

## Endpoint
`POST /api/v1/sqlite-recovery/evaluate` (port 8004)
**Content-Type:** `application/json`

### Test data
The test cases use the NIST CFTT SQLite Data Recovery data sets (specification v1.0): SQLite databases built from the Chinook sample data, with Android and iOS copies, and their `-journal`, `-wal` and `-shm` files.

| Task | Test cases | What the tool reports |
|---|---|---|
| `SFT01` | `SFT-01-UTF16BE-PERSIST`, `SFT-01-UTF16LE-OFF`, `SFT-01-UTF8-WAL` | Header and file details: page size, journal mode, write/read version, page count, text encoding, MD5 and SHA-1 |
| `SFT02` | `SFT-02` | Schema of a table: table name, columns, number of rows |
| `SFT03` | `SFT-03-PERSIST`, `SFT-03-WAL` | Recovered rows: deleted rows and old versions of updated rows, identified by rowid |
| `SFT04` | `SFT-04-PERSIST`, `SFT-04-WAL` | The file the recovered rows were found in (`-journal` for PERSIST, the database file for WAL) |
| `SFT05` | `SFT-05` | Table creation statements (an optional NIST feature) |

The ground truth is in `ground_truth/autodfbench_gt.sqlite` (`cftt_task='sqlite'`). A request is matched to ground-truth rows by `base_test_case` and `file_name`, and for `SFT02` also by `sqlite_table_name`.

### Request body
| Field | Type | Required | Description |
|---|---|---|---|
| `task_id` | string | yes | `SFT01`, `SFT02`, `SFT03`, `SFT04` or `SFT05` |
| `base_test_case` | string | yes | Test case name (e.g. `SFT-01-UTF8-WAL`). For `SFT03` it is matched as a prefix |
| `file_name` | string | yes | NIST file the answer is for (e.g. `sft-01_utf8_wal_android.sqlite`) |
| `sqlite_table_name` | string | `SFT02` only | Table the answer is for (e.g. `Albums`) |
| `extracted_data` | object | yes | The tool's answer; fields per task below |

### `extracted_data` per task
| Task | Fields |
|---|---|
| `SFT01` | Any of `page_size`, `journal_mode`, `sqlite_write_read_version`, `number_of_pages`, `encoding`, `sqlite_md5_hash`, `sqlite_sha1_hash` |
| `SFT02` | `sqlite_table_name`, `sqlite_column`, `sqlite_number_of_rows` |
| `SFT03` | `file_line`: list of recovered rowids |
| `SFT04` | `source_file`: file name, or a list of file names |
| `SFT05` | `sqlite_cmd`: the table creation statement |

### Scoring
- **`SFT01`, `SFT02`, `SFT05`:** each submitted field is compared with the ground-truth value of the same name. Numbers must be equal; text matches when the ground-truth value appears in the submitted value (case-insensitive). A field with no ground-truth value counts as a match. Only submitted fields are scored.
- **`SFT03`:** set comparison of rowids. **TP:** a submitted rowid in the ground truth. **FP:** a rowid not in the ground truth, or submitted twice. **FN:** a ground-truth rowid not submitted.
- **`SFT04`:** the submitted file name(s) are compared with the expected source file (file name only, without folders, case-insensitive). TP: the expected file is named; FP: any other name. FN is always 0.
- Precision, recall and F1 follow from TP, FP and FN.

### Example request
```bash
curl -X POST http://localhost:8004/api/v1/sqlite-recovery/evaluate \
  -H "Content-Type: application/json" \
  -d '{"task_id": "SFT04", "base_test_case": "SFT-04-WAL", "file_name": "sft-03-WAL_ios.sqlite",
       "extracted_data": {"source_file": "sft-03-WAL_ios.sqlite"}}'
```

### Response sample
```json
{
  "task_id": "SFT04",
  "base_test_case": "SFT-04-WAL",
  "file_name": "sft-03-WAL_ios.sqlite",
  "evaluation": {
    "TP": 1,
    "FP": 0,
    "FN": 0,
    "Precision": 1.0,
    "Recall": 1.0,
    "F1-Score": 1.0,
    "input_data": {"source_file": "sft-03-WAL_ios.sqlite"},
    "expected_source_file": "sft-03-WAL_ios.sqlite",
    "detailed_matches": [{"predicted": "sft-03-WAL_ios.sqlite", "match": true}]
  }
}
```

### Errors
| Status | Cause |
|---|---|
| 400 | Not JSON, missing required fields, or unknown `task_id` |
| 404 | `SFT03`, `SFT04`: no ground truth for this `base_test_case` and `file_name` |
| 500 | `SFT01`, `SFT02`, `SFT05`: no ground truth for this `base_test_case`, `file_name` (and `sqlite_table_name`); check the names |

### Batch evaluation
`csv_eval.py sqlite_recovery` scores many answers at once; `tests/sqlite_recovery_test.csv` is an example input.
