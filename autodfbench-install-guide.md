# AutoDFBench Installation Guide

AutoDFBench runs as one container (or one Python process). The ground truth is a SQLite file that ships with the repository, so there is no database server to install or configure.

## Option 1: Docker

### 1. Install Docker

- **Windows / macOS:** install Docker Desktop and start it.
- **Linux:** install Docker Engine and the Docker Compose plugin from Docker's package repository.

Check the installation:

```bash
docker --version
docker compose version
```

### 2. Clone and start

```bash
git clone https://github.com/akila-UCD/AutoDFBench.git
cd AutoDFBench
docker compose up -d
```

This pulls the prebuilt image `akila1989/autodfbench-api:1.1.1` from Docker Hub (about 106 MB). To build it from the source instead, use `docker compose up -d --build`.

No `.env` file and no database credentials are needed. The MySQL settings used before 1.1 (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, …) are no longer read, so you can delete them from an old `.env`.

### 3. Check it is running

```bash
docker compose ps
docker compose logs autodfbench
```

The log lists the five APIs (ports 8000–8004). A quick request:

```bash
curl -s -X POST http://localhost:8000/api/v1/string-search/evaluate \
  -H "Content-Type: application/json" \
  -d '{"base_test_case":"FT-SS-01","file_contents_found":[""],"os":"windows","tool_used":"test","write_db":false}'
```

A JSON response with `total_gt_lines` means the API and ground truth are working.

### 4. Stop / update

```bash
docker compose down                        # stop
git pull && docker compose pull && docker compose up -d   # update to a newer version
```

Results written with `write_db: true` are kept in `results/autodfbench_results.sqlite` on the host.

## Option 2: Python only

Requires Python 3.10–3.12 (the file-carving API uses the `cgi` module, removed in Python 3.13).

```bash
git clone https://github.com/akila-UCD/AutoDFBench.git
cd AutoDFBench
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-api.txt
python serve.py                    # or: python serve.py --base-port 9000
```

Stop with Ctrl+C.

## Ports

| Port | API |
|---|---|
| 8000 | String Search |
| 8001 | Deleted File Recovery |
| 8002 | File Carving |
| 8003 | Windows Registry |
| 8004 | SQLite Recovery |

If a port is already in use, change the left-hand side of `ports` in `docker-compose.yml` (e.g. `"9000-9004:8000-8004"`) or use `python serve.py --base-port 9000`.

## Settings (optional)

All settings have working defaults; see the Configuration section of the README for the full list.
- **Without Docker:** copy `.env.example` to `.env` in the project folder and edit it.
- **With Docker:** add variables under `environment:` in `docker-compose.yml`.

Example, keeping results in another folder:

```yaml
services:
  autodfbench:
    environment:
      AUTODFBENCH_RESULTS_DB: /app/results/my_results.sqlite
```

## Troubleshooting

### `Ground-truth database not found`

`ground_truth/autodfbench_gt.sqlite` is missing. Make sure the clone is complete (`git status`) and that the file's checksum matches:

```bash
cd ground_truth && sha256sum -c autodfbench_gt.sqlite.sha256
```

### `Invalid test case or no GT rows`

The API is reachable, but the `base_test_case` in the request does not exist for that task. Check the test case names in the documentation under `docs/`.

### File carving / Windows registry return no ground-truth files

These two APIs read source files from `Data/`, which is not part of the repository. Place the data in `Data/` in the project folder; Docker mounts it into the container read-only.
