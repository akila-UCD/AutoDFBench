# AutoDFBench File Carving Evaluation API

## Endpoint
`POST /api/v1/file-carving/evaluate`

### Parameters (multipart/form-data)
| Field           | Type    | Description                          |
|----------------|---------|--------------------------------------|
| base_test_case | string  | Test case name (e.g. carv-contig-bmp) |
| tool_used | string  | Tool name which used for the testing (e.g. Scalpel_version_1.60) |
| files          | file[]  | One or more carved output files       |

### Sample `curl` command
```bash
curl -X POST http://localhost:8000/api/v1/file-carving/evaluate \
  -F "base_test_case=carv-contig-bmp" \
  -F "tool_used=Scalpel_version_1.60" \
  -F "files=@./recovered1.bmp" \
  -F "files=@./recovered2.bmp"

### Responce SAMPLE 
{
  "base_test_case": "carv-frag-jpg",
  "total_ground_truth_files": 6,
  "total_submitted_files": 13,
  "true_positives": 6,
  "false_positives": 7,
  "false_negatives": 0,
  "precision": 0.46153846153846156,
  "recall": 1.0,
  "f1_score": 0.631578947368421,
  "details": [
    {
      "submitted_file": "00000000.jpg",
      "matched": true,
      "matched_gt_file": "leaf.jpg"
    },
    ...
  ]
}
