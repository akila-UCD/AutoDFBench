# AutoDFBench Deleted File Recovery (DFR) Test Cases

This document introduces the **Deleted File Recovery (DFR)** test cases in AutoDFBench. It covers how the cases are organised, which test sets they belong to, what a submission looks like and how each submission is scored.

The DFR test cases come from the NIST CFTT deleted file recovery datasets. Each case is a raw disk image (`.dd`) containing files that were deleted in a known, controlled way. The ground truth for every image (file names, sizes, MAC timestamps and data blocks) is stored in the `ground_truth` table of the AutoDFBench database (`cftt_task = 'deleted_file_recovery'`).

---

## 1. Naming Convention

Every test case is identified by a `base_test_case` string:

```
DFR-<NN>/<fs>-<NN>[-<variant>]
```

| Part | Meaning | Examples |
|---|---|---|
| `DFR-<NN>` | Main test case (scenario) | `DFR-01`, `DFR-07`, `DFR-14` |
| `<fs>` | File system of the image | `fat`, `ntfs`, `ext`, `xfat` |
| `<variant>` | Optional scenario variant | `recycle`, `braid`, `nest`, `one`, `two`, `compress`, `mft` |

Examples: `DFR-01/ext-01`, `DFR-05/ntfs-05-braid`, `DFR-11/ntfs-11-mft`.

The matching disk images are named `DFR-<NN>/dfr-<NN>[-<variant>]-<fs>.dd`, for example `DFR-05/dfr-05-braid-ntfs.dd`.

---

## 2. Test Sets

A single disk image can be evaluated under different **test sets**. The test set decides what a tool must recover and how a recovered file is matched to the ground truth.

> **Important:** pass the test set names to the API **exactly as written below**, including their original spellings (for example `NO_OVERWITE_TESTS`, `NON_LATIN_CHAR_TETS`, `SPECAIL_OBJECTS_TESTS`). Any other spelling is rejected.

| Test set | What it evaluates | Matching rule (a submitted file is a TP when…) | Required per-file fields |
|---|---|---|---|
| `NO_OVERWITE_TESTS` | Recovery of deleted files whose content has **not** been overwritten (simple, fragmented, braided, nested and directory scenarios) | its data-block set **exactly** matches a ground-truth file's block set | `file_name`, `blocks` |
| `OVERWITE_TESTS` | Recovery when deleted files are **partially or fully overwritten** by later activity | its data-block set **exactly** matches a ground-truth file's block set | `file_name`, `blocks` |
| `RECYCLE_DEL_TESTS` | Files deleted through the **Recycle Bin / Trash** | its data-block set **exactly** matches a ground-truth file's block set | `file_name`, `blocks` |
| `FILE_SIZE_TESTS` | Correct **file size** reporting for recovered files | its `file_size` equals the size of an unmatched ground-truth file | `file_name`, `file_size` |
| `MAC_TIME_TESTS` | Correct **MAC timestamps** (modified / accessed / changed) | its timestamps give the best weighted match against an unmatched ground-truth file | `file_name`; with `check_meta=true`: `deleted_timestamp`, `modified_timestamp`, `accessed_timestamp`, `changed_timestamp` (epoch **int**) |
| `NON_LATIN_CHAR_TETS` | Recovery of files with **non-Latin (Unicode) file names** | its name matches a ground-truth file name (Unicode-normalised comparison) | `file_name` |
| `SPECAIL_NTFS_TEST` | NTFS special cases: **compressed** files and **MFT-resident** files | both its name **and** size match a ground-truth file | `file_name`, `file_size` |
| `SPECAIL_OBJECTS_TESTS` | **Special file-system objects** (for example links and their targets) | both its name **and** size match a ground-truth file | `file_name`, `file_size` |

Each ground-truth file can be matched at most once. Duplicate `file_name` values in a submission are rejected.

---

## 3. Test Case Catalogue

### 3.1 Reference DFR test plan (44 runs)

This is the set of DFR runs used to evaluate the DFR helper script. It covers every test set on FAT, NTFS and EXT.

