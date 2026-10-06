# autodfbench/database.py
"""
SQLite storage for AutoDFBench.

Two files:
  - ground truth  (read-only):  ground_truth/autodfbench_gt.sqlite env AUTODFBENCH_GT_DB
  - results       (writable):   results/autodfbench_results.sqlite env AUTODFBENCH_RESULTS_DB

get_db_connection() opens the results database and attaches the ground-truth database read-only,
so existing queries keep working unchanged: `SELECT ... FROM ground_truth` reads the ground truth,
`INSERT INTO test_results` writes a result. The connection accepts the MySQL-style `%s`
placeholders used throughout the code base and `cursor(dictionary=True)`.
"""
import os
import sqlite3
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()  # settings may come from a .env file (see .env.example)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GT_DB = Path(os.getenv("AUTODFBENCH_GT_DB", PROJECT_ROOT / "ground_truth" / "autodfbench_gt.sqlite"))
RESULTS_DB = Path(os.getenv("AUTODFBENCH_RESULTS_DB", PROJECT_ROOT / "results" / "autodfbench_results.sqlite"))

Error = sqlite3.Error

RESULTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS test_results (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    base_test_case TEXT,
    testCase       TEXT,
    job_id         TEXT,
    TP             INTEGER,
    FP             INTEGER,
    FN             INTEGER,
    "precision"    REAL,
    "recall"       REAL,
    F1             REAL,
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


class _Cursor:
    def __init__(self, cur, dictionary):
        self._cur = cur
        self._dict = dictionary

    def execute(self, sql, params=()):
        self._cur.execute(sql.replace("%s", "?"), tuple(params or ()))
        return self

    def _row(self, r):
        if r is None or not self._dict:
            return r
        return {d[0]: v for d, v in zip(self._cur.description, r)}

    def fetchall(self):
        return [self._row(r) for r in self._cur.fetchall()]

    def fetchone(self):
        return self._row(self._cur.fetchone())

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    def close(self):
        self._cur.close()


class _Connection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, dictionary=False, **_):
        return _Cursor(self._conn.cursor(), dictionary)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _uri(path, mode):
    return f"file:{quote(str(path))}?mode={mode}"


def get_db_connection():
    """Results DB (writable) with the ground truth attached read-only. None if the GT file is missing."""
    if not GT_DB.is_file():
        print(f"[DB] Ground-truth database not found: {GT_DB}")
        return None
    RESULTS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_uri(RESULTS_DB, "rwc"), uri=True, timeout=30)
    conn.execute(RESULTS_SCHEMA)
    conn.execute("ATTACH DATABASE ? AS gt", (_uri(GT_DB, "ro"),))
    return _Connection(conn)
