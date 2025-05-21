# AutoDFBench File Carving Evaluation API

## Endpoint
`POST /api/v1/file-carving/evaluate`

### Parameters (multipart/form-data)
| Field           | Type    | Description                          |
|----------------|---------|--------------------------------------|
| base_test_case | string  | Test case name (e.g. carv-contig-bmp) |
| files          | file[]  | One or more carved output files       |

### Sample `curl` command
```bash
curl -X POST http://localhost:8000/api/v1/file-carving/evaluate \
  -F "base_test_case=carv-contig-bmp" \
  -F "files=@./recovered1.bmp" \
  -F "files=@./recovered2.bmp"

### Responce SAMPLE 
{
  "base_test_case": "carv-contig-bmp",
  "total_submitted_files": 2,
  "matched_files": 1,
  "precision": 0.5,
  "recall": 0.5,
  "f1_score": 0.5,
  "details": [
    {
      "submitted_file": "recovered1.bmp",
      "temp_path": "./uploaded_files/recovered1.bmp",
      "matched": true,
      "ground_truth_match": "/ground_truths/image1.bmp",
      "similarity_score": 0.92
    },
    ...
  ]
}