| Main case | `base_test_case` | Test set | `check_meta` | Disk image |
|---|---|---|---|---|
| DFR-01 | `DFR-01/{ext,fat,ntfs}-01` | `NO_OVERWITE_TESTS` | false | `DFR-01/dfr-01-{fs}.dd` |
| DFR-01 | `DFR-01/{ext,fat,ntfs}-01` | `MAC_TIME_TESTS` | true | `DFR-01/dfr-01-{fs}.dd` |
| DFR-01 | `DFR-01/{ext,fat,ntfs}-01` | `FILE_SIZE_TESTS` | true | `DFR-01/dfr-01-{fs}.dd` |
| DFR-01 | `DFR-01/{ext,fat,ntfs}-01-recycle` | `RECYCLE_DEL_TESTS` | false | `DFR-01/dfr-01-recycle-{fs}.dd` |
| DFR-02 | `DFR-02/{ext,fat,ntfs}-02` | `NO_OVERWITE_TESTS` | false | `DFR-02/dfr-02-{fs}.dd` |
| DFR-03 | `DFR-03/{ext,fat,ntfs}-03` | `NO_OVERWITE_TESTS` | false | `DFR-03/dfr-03-{fs}.dd` |
| DFR-04 | `DFR-04/{ext,fat,ntfs}-04` | `NON_LATIN_CHAR_TETS` | true | `DFR-04/dfr-04-{fs}.dd` |
| DFR-05 | `DFR-05/{ext,fat,ntfs}-05` | `NO_OVERWITE_TESTS` | false | `DFR-05/dfr-05-{fs}.dd` |
| DFR-05 | `DFR-05/{ext,fat,ntfs}-05-braid` | `NO_OVERWITE_TESTS` | false | `DFR-05/dfr-05-braid-{fs}.dd` |
| DFR-05 | `DFR-05/{ext,fat,ntfs}-05-nest` | `NO_OVERWITE_TESTS` | false | `DFR-05/dfr-05-nest-{fs}.dd` |
| DFR-07 | `DFR-07/{ext,fat,ntfs}-07` | `OVERWITE_TESTS` | false | `DFR-07/dfr-07-{fs}.dd` |
| DFR-11 | `DFR-11/{ext,fat,ntfs}-11` | `NO_OVERWITE_TESTS` | false | `DFR-11/dfr-11-{fs}.dd` |
| DFR-11 | `DFR-11/ntfs-11-compress` | `SPECAIL_NTFS_TEST` | true | `DFR-11/dfr-11-compress-ntfs.dd` |
| DFR-11 | `DFR-11/ntfs-11-mft` | `SPECAIL_NTFS_TEST` | true | `DFR-11/dfr-11-mft-ntfs.dd` |
| DFR-12 | `DFR-12/{ext,fat,ntfs}-12` | `OVERWITE_TESTS` | false | `DFR-12/dfr-12-{fs}.dd` |
| DFR-14 | `DFR-14/{ext,fat,ntfs}-14` | `SPECAIL_OBJECTS_TESTS` | true | `DFR-14/dfr-14-{fs}.dd` |

`{ext,fat,ntfs}` means one run per file system: 14 rows × 3 file systems + 2 NTFS-only rows = **44 runs**.

### 3.2 Ground-truth file counts (FAT / NTFS / EXT)

These are the number of deleted files recorded in the ground truth for each case (database `AutoDFBench1.3.sql`).

| Base case | FAT | NTFS | EXT |
|---|---:|---:|---:|
| DFR-01 | 3 | 1 | 9 |
| DFR-01 `-recycle` | 3 | 1 | 12 |
| DFR-02 | 3 | 1 | 12 |
| DFR-03 | 3 | 1 | 3 |
| DFR-04 | 36 | 12 | 36 |
| DFR-05 | 6 | 2 | 6 |
| DFR-05 `-braid` | 6 | 2 | 6 |
| DFR-05 `-nest` | 6 | 2 | 6 |
| DFR-06 | 3 | 1 | 3 |
| DFR-07 | 15 | 4 | 15 |
| DFR-07 `-one` | 9 | 3 | 9 |
| DFR-07 `-two` | 9 | 3 | 9 |
| DFR-08 | 40 | 25 | 50 |
| DFR-09 | 780 | 260 | 780 |
| DFR-10 | 2340 | 780 | 2340 |
| DFR-11 | 9 | 3 | 9 |
| DFR-11 `-compress` | – | 3 | – |
| DFR-11 `-mft` | – | 3 | – |
| DFR-12 | 36 | 12 | 36 |
| DFR-13 | 40 | 40 | 40 |
| DFR-14 | 12 | 15 | 6 |

The database also contains exFAT (`xfat`) ground truth for most cases, which can be used for extended experiments.

---

## 4. Evaluation API

### Endpoint

```
POST /api/v1/deleted_file_recovery/evaluate
Content-Type: application/json
```

In the Docker setup the DFR API listens on port **8001** (`http://localhost:8001`). To run it locally:

```bash
python3 -m API.deleted_file_recovery_api      # uses API_PORT, default 8000
```

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `base_test_case` | string | yes | e.g. `DFR-01/ntfs-01` |
| `tool_used` | string | yes | Tool / model / script name, e.g. `The Sleuth Kit ver 3.2.2` |
| `test_set` | string | yes | One of the test sets in Section 2 |
| `files` | array | yes | Recovered files (see below) |
| `file_system` | string | no | `FAT`, `NTFS`, `EXT`, … (used for name normalisation) |
| `check_meta` | bool | no | Enables metadata validation (needed for `MAC_TIME_TESTS`) |
| `sector_size` | int | no | Default `512` |
| `weights` | object | no | MAC weights: `modify_time_stamp`, `access_time_stamp`, `change_time_stamp` (default 1/3 each) |
| `write_db` | bool | no | Store the result in the database (default `true`) |
| `write_reports` | bool | no | Write a JSON report and a summary CSV to `results_dir` (default `true`, `./dfr_tests`) |

