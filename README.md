[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Paper](https://img.shields.io/badge/paper-DFDS%202025-orange)](https://dl.acm.org/doi/abs/10.1145/3712716.3712718)
[![arXiv](https://img.shields.io/badge/arXiv-2512.16965-b31b1b.svg)](https://arxiv.org/abs/2512.16965)

<img width="150px" src="https://github.com/akila-UCD/AutoDFBench/blob/main/autoDfBench_logoV2.png?raw=true" alt="AutoDFBench Logo">

# AutoDFBench 1.0

**AutoDFBench** is an automated benchmarking framework for evaluating **digital forensic tools, scripts, and AI-generated code** against the **NIST Computer Forensics Tool Testing (CFTT) programme**.

The framework supports automated testing, validation, and benchmarking of forensic tools across multiple digital forensic tasks while generating standardised evaluation metrics including **precision, recall, F1 score, and AutoDFBench Score**.

AutoDFBench enables **reproducible and comparable benchmarking** for:

- Digital forensic tools
- DF scripts
- AI-generated forensic code
- Agent-based forensic systems

---

# Supported Digital Forensic Tasks

AutoDFBench 1.0 currently supports benchmarking for the following **CFTT forensic domains**:

- String Search
- Deleted File Recovery
- File Carving
- Windows Registry Recovery
- SQLite Data Recovery

The framework includes **63 test cases and 10,968 unique test scenarios** derived from CFTT datasets.

---

# Documentation

## API Documentation

Detailed API documentation is available here: docs/API.md

## Ground Truth Data

Details about datasets and evaluation data: docs/Data.md


---

# Recommended Setup (Docker)

The **recommended way to run AutoDFBench 1.0 is using Docker**, as the Docker environment already contains all required dependencies and configurations.

---

## 1 Create Docker Network

```bash
docker network create autodfbench-net
```
# GitHub Setup

## 1 Clone
git clone https://github.com/akila-UCD/AutoDFBench.git
cd AutoDFBench

## 2 Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```
Edit .env if necessary.
Example configuration:

```bash
CONDA_EXECUTE_ENV='/opt/conda/bin/python'
DISK_IMAGE_SOURCE_FOLDER='DD_IMAGES/'
DISK_IMAGE_DESTINATION_FOLDER='/DD_IMAGES'
WINDOWS_DATA_CSV_PATH='Data/Evaluation-Matrix-String-Searching-Windows-DataSets.csv'
UNIX_DATA_CSV_PATH='Data/Evaluation-Matrix-String-Searching-Unix-DataSets.csv'
DELETED_FILE_DATA_CSV_PATH='Data/Evaluation_prompts_deleted_file.recovery.csv'
```

## 3 Start AutoDFBench Services
```bash
docker compose up -d

```
This will start:

AutoDFBench services
MySQL database
Evaluation environment

## Running AutoDFBench APIs

AutoDFBench exposes task-specific APIs that process evaluation requests and produce structured JSON outputs.

## String Search API
```bash
python3 -m API.string_search_api
```
### Deleted File Recovery API
```bash
python3 -m API.deleted_file_recovery_api
```
### SQLite Recovery API
```bash
python3 -m API.sqlite_recovery_api
```
### File Carving API
```bash
python3 -m API.file_carving_api
```

## Batch Evaluation Using CSV

AutoDFBench allows automated batch benchmarking using CSV input files.
Each CSV contains test parameters and expected outputs.

## String Search Evaluation
```bash
python3 csv_eval.py string_search FT_SS-01 testSS_CSV.csv tests/ss/ss_results.csv --include-summary
```

## Deleted File Recovery Evaluation
```bash
python3 csv_eval.py deleted_file_recovery DFR-BATCH-01 input_dfr.csv out/dfr_results.csv --include-summary
```

## File Carving Evaluation
```bash
python3 csv_eval.py file_carving FC-BATCH-01 testFileCarv_CSV.csv tests/dfr_tests/out/file_carving_results.csv --include-summary
```

## Windows Registry Evaluation
```bash
python3 csv_eval.py windows_registry WR-BATCH-01 testWINREG_CSV.csv tests/win_reg/windows_registry_results.csv --include-summary
```

### SQLite Recovery Evaluation
```bash
python3 csv_eval.py sqlite_recovery SQLITE-SFT01-BATCH tests/sqlite_recovery_test.csv sqlite_results.csv --include-summary
```

## Running Without Docker (GitHub Installation)

Advanced users may run AutoDFBench1.0 directly from the repository.
Requirements

Install the following:

Python 3.10+
MySQL or MariaDB
Miniconda or Anaconda
Git

### Clone Repository
```bash
git clone https://github.com/akila-UCD/AutoDFBench.git
cd AutoDFBench
```

### Configure Environment

Rename
```bash
.env.example → .env
```
Modify environment variables according to your setup.

AutoDFBench Score

The evaluation results include:

- True Positives
- False Positives
- False Negatives
- Precision
- Recall
- F1 Score
- AutoDFBench Score

The AutoDFBench Score is calculated as the average of the F1 scores across all executed test cases.

This allows fair comparison between forensic tools, scripts, and AI-generated solutions.

## Citation

If you use AutoDFBench in academic work, please cite the following publications.

## Publications

AutoDFBench is described in the following peer-reviewed publications.

### AutoDFBench (DFDS 2025)

Akila Wickramasekara, Alanna Densmore, Frank Breitinger, Hudan Studiawan, and Mark Scanlon.  
**AutoDFBench: A Framework for AI Generated Digital Forensic Code and Tool Testing and Evaluation.**  
Digital Forensics Doctoral Symposium (DFDS), 2025.

Paper: https://dl.acm.org/doi/abs/10.1145/3712716.3712718

```bibtex
@inproceedings{wickramasekara2025AutoDFBench,
author={Wickramasekara, Akila and Densmore, Alanna and Breitinger, Frank and Studiawan, Hudan and Scanlon, Mark},
title={AutoDFBench: A Framework for AI Generated Digital Forensic Code and Tool Testing and Evaluation},
booktitle={Digital Forensics Doctoral Symposium},
series={DFDS 2025},
year=2025,
month=04,
publisher={Association for Computing Machinery},
doi={10.1145/3712716.3712718}
}
```
### AutoDFBench 1.0

Akila Wickramasekara, Tharusha Mihiranga, Aruna Withanage, Buddhima Weerasinghe, Frank Breitinger, John Sheppard, and Mark Scanlon.
**AutoDFBench 1.0: A Benchmarking Framework for Digital Forensic Tool Testing and Generated Code Evaluation.**

Paper: https://arxiv.org/abs/2512.16965

```bibtex
@article{Wickramasekara2026AutoDFBench1.0,
title = {AutoDFBench 1.0: A Benchmarking Framework for Digital Forensic Tool Testing and Generated Code Evaluation},
journal = {Forensic Science International: Digital Investigation},
volume = {56S},
month = {03},
year = {2026},
issn = {2666-2817},
author = {Akila Wickramasekara and Tharusha Mihiranga and Aruna Withanage and Buddhima Weerasinghe and Frank Breitinger and John Sheppard and Mark Scanlon},
keywords = {Digital Forensics, Tool Testing and Validation, Generated Code Validation, Benchmark, NIST Computer Forensics Tool Testing Program (CFTT)},
abstract = {The National Institute of Standards and Technology (NIST) Computer Forensic Tool Testing (CFTT) programme has become the de facto standard for providing digital forensic tool testing and validation. However to date, no comprehensive framework exists to automate benchmarking across the diverse forensic tasks included in the programme. This gap results in inconsistent validation, challenges in comparing tools, and limited validation reproducibility. This paper introduces AutoDFBench 1.0, a modular benchmarking framework that supports the evaluation of both conventional DF tools and scripts, as well as AI-generated code and agentic approaches. The framework integrates five areas defined by the CFTT programme: string search, deleted file recovery, file carving, Windows registry recovery, and SQLite data recovery. AutoDFBench 1.0 includes ground truth data comprising of 63 test cases and 10,968 unique test scenarios, and execute evaluations through a RESTful API that produces structured JSON outputs with standardised metrics, including precision, recall, and F1 score for each test case, and the average of these F1 scores becomes the AutoDFBench Score. The benchmarking framework is validated against CFTT datasets. The framework enables fair and reproducible comparison across tools and forensic scripts, establishing the first unified, automated, and extensible benchmarking framework for digital forensic tool testing and validation. AutoDFBench 1.0 supports tool vendors, researchers, practitioners, and standardisation bodies by facilitating transparent, reproducible, and comparable assessments of DF technologies.}
}
```

## License

AutoDFBench is released as open-source software under the Apache License 2.0.

The framework is publicly available via the GitHub repository:

https://github.com/akila-UCD/AutoDFBench

The Apache 2.0 license permits use, modification, and distribution of the software while requiring preservation of the copyright notice and license terms.

See the LICENSE file for the full license text.