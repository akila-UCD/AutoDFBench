# AutoDFBench Installation Guide

This guide explains how to install and run AutoDFBench on both Windows and Linux using Docker and Docker Compose. Docker Desktop is the standard path on Windows, while Docker Engine plus the Docker Compose plugin is the standard path on Linux.[cite:523][cite:527][cite:525]

## Requirements

Before starting, make sure the target machine has internet access, enough disk space for Docker images and containers, and permission to install system software. On Windows, Docker Desktop typically uses the WSL 2 backend, while on Ubuntu Linux the recommended method is installing Docker Engine from Docker's apt repository and adding the Docker Compose plugin.[cite:523][cite:527][cite:525]

## Windows setup

### 1. Install Docker Desktop

1. Download Docker Desktop for Windows from the official Docker Desktop page.[cite:523][cite:526]
2. Run `Docker Desktop Installer.exe` as an administrator.[cite:526][cite:529]
3. During setup, keep the WSL 2 option enabled if it is available.[cite:523][cite:526]
4. Finish the installation and restart Windows if prompted.[cite:523][cite:529]
5. Open Docker Desktop and confirm it starts successfully.[cite:523][cite:529]

### 2. Verify Docker

Open PowerShell and run:

```powershell
docker --version
docker compose version
```

These commands confirm that Docker and the Compose plugin are available on the system.[cite:525][cite:530]

### 3. Get the AutoDFBench project

Clone or copy the AutoDFBench project folder onto the machine, then open PowerShell in that folder. The project directory must contain the `docker-compose.yml` file and the related application files.

### 4. Create the environment file

Inside the AutoDFBench project folder, create a `.env` file with the database credentials:

```powershell
@"
MYSQL_ROOT_PASSWORD=adfbroot123
MYSQL_USER=autodfbench_user
MYSQL_PASSWORD=adfb123
"@ | Set-Content .env
```

Docker Compose automatically reads `.env` from the project directory when it starts services from that folder.[cite:531]

### 5. Fix shell script line endings if needed

If the API container fails with an error like `/usr/bin/env: 'bash\r': No such file or directory`, convert shell scripts such as `docker/entrypoint.sh` from CRLF to LF line endings. This error is caused by Windows-style line endings in Linux shell scripts.[cite:523]

A PowerShell fix is:

```powershell
$content = Get-Content .\docker\entrypoint.sh -Raw
$content = $content -replace "`r`n", "`n"
[System.IO.File]::WriteAllText((Resolve-Path .\docker\entrypoint.sh), $content)
```

### 6. Start AutoDFBench

Run:

```powershell
docker compose up -d --build
```

This builds the AutoDFBench API image if needed and starts the MySQL and API containers in detached mode.[cite:525]

### 7. Check container status

Run:

```powershell
docker compose ps
docker ps
docker logs autodfbench-api --tail=50
```

A healthy setup should show the MySQL container running and the API container in the `Up` state. If the API logs show multiple services entering the `RUNNING` state, the application backend has started successfully.

### 8. Test the API

Once the API is up, test it from PowerShell with `Invoke-RestMethod`. Example:

```powershell
$raw = @"
{
  "tool_used": "IPED Version 3.18.13",
  "base_test_case": "FT-SS-08-c",
  "os": "windows",
  "file_contents_found": [
    "[LITERAL] ASCII ====> 123-45-6789 1009 <==== fat BlueCrab Carp"
  ]
}
"@

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/string-search/evaluate" -ContentType "application/json; charset=utf-8" -Body $raw
```

If the benchmark data is loaded correctly, the API returns an evaluation result instead of a 400 error.

## Linux setup

### 1. Install Docker Engine

On Ubuntu, install Docker Engine using Docker's official apt repository.[cite:527]

```bash
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

This installs Docker Engine and the Docker Compose plugin from Docker's official packages.[cite:527][cite:525]

### 2. Verify Docker

Run:

```bash
docker --version
docker compose version
```

These commands confirm that Docker Engine and Compose are installed correctly.[cite:525][cite:527]

### 3. Optional: run Docker without sudo

Add your user to the `docker` group and then log out and back in:

```bash
sudo usermod -aG docker $USER
```

This step is commonly used on Linux so Docker commands can be run without `sudo`.[cite:524]

### 4. Get the AutoDFBench project

Clone or copy the AutoDFBench repository to the Linux machine and change into that directory:

```bash
cd /path/to/AutoDFBench
```

### 5. Create the environment file

Create a `.env` file in the project root:

```bash
cat > .env <<EOF
MYSQL_ROOT_PASSWORD=adfbroot123
MYSQL_USER=autodfbench_user
MYSQL_PASSWORD=adfb123
EOF
```

Docker Compose reads `.env` from the working directory where the compose file is launched.[cite:525][cite:531]

### 6. Start AutoDFBench

Run:

```bash
docker compose up -d --build
```

This starts the MySQL and AutoDFBench API services in the background.[cite:525]

### 7. Check container status

Run:

```bash
docker compose ps
docker ps
docker logs autodfbench-api --tail=50
```

The API should show as `Up`, and the logs should indicate the supervised API processes have entered the running state.

### 8. Test the API

Use `curl` on Linux:

```bash
curl -X POST "http://localhost:8000/api/v1/string-search/evaluate" \
  -H "Content-Type: application/json" \
  --data-raw '{
    "base_test_case":"FT-SS-08-c",
    "file_contents_found":["[LITERAL] ASCII ====> 123-45-6789 1009 <==== fat BlueCrab Carp"],
    "os":"windows",
    "tool_used":"IPED Version 3.18.13"
  }'
```

A valid response confirms that the API is working and that the benchmark database contains matching ground-truth rows.

## Database notes

AutoDFBench depends on MySQL being initialized correctly. If MySQL credentials do not work after editing `.env`, the data volume may have been created earlier with different credentials, because MySQL initialization variables apply only when the data directory is first created.[cite:498][cite:506]

To recreate the database from scratch, run:

```bash
docker compose down -v
docker compose up -d --build
```

This deletes the MySQL volume and reinitializes the database with the current `.env` values.[cite:498][cite:506]

## Troubleshooting

### Docker credential errors on Windows

If Docker fails to pull images with an error about credentials or a terminated logon session, inspect `%USERPROFILE%\\.docker\\config.json` and check whether a credential store entry such as `wincred` or `desktop` is causing the issue. Removing the stale credential-store setting and logging in again can resolve this kind of Windows Docker authentication problem.[cite:347][cite:348][cite:352]

### `bash\r` error during container startup

If the API container exits with `/usr/bin/env: 'bash\r': No such file or directory`, convert the shell script to Unix LF line endings before rebuilding the image. This is a Windows-to-Linux line-ending issue.[cite:399][cite:405]

### MySQL access denied

If MySQL rejects the expected credentials, verify the environment values used by the container:

```bash
docker inspect autodfbench-mysql --format '{{range .Config.Env}}{{println .}}{{end}}'
```

If those values are correct but login still fails, the existing database volume likely contains older credentials and should be recreated if data loss is acceptable.[cite:498][cite:500][cite:506]

### API returns no ground-truth rows

If the API responds with an error such as `Invalid test case or no GT rows for cftt_task='string_search'`, the application is reachable but the benchmark database is missing the needed test-case rows. Confirm the database contents directly inside MySQL with `SHOW DATABASES`, `SHOW TABLES`, and targeted `SELECT` queries.[cite:513][cite:518]
