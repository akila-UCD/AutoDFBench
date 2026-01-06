#!/usr/bin/env python3
# sectors_to_blocks_update_gt.py
# Compute FS-relative block/cluster numbers from absolute sector ranges,
# print ONLY the list to stdout, and update ground_truth.dfr_blocks.

import argparse, math, re, sys
from functools import reduce
from math import gcd
from typing import List, Tuple, Set
from pathlib import Path
import mysql.connector

# ---------- Defaults (override via CLI if needed) ----------
DB_HOST = "172.20.0.2"
DB_PORT = 3306
DB_NAME = "DFLLM"
DB_USER = "root"
DB_PASS = "root"

SECTOR_SIZE = 512
COMMON_SIZES = [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]
# Preference order when everything else ties (typical FS choices first)
PREF_ORDER   = [4096, 2048, 1024, 8192, 16384, 32768, 65536, 512]

# ---------- Parsing ----------
def parse_ranges(ranges_text: str) -> List[Tuple[int, int]]:
    if not ranges_text:
        return []
    out: List[Tuple[int, int]] = []
    for s, e in re.findall(r'(\d+)\s*-\s*(\d+)', ranges_text):
        s_i, e_i = int(s), int(e)
        if e_i < s_i:
            s_i, e_i = e_i, s_i
        out.append((s_i, e_i))
    # Add singletons not covered by any S-E
    for n in re.findall(r'\b(\d+)\b', ranges_text):
        ni = int(n)
        if any(s <= ni <= e for s, e in out):
            continue
        out.append((ni, ni))
    return sorted(set(out))

def total_sectors(ranges: List[Tuple[int,int]]) -> int:
    return sum(e - s + 1 for s, e in ranges)

def gcd_run_len_in_sectors(ranges: List[Tuple[int,int]]) -> int:
    lens = [e - s + 1 for s, e in ranges]
    return reduce(gcd, lens) if lens else 0

# ---------- Math ----------
def expected_blocks_from_size(file_size: int, block_size: int) -> int:
    return 0 if file_size <= 0 else math.ceil(file_size / block_size)

def sectors_to_blocks(
    ranges: List[Tuple[int,int]],
    part_start: int,
    block_size: int
) -> List[int]:
    spb = block_size // SECTOR_SIZE
    if spb <= 0 or block_size % SECTOR_SIZE != 0:
        raise ValueError(f"Invalid block size {block_size}; must be a multiple of {SECTOR_SIZE}.")
    blocks: Set[int] = set()
    for s, e in ranges:
        sb = (s - part_start) // spb
        eb = (e - part_start) // spb
        for b in range(sb, eb + 1):
            blocks.add(b)
    return sorted(blocks)

def infer_block_size(
    ranges: List[Tuple[int,int]],
    part_start: int,
    file_size: int
) -> Tuple[int, List[int]]:
    """
    Robust inference: favour (1) count match vs ceil(size/bs),
    (2) aligned starts, (3) minimal over-coverage, (4) common sizes, (5) smaller bs.
    """
    S = total_sectors(ranges)
    gcd_sec = gcd_run_len_in_sectors(ranges)
    gcd_hint = gcd_sec * SECTOR_SIZE if gcd_sec else None

    scored = []
    for bs in COMMON_SIZES:
        try:
            blocks = sectors_to_blocks(ranges, part_start, bs)
        except Exception:
            continue

        block_count = len(blocks)
        exp = expected_blocks_from_size(file_size, bs)
        ok = (block_count == exp)

        spb = bs // SECTOR_SIZE
        aligned = all(((s - part_start) % spb) == 0 for (s, _) in ranges)
        over_cov = max(0, block_count * spb - S)

        pref_rank = PREF_ORDER.index(bs) if bs in PREF_ORDER else len(PREF_ORDER)

        score = (0 if ok else 1,
                 0 if aligned else 1,
                 over_cov,
                 pref_rank,
                 bs)  # final tie-break prefers smaller bs

        if gcd_hint and bs == gcd_hint:
            score = (score[0], score[1], max(0, score[2]-1), score[3], score[4])

        scored.append((score, bs, blocks, exp))

    if not scored:
        return 0, []

    scored.sort(key=lambda t: t[0])
    best_score, best_bs, _, _ = scored[0]
    best_list = [bs for (sc, bs, _, _) in scored if sc == best_score]
    return best_bs, sorted(set(best_list))