Each entry in `files`:

| Field | Type | Description |
|---|---|---|
| `file_name` | string | Recovered file name (path allowed) |
| `blocks` | list / string | Data blocks (sectors) of the file; ranges such as `"100-120"` are expanded |
| `file_size` | int | Size in bytes |
| `deleted_timestamp`, `modified_timestamp`, `accessed_timestamp`, `changed_timestamp` | int | Epoch seconds (UTC) |

### Example

```bash
curl -X POST http://localhost:8001/api/v1/deleted_file_recovery/evaluate \
  -H "Content-Type: application/json" \
  -d '{
        "base_test_case": "DFR-01/ntfs-01",
        "tool_used": "The Sleuth Kit ver 3.2.2",
        "test_set": "NO_OVERWITE_TESTS",
        "file_system": "NTFS",
        "check_meta": false,
        "files": [
          {"file_name": "example.txt", "file_size": 2048, "blocks": [10432, 10433, 10434, 10435]}
        ]
      }'
```

### Response (abridged)

```json
{
  "tool_used": "The Sleuth Kit ver 3.2.2",
  "base_test_case": "DFR-14/ext-14",
  "test_set_used": "SPECAIL_OBJECTS_TESTS",
  "total_ground_truth_files": 6,
  "total_submitted_files": 22,
  "true_positives": 0,
  "false_positives": 22,
  "false_negatives": 6,
  "precision": 0.0,
  "recall": 0.0,
  "F1": 0.0,
  "AutoDFBench_score": 0.0,
  "Rec": 22, "SS": 10, "Full": 2, "First": 2, "Match": 6,
  "Over": 0, "Multi": 0, "Size_match": 2, "GT_COUNT": 6,
  "details": [
    {"submitted_file": "Castor-far-rmLink-X4.txt", "mapped_gt_for_f1": null, "meets_f1": false,
     "flags": {"Match": true, "SS": false, "Full": false, "First": false, "Over": false, "Multi": false, "Size_match": false}}
  ]
}
```

A full sample response is in `dfr_tests/DFR-14_ext-14_The_Sleuth_Kit_ver_3.2.2.json`.

---

## 5. Scoring

- **TP / FP / FN** follow the matching rule of the selected test set (Section 2). A submitted file that cannot be matched is a **FP**. Ground-truth files that were never matched are **FN**.
- **Precision** = TP / (TP + FP), **Recall** = TP / (TP + FN), **F1** = harmonic mean.
- `AutoDFBench_score` for a single run is its F1. The overall AutoDFBench DFR score is the **mean F1 across all executed runs**.

### Diagnostic counters

These counters give extra detail. They do not change the F1.

| Counter | Meaning |
|---|---|
| `Rec` | Number of files submitted |
| `SS` | Submitted files that include at least one data block |
| `Match` | Submitted file names that match a ground-truth name |
| `Full` | Submitted block sets that exactly match a ground-truth file |
| `First` | Submitted files whose first block equals a ground-truth first block |
| `Over` | Submitted files that report more blocks than the matched ground-truth file |
| `Multi` | Same first block as a ground-truth file but a different block set |
| `Size_match` | Submitted sizes that match the corresponding ground-truth file |

---

## 6. Running the Full DFR Test Plan with a Helper Script

Run the test plan in Section 3.1 with a helper script, one call per test case:

1. Run the helper on the disk image to collect deleted-file metadata (names, sizes, blocks, MAC times), for example with The Sleuth Kit (`mmls`, `fsstat`, `fls -d`, `istat`):

   ```bash
   python3 dfr_helper_V1.py \
     --dd_image DFR-01/dfr-01-ntfs.dd \
     --benchmarking TRUE \
     --base_test_case DFR-01/ntfs-01 \
     --test_set NO_OVERWITE_TESTS \
     --check_meta false
   ```

   The helper prints one JSON object whose `test_cases[0]` holds `base_test_case`, `tool_used`, `test_set`, `check_meta`, `file_system`, `file_count` and `files`.

2. POST `test_cases[0]` to the DFR API (Section 4).
3. Collect `F1`, `precision` and `recall` for each run. Average them per main case (DFR-01, DFR-02, …) and over all runs to get the overall DFR score.

Batch evaluation from a CSV is also supported:

```bash
python3 csv_eval.py deleted_file_recovery DFR-BATCH-01 input_dfr.csv out/dfr_results.csv --include-summary
```
