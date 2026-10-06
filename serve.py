#!/usr/bin/env python3
"""
Start all AutoDFBench evaluation APIs.

    python serve.py                 # ports 8000-8004
    python serve.py --base-port 9000

  string search           base+0   /api/v1/string-search/evaluate
  deleted file recovery   base+1   /api/v1/deleted_file_recovery/evaluate
  file carving            base+2
  windows registry        base+3
  sqlite recovery         base+4

Each API runs as its own process (the same modules as before, started with API_PORT set).
If one exits, it is restarted. Ctrl+C / SIGTERM stops all of them.
"""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

APIS = [
    ("string_search", "API.string_search_api"),
    ("deleted_file_recovery", "API.deleted_file_recovery_api"),
    ("file_carving", "API.file_carving_api"),
    ("windows_registry", "API.windows_registry_api"),
    ("sqlite_recovery", "API.sqlite_recovery_api"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-port", type=int, default=int(os.getenv("AUTODFBENCH_BASE_PORT", 8000)))
    args = ap.parse_args()

    from autodfbench.database import GT_DB
    if not GT_DB.is_file():
        sys.exit(f"Ground-truth database not found: {GT_DB}")

    def start(i, module):
        env = dict(os.environ, API_PORT=str(args.base_port + i), PYTHONUNBUFFERED="1")
        return subprocess.Popen([sys.executable, "-m", module], cwd=ROOT, env=env)

    procs = {name: start(i, module) for i, (name, module) in enumerate(APIS)}
    for i, (name, _) in enumerate(APIS):
        print(f"[serve] {name:<22} http://localhost:{args.base_port + i}", flush=True)

    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while not stopping:
        time.sleep(1)
        for i, (name, module) in enumerate(APIS):
            code = procs[name].poll()
            if code is not None and not stopping:
                print(f"[serve] {name} exited with {code}; restarting", flush=True)
                time.sleep(2)
                procs[name] = start(i, module)

    for p in procs.values():
        p.terminate()
    for p in procs.values():
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()


if __name__ == "__main__":
    main()
