# autodfbench/db_sqlite_recovery.py
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Ensure project root is on sys.path so `modules.*` can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../AutoDFBench
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.database import get_ground_truth  # noqa: E402

__all__ = ["get_ground_truth"]
