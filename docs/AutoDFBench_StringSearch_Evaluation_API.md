# AutoDFBench String Search API

**Endpoint:** `POST http://localhost:8000/api/v1/string-search/evaluate`  
**Content-Type:** `application/json`

---

## Overview

The AutoDFBench String Search API evaluates a forensic tool's output against a predefined benchmark test case. Each request submits the benchmark case identifier, the content recovered by the forensic tool, the operating system context, and the tool metadata.

---

## Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `base_test_case` | `string` | ✅ | Benchmark test case identifier (e.g. `FT-SS-08-c`) |
| `file_contents_found` | `array[string]` | ✅ | List of strings recovered/found by the forensic tool |
| `os` | `string` | ✅ | Operating system used during evaluation (`windows` / `linux`) |
| `tool_used` | `string` | ✅ | Forensic tool name and version |

---

## Example Request

The example below submits results for test case `FT-SS-08-c` (SSN — PII detection), evaluated using IPED on Windows.

```json
{
  "base_test_case": "FT-SS-08-c",
  "file_contents_found": [
    "[LITERAL] ASCII ====> 123-45-6789 1009 <==== fat BlueCrab Carp"
  ],
  "os": "windows",
  "tool_used": "IPED Version 3.18.13"
}
```

### cURL (Windows PowerShell)

```powershell
curl -X POST "http://localhost:8000/api/v1/string-search/evaluate" `
  -H "Content-Type: application/json" `
  -d '{
    "base_test_case": "FT-SS-08-c",
    "file_contents_found": [
      "[LITERAL] ASCII ====> 123-45-6789 1009 <==== fat BlueCrab Carp"
    ],
    "os": "windows",
    "tool_used": "IPED Version 3.18.13"
  }'
```

### Python

```python
import requests

url = "http://localhost:8000/api/v1/string-search/evaluate"

payload = {
    "base_test_case": "FT-SS-08-c",
    "file_contents_found": [
        "[LITERAL] ASCII ====> 123-45-6789 1009 <==== fat BlueCrab Carp"
    ],
    "os": "windows",
    "tool_used": "IPED Version 3.18.13"
}

response = requests.post(url, json=payload)
print(response.status_code)
print(response.json())
```

---

## Notes on `file_contents_found`

- Pass the **raw string output** returned by the forensic tool for the relevant test case.
- If the tool found **no results**, pass an empty string: `[""]`.
- Multiple recovered strings can be included as separate list entries.
- If the result is unknown at time of evaluation, leave blank and fill manually before submission.

---

## Test Case Catalog

> **Sub test case** is `—` when the base test case is the direct evaluation target (no sub-group applies).

| CFTT test case | base test case | Search keyword / target |
|---|---|---|
| FT-SS-01 | FT-SS-01 | DireWolf |
| FT-SS-02 | FT-SS-02 | WOLF |
| FT-SS-02 | FT-SS-02 | wolf | 
| FT-SS-02 | FT-SS-02 | Wolf |
| FT-SS-02 | FT-SS-02-d | DireWolf |
| FT-SS-02 | FT-SS-02-e | WereWolf |
| FT-SS-03 | FT-SS-03-a | WOLF |
| FT-SS-03 | FT-SS-03-b | wolf |
| FT-SS-03 | FT-SS-03-c | Wolf |
| FT-SS-04 | FT-SS-04 | panda,fox |
| FT-SS-05 | FT-SS-05 | Were,Dire | 
| FT-SS-06 | FT-SS-06 | fox,not:tiger |
| FT-SS-07-CJK-char | FT-SS-07-a1 | 中国 |
| FT-SS-07-CJK-char | FT-SS-07-a2 | 東京 |
| FT-SS-07-CJK-hangul | FT-SS-07-b | 서울 |
| FT-SS-07-CJK-kana | FT-SS-07-c1 | スバル |
| FT-SS-07-CJK-kana | FT-SS-07-c2 | みつびし |
| FT-SS-07-Cyrillic | FT-SS-07-d | Сибирь |
| FT-SS-07-Latin | FT-SS-07-e1 | garçon |
| FT-SS-07-Latin | FT-SS-07-e2 | Schönheit |
| FT-SS-07-NoBOM | FT-SS-07-f1 | Россия |
| FT-SS-07-NoBOM | FT-SS-07-f3 | 中國 | 
| FT-SS-07-NoBOM | FT-SS-07-f4 | QuarterHorse |
| FT-SS-07-Norm | FT-SS-07-g1 | mañana (NFD) | 
| FT-SS-07-Norm | FT-SS-07-g8 | mañana (NFC) |
| FT-SS-07-Norm | FT-SS-07-g2 | infinity | 
| FT-SS-07-Norm | FT-SS-07-g3 | Mäuse (NFD) | 
| FT-SS-07-Norm | FT-SS-07-g5 | Mäuse (NFC) |
| FT-SS-07-Norm | FT-SS-07-g4 | infiﬁnity (ligature) |
| FT-SS-07-Norm | FT-SS-07-g6 | libertà (NFC) |
| FT-SS-07-Norm | FT-SS-07-g7 | libertà (NFD) |
| FT-SS-07-Norm | FT-SS-07-h | الكسكس |
| FT-SS-08 | FT-SS-08-a1 | iron.man@marvel.com | 
| FT-SS-08 | FT-SS-08-a2| potus@capitol.gov |
| FT-SS-08 | FT-SS-08-a3 | berlin@deutchland.net |
| FT-SS-08 | FT-SS-08-a4 | kgb@moscow.red.square.ru |
| FT-SS-08 | FT-SS-08-b1 | (901)555-1111 |
| FT-SS-08 | FT-SS-08-b2 | 301.555-9009 |
| FT-SS-08 | FT-SS-08-b3 | 800-555-1122 | 
| FT-SS-08 | FT-SS-08-c | 123-45-6789 |
| FT-SS-08 | FT-SS-08-d | 987-65-4321 |
| FT-SS-08 | FT-SS-08-e  | 999-55-1321 |
| FT-SS-09 | FT-SS-09-a1 | longbow | 
| FT-SS-09 | FT-SS-09-a2 | shotgun | 
| FT-SS-09 | FT-SS-09-a3 | revolver |
| FT-SS-09 | FT-SS-09-a4 | peroxide |
| FT-SS-09 | FT-SS-09-a5 | nitroglycerin |
| FT-SS-09 | FT-SS-09-a6 | rifle | 
| FT-SS-09 | FT-SS-09-a7 | crossbow |
| FT-SS-09 | FT-SS-09-a8 | flintlock |
| FT-SS-09-Frag | FT-SS-09-Frag1 | California |
| FT-SS-09-Frag | FT-SS-09-Frag2 | Washington |
| FT-SS-09-Lost | FT-SS-09-Lost-a | SecretKey |
| FT-SS-09-Lost | FT-SS-09-Lost-b | disconnected |
| FT-SS-09-MFT | FT-SS-09-MFT| bear |
| FT-SS-09-Meta | FT-SS-09-Meta-a | cañón |
| FT-SS-09-Meta | FT-SS-09-Meta-a | thunderbird |
| FT-SS-10-Regex | FT-SS-10-a1 | DireWolf |
| FT-SS-10-Regex | FT-SS-10-a2 | WereWolf |

---

## Prerequisites

Ensure the AutoDFBench Docker container is running before making requests:

```bash
docker compose up -d
```

---

*AutoDFBench Framework — String Search Benchmark API v1*