# ---------- DB ----------
def db_connect(host, port, name, user, passwd):
    return mysql.connector.connect(
        host=host, port=port, database=name, user=user, password=passwd, autocommit=False
    )

def update_ground_truth_blocks(
    host, port, name, user, passwd,
    base_test_case: str, filename: str, blocks_csv: str, update_all_matches: bool=False
) -> Tuple[int,int,int]:
    """
    Update ground_truth.dfr_blocks for rows matching base_test_case and file_name.
    Preference: exact match on basename (case-insensitive), else longest partial match.
    Returns (updated, unchanged, not_found).
    """
    base = Path(filename).name
    base_l = base.lower()

    sql_find = """
        SELECT id, file_name, dfr_blocks
          FROM ground_truth
         WHERE base_test_case = %s
           AND (LOWER(file_name) = %s OR LOWER(file_name) LIKE CONCAT('%', %s, '%'))
         ORDER BY (LOWER(file_name) = %s) DESC, LENGTH(file_name) DESC
    """

    conn = db_connect(host, port, name, user, passwd)
    upd = 0; same = 0; miss = 0
    try:
        with conn.cursor() as cur:
            cur.execute(sql_find, (base_test_case, base_l, base_l, base_l))
            rows = cur.fetchall()

        if not rows:
            miss += 1
        else:
            target_rows = rows if update_all_matches else rows[:1]
            with conn.cursor() as cur:
                for (row_id, file_name, current) in target_rows:
                    if (current or "") == (blocks_csv or ""):
                        same += 1
                        continue
                    cur.execute("UPDATE ground_truth SET dfr_blocks = %s WHERE id = %s",
                                (blocks_csv, row_id))
                    upd += 1
            conn.commit()
    finally:
        conn.close()
    return upd, same, miss

# ---------- CLI / Main ----------
def main():
    ap = argparse.ArgumentParser(
        description="Print ONLY FS-relative blocks from absolute sector ranges and update ground_truth.dfr_blocks."
    )
    ap.add_argument("--filename", required=True, help="Filename to match in ground_truth.file_name (basename is used)")
    ap.add_argument("--base-test-case", required=True, help="ground_truth.base_test_case")
    ap.add_argument("--part-start", type=int, required=True, help="Partition start sector (from mmls)")
    ap.add_argument("--ranges", required=True, help="Absolute sector ranges, e.g. '204-211, 220 - 227'")
    ap.add_argument("--file-size", type=int, required=True, help="File size in bytes (for block-size inference)")
    ap.add_argument("--block-size", type=int, default=0, help="Filesystem block/cluster size; if 0, infer it")

    ap.add_argument("--no-update", action="store_true", help="Do NOT write to DB; just print blocks")
    ap.add_argument("--update-all-matches", action="store_true", help="If multiple rows match filename, update all")

    # DB overrides
    ap.add_argument("--db-host", default=DB_HOST)
    ap.add_argument("--db-port", type=int, default=DB_PORT)
    ap.add_argument("--db-name", default=DB_NAME)
    ap.add_argument("--db-user", default=DB_USER)
    ap.add_argument("--db-pass", default=DB_PASS)

    args = ap.parse_args()

    # If file size is zero, output empty list and (optionally) clear DB field.
    if args.file_size <= 0:
        blocks = []
    else:
        ranges = parse_ranges(args.ranges)
        if not ranges:
            print("[]")
            return

        bs = args.block_size
        if bs <= 0:
            bs, _cands = infer_block_size(ranges, args.part_start, args.file_size)
            if not bs:
                print("[]")
                return

        blocks = sectors_to_blocks(ranges, args.part_start, bs)

    # Print ONLY the blocks list to stdout
    print(f"{blocks}")

    # Update DB (CSV with spaces: "12, 13, 14")
    if not args.no_update:
        csv_val = ", ".join(str(b) for b in blocks)
        _u, _s, _m = update_ground_truth_blocks(
            args.db_host, args.db_port, args.db_name, args.db_user, args.db_pass,
            args.base_test_case, args.filename, csv_val,
            update_all_matches=args.update_all_matches
        )

if __name__ == "__main__":
    main()
