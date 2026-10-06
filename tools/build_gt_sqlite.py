#!/usr/bin/env python3
"""
Build ground_truth/autodfbench_gt.sqlite (the database the APIs read) from a MySQL AutoDFBench database.

Only maintainers need this, after changing the ground truth in MySQL. Users get the SQLite file with the repo.

    pip install mysql-connector-python
    python tools/build_gt_sqlite.py --host 127.0.0.1 --port 3307 --user root --database autodfbench

The password is read from the DB_PASSWORD environment variable (or prompted for).
Copied tables: ground_truth (all rows) and config (types only; values are blanked because they hold
local paths and model endpoints). Text columns use COLLATE NOCASE to match MySQL's case-insensitive
utf16_general_ci comparisons.
"""
import argparse
import getpass
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "ground_truth" / "autodfbench_gt.sqlite"

GROUND_TRUTH_COLUMNS = [
    ("id", "INTEGER PRIMARY KEY"),
    ("base_test_case", "TEXT NOT NULL COLLATE NOCASE"),
    ("file_line", "TEXT COLLATE NOCASE"),
    ("type", "TEXT COLLATE NOCASE"),
    ("os", "TEXT COLLATE NOCASE"),
    ("cftt_task", "TEXT COLLATE NOCASE"),
    ("file_name", "TEXT COLLATE NOCASE"),
    ("size", "INTEGER"),
    ("access_time_stamp", "TEXT COLLATE NOCASE"),
    ("modify_time_stamp", "TEXT COLLATE NOCASE"),
    ("change_time_stamp", "TEXT COLLATE NOCASE"),
    ("deleted_time_stamp", "TEXT COLLATE NOCASE"),
    ("block_count", "INTEGER"),
    ("dfr_blocks", "TEXT COLLATE NOCASE"),
    ("file_hash", "TEXT COLLATE NOCASE"),
    ("carve_types", "TEXT COLLATE NOCASE"),
    ("carve_blocks", "INTEGER"),
    ("carve_spill", "INTEGER"),
    ("gt_file", "TEXT COLLATE NOCASE"),
    ("page_size", "INTEGER"),
    ("journal_mode", "TEXT COLLATE NOCASE"),
    ("number_of_pages", "INTEGER"),
    ("encoding", "TEXT COLLATE NOCASE"),
    ("sqlite_md5_hash", "TEXT COLLATE NOCASE"),
    ("sqlite_sha1_hash", "TEXT COLLATE NOCASE"),
    ("sqlite_table_name", "TEXT COLLATE NOCASE"),
    ("sqlite_column", "TEXT COLLATE NOCASE"),
    ("sqlite_number_of_rows", "INTEGER"),
    ("sqlite_cmd", "TEXT COLLATE NOCASE"),
]


def build(mysql_conn, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)

    names = [c for c, _ in GROUND_TRUTH_COLUMNS]
    quoted = ", ".join(f"`{c}`" for c in names)
    src = mysql_conn.cursor()
    src.execute(f"SELECT {quoted} FROM ground_truth ORDER BY id")
    gt_rows = src.fetchall()
    src.execute("SELECT id, `type` FROM config ORDER BY id")
    config_rows = [(i, t, "") for i, t in src.fetchall()]
    src.close()

    db = sqlite3.connect(tmp)
    cols = ",\n    ".join(f'"{c}" {t}' for c, t in GROUND_TRUTH_COLUMNS)
    db.executescript(f"""
CREATE TABLE ground_truth (
    {cols}
);
CREATE TABLE config (
    id    INTEGER PRIMARY KEY,
    type  TEXT NOT NULL COLLATE NOCASE,
    value TEXT NOT NULL
);
""")
    db.executemany(f"INSERT INTO ground_truth VALUES ({', '.join('?' * len(names))})", gt_rows)
    db.executemany("INSERT INTO config VALUES (?, ?, ?)", config_rows)
    db.executescript("""
CREATE INDEX idx_gt_task_case ON ground_truth (cftt_task, base_test_case);
CREATE INDEX idx_gt_case ON ground_truth (base_test_case);
""")
    db.commit()
    db.execute("VACUUM")
    db.close()
    os.replace(tmp, out_path)
    return len(gt_rows), len(config_rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=3306)
    ap.add_argument("--user", default="root")
    ap.add_argument("--database", default="autodfbench")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    try:
        import mysql.connector
    except ImportError:
        sys.exit("mysql-connector-python is required: pip install mysql-connector-python")

    password = os.getenv("DB_PASSWORD") or getpass.getpass("MySQL password: ")
    conn = mysql.connector.connect(host=args.host, port=args.port, user=args.user,
                                   password=password, database=args.database)
    n_gt, n_cfg = build(conn, args.out)
    conn.close()

    sha = hashlib.sha256(args.out.read_bytes()).hexdigest()
    args.out.with_name(args.out.name + ".sha256").write_text(f"{sha}  {args.out.name}\n")
    print(f"{args.out}: {n_gt} ground_truth rows, {n_cfg} config rows, sha256 {sha}")


if __name__ == "__main__":
    main()
