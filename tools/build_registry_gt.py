#!/usr/bin/env python3
"""
Build Windows registry ground-truth CSVs from the NIST CFReDS registry hives with Regipy.

Only maintainers need this. It writes the CSV format of the original ground truth (Data/windows_registry,
used for the AutoDFBench 1.0 paper): one KEY row per registry key, path style "/A/B", empty VALUE,
plus the FILE_INFO and PROCESSING_SUMMARY rows.

The walk differs from the one behind the original set in two ways:
  - each key node is listed once, so a subkey list pointing back up the tree (MR-08) is not followed again;
  - the walk stops 512 levels below the root key (the documented Windows limit for registry tree depth),
    so the very deep chain in NR-03-3 has a defined cut-off instead of stopping at Python's recursion limit.
For hives without loops or chains deeper than 512 levels the output is identical to the original set.

By default it builds the files of ground-truth set 1.1 (the files that differ from set 1.0) into
Data/windows_registry_v1.1:

    pip install regipy
    python tools/build_registry_gt.py --hives /path/to/win_REG

--hives is the folder of the CFReDS "Windows Registry" data set (with ugrd-nr, ugrd-nrd, ugrd-mr, ugrd-cr).
"""
import argparse
import csv
import os
import sys
from pathlib import Path

from regipy.registry import NKRecord, RegistryHive
from regipy.utils import convert_wintime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from autodfbench.registry_gt_sets import GT_SETS  # noqa: E402

MAX_DEPTH = 512

# Regipy does not keep a key node's offset; record it so revisits (loops) can be detected
_nk_init = NKRecord.__init__


def _nk_init_with_offset(self, cell, stream):
    _nk_init(self, cell, stream)
    self.cell_offset = cell.offset


NKRecord.__init__ = _nk_init_with_offset


def walk_keys(hive, max_depth=MAX_DEPTH):
    """(path, mtime) for every key reachable from the root key: depth first, each key node once,
    at most max_depth levels below the root. Also returns how often a loop or the depth limit was hit."""
    rows, stats = [], {"revisits": 0, "truncated": 0}
    stack = [(hive.root, "/", 0)]
    seen = set()
    while stack:
        nk, path, depth = stack.pop()
        if nk.cell_offset in seen:
            stats["revisits"] += 1
            continue
        seen.add(nk.cell_offset)
        rows.append((path, str(convert_wintime(nk.header.last_modified, as_json=False))))
        if not nk.subkey_count:
            continue
        if depth >= max_depth:
            stats["truncated"] += 1
            continue
        children = [s for s in nk.iter_subkeys() if isinstance(s, NKRecord)]
        prefix = "" if path == "/" else path
        for child in reversed(children):
            stack.append((child, f"{prefix}/{child.name}", depth + 1))
    return rows, stats


def build_csv(hive_path, out_path, max_depth=MAX_DEPTH):
    hive_path = Path(hive_path)
    rows, stats = walk_keys(RegistryHive(str(hive_path)), max_depth)
    tmp = Path(str(out_path) + ".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)  # default \r\n line endings, as in the 1.0 files
        w.writerow(["PATH", "TYPE", "VALUE", "MTIME"])
        w.writerow([f"FILE_INFO: {hive_path.name}", "METADATA",
                    f"Size: {hive_path.stat().st_size} bytes, Processed with Regipy", ""])
        for path, mtime in rows:
            w.writerow([path, "KEY", "", mtime])
        w.writerow(["/PROCESSING_SUMMARY", "STATS", f"Keys: {len(rows)}, Values: 0", ""])
    os.replace(tmp, out_path)
    return len(rows), stats


def find_hive(hives_dir, name):
    """NIST hive file by exact name (names contain [ ], so no glob patterns)."""
    for dirpath, _, files in os.walk(hives_dir):
        if name in files:
            return Path(dirpath) / name
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hives", required=True, help="CFReDS Windows Registry data set folder (win_REG)")
    ap.add_argument("--set", default="1.1", choices=[s for s in GT_SETS if GT_SETS[s]["files"]],
                    help="ground-truth set to build (default 1.1)")
    ap.add_argument("--out", help="output folder (default Data/<folder of the set>)")
    ap.add_argument("--files", nargs="+", metavar="CSV",
                    help="build these ground-truth CSVs instead, e.g. '[nr]-02-1_v15.hive.csv'")
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else ROOT / "Data" / GT_SETS[args.set]["folder"]
    out_dir.mkdir(parents=True, exist_ok=True)
    names = args.files or sorted(GT_SETS[args.set]["files"])
    failed = 0
    for csv_name in names:
        hive = find_hive(args.hives, csv_name[:-len(".csv")])
        if hive is None:
            print(f"{csv_name}: hive not found under {args.hives}", file=sys.stderr)
            failed += 1
            continue
        try:
            n, stats = build_csv(hive, out_dir / csv_name)
        except Exception as e:
            print(f"{csv_name}: Regipy cannot parse the hive ({type(e).__name__}: {e}); no CSV written",
                  file=sys.stderr)
            Path(str(out_dir / csv_name) + ".tmp").unlink(missing_ok=True)
            failed += 1
            continue
        notes = []
        if stats["revisits"]:
            notes.append(f"{stats['revisits']} subkey reference(s) to an already listed key not followed")
        if stats["truncated"]:
            notes.append(f"stopped at {MAX_DEPTH} levels below the root")
        print(f"{csv_name}: {n} keys" + (f" ({'; '.join(notes)})" if notes else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
