# AutoDFBench File Carving Evaluation API

## Endpoint
`POST /api/v1/file-carving/evaluate` (port 8002)

### Test data
The test cases use the CFTT **File Carving Graphic Files** (2023) data set from CFReDS:

| Item | Description |
|---|---|
| Images | 18 images named `image-<layout>-<type>.dd`; the matching test case is `carv-<layout>-<type>` |
| Layouts | `contig` (contiguous, sector aligned), `non` (not sector aligned), `frag` (fragmented in order with fill between fragments) |
| Types | `heic`, `png`, `jpg`, `bmp`, `tiff`, `gif` |
| Ground truth | 6 original files per test case |

The original files (the `source` folder of the data set) must be in `Data/source`, or in the folder given by `CARVING_SOURCE_DIR`.
The API returns an error if a test case's originals are missing.

### Parameters (multipart/form-data)
| Field           | Type    | Description                          |
|----------------|---------|--------------------------------------|
| base_test_case | string  | Test case name (e.g. carv-contig-bmp) |
| tool_used | string  | Tool name which used for the testing (e.g. Scalpel_version_1.60) |
| files          | file[]  | One or more carved output files       |
| write_db       | bool    | Store the result in the results database (default `true`) |

### Sample `curl` command
```bash
curl -X POST http://localhost:8002/api/v1/file-carving/evaluate \
  -F "base_test_case=carv-contig-bmp" \
  -F "tool_used=Scalpel_version_1.60" \
  -F "write_db=false" \
  -F "files=@./recovered1.bmp" \
  -F "files=@./recovered2.bmp"
```

### Scoring
Each submitted file is matched to the most similar original, using a perceptual hash (pHash).

- **TP:** the submitted file decodes, and its byte similarity to that original is above 20%.
- **One TP per original:** if several submitted files match the same original, the most similar one is the TP and the others are FPs.
- **FP:** any other submitted file.
- **FN:** an original with no TP.

HEIC files are opened with `pillow-heif`.

### Response sample
```json
{
  "base_test_case": "carv-frag-jpg",
  "test_case": "carv-frag-jpg_Scalpel_version_1.60",
  "tool_used": "Scalpel_version_1.60",
  "counts": {"total_ground_truth_files": 6, "total_submitted_files": 7, "tp": 6, "fp": 1, "fn": 0},
  "scores": {"precision": 0.857143, "recall": 1.0, "f1": 0.923077},
  "details": [
    {
      "submitted_file": "00000000.jpg",
      "matched_gt_file": "leaf.jpg",
      "counted_as": "TP",
      "metrics": {"byte_similarity": 1.0, "recall_blocks": 1.0, "...": "..."},
      "file_scores": {"error_check": {"decodes": true, "decode_error": null}, "quality_label": "Complete no flaws"},
      "...": "..."
    }
  ],
  "params": {"...": "..."}
}
```
