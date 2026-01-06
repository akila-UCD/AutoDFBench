#!/usr/bin/env python3
# fs_blocks_from_sector_ranges.py
# Compute filesystem units (blocks/clusters) and FS-relative sectors from absolute sector ranges.
# Also print istat-like output (EXT Direct Blocks / NTFS Clusters / FAT Clusters) WITHOUT calling istat.

import argparse, re, sys, json, math, subprocess
from pathlib import Path
import mysql.connector

# -------------------- DB config --------------------
DB_HOST = "172.20.0.2"
DB_PORT = 3306
DB_NAME = "DFLLM"
DB_USER = "root"
DB_PASS = "root"

DEFAULT_TASK = "deleted_file_recovery"
SECTOR_SIZE = 512

# Candidate FS unit sizes (bytes) and preference order (when all else ties)
COMMON_SIZES = [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]
PREF_ORDER   = [4096, 2048, 1024, 8192, 16384, 32768, 65536, 512]

# -------------------- shell helpers --------------------
def run(cmd, quiet_stderr=True):
    return subprocess.run(
        cmd, text=True, stdout=subprocess.PIPE,
        stderr=(subprocess.DEVNULL if quiet_stderr else subprocess.PIPE),
        check=True
    ).stdout

# -------------------- mmls / fsstat --------------------
_MMLS_ROW = re.compile(r"^\s*(\d+):\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.+)$")

def parse_mmls(image):
    """Return list of partitions: [{'slot':int,'start':int,'end':int,'desc':str}]"""
    try:
        txt = run(["mmls", image])
    except Exception:
        txt = ""
    parts = []
    for line in txt.splitlines():
        m = _MMLS_ROW.match(line)
        if not m:
            continue
        slot = int(m.group(1)); start = int(m.group(3)); end = int(m.group(4))
        desc = m.group(6).strip().lower()
        if "unallocated" in desc or "metadata" in desc:
            continue
        parts.append({"slot": slot, "start": start, "end": end, "desc": desc})
    if not parts:
        parts = [{"slot": 0, "start": 0, "end": 10**18, "desc": "raw"}]
    parts.sort(key=lambda p: p["start"])
    return parts

def fsstat_info(image, part_start):
    """Return (fs_type, unit_size_bytes, sectors_per_unit)."""
    txt = run(["fsstat", "-o", str(part_start), image])
    fs_type_m = re.search(r"File System Type:\s*(.+)", txt)
    fs_type = (fs_type_m.group(1).strip().lower() if fs_type_m else "unknown")

    sec_size_m = re.search(r"Sector Size:\s*(\d+)", txt)
    sector_size = int(sec_size_m.group(1)) if sec_size_m else SECTOR_SIZE

    unit_size = None
    if "ntfs" in fs_type:
        m = re.search(r"Cluster Size:\s*(\d+)", txt); unit_size = int(m.group(1)) if m else None
    elif "fat" in fs_type:
        m_spc = re.search(r"Sectors Per Cluster:\s*(\d+)", txt)
        if m_spc: unit_size = int(m_spc.group(1)) * sector_size
        else:
            m = re.search(r"Cluster Size:\s*(\d+)", txt); unit_size = int(m.group(1)) if m else None
    else:  # ext*
        m = re.search(r"Block Size:\s*(\d+)", txt); unit_size = int(m.group(1)) if m else None

    if not unit_size:
        raise RuntimeError(f"fsstat could not determine unit size for offset {part_start}")
    return fs_type, unit_size, max(1, unit_size // sector_size)

# -------------------- parsing + math --------------------
def parse_ranges(text):
    """Accept 'S-E, S2 - E2' and singletons 'N' (as N-N). Return sorted unique [(s,e)]."""
    if not text:
        return []
    out = []
    for s,e in re.findall(r"(\d+)\s*-\s*(\d+)", text):
        s, e = int(s), int(e)
        if e < s: s,e = e,s
        out.append((s,e))
    # add singletons not inside any of the S-E ranges
    for n in re.findall(r"\b(\d+)\b", text):
        ni = int(n)
        if any(s <= ni <= e for s,e in out):
            continue
        out.append((ni,ni))
    # unique + sorted
    out = sorted(set(out))
    return out

def pick_partition(parts, ranges):
    smin = min(s for s,_ in ranges); smax = max(e for _,e in ranges)
    for p in parts:
        if p["start"] <= smin and smax <= p["end"]:
            return p
    for p in parts:
        if p["start"] <= smin <= p["end"]:
            return p
    return None

def total_sectors(ranges):
    return sum(e - s + 1 for s, e in ranges)

def expected_units_from_size(file_size, unit_size):
    return 0 if (not file_size or file_size <= 0) else math.ceil(file_size / unit_size)

def sectors_to_units(ranges, part_start, sectors_per_unit):
    """Absolute sector ranges → filesystem unit indices (relative to the FS)."""
    units = set()
    spu = max(1, int(sectors_per_unit))
    for s,e in ranges:
        sb = (s - part_start) // spu
        eb = (e - part_start) // spu
        for u in range(sb, eb+1):
            units.add(u)
    return sorted(units)

def fs_relative_sectors(ranges, part_start):
    """Absolute sector ranges → FS-relative sector numbers (sector - part_start)."""
    rel = []
    for s,e in ranges:
        for sec in range(s, e+1):
            rel.append(sec - part_start)
    return sorted(set(rel))

def compress_ranges(nums):
    """[1,2,3,7,9,10] -> '1-3,7,9-10'"""
    if not nums: return ""
    nums = sorted(nums)
    res = []; a = b = nums[0]
    for x in nums[1:]:
        if x == b + 1: b = x; continue
        res.append((a,b)); a = b = x
    res.append((a,b))
    return ",".join(f"{x}-{y}" if x!=y else f"{x}" for x,y in res)

def format_csv(nums, spaced=True):
    """Format as CSV '76, 77, 78, ...' (spaced=True) or '76,77,78'."""
    sep = ", " if spaced else ","
    return sep.join(str(n) for n in nums)

# -------------------- Robust unit-size inference (alignment + over-coverage) --------------------
def infer_unit_size_by_mapping(ranges, part_start, file_size=None, *,
                               sector_size=SECTOR_SIZE,
                               candidates=COMMON_SIZES,
                               pref_order=PREF_ORDER,
                               debug=False):
    """
    Try each candidate unit size:
      - Map sectors→units and count unique units.
      - ok := (#units == ceil(file_size/bs)) if file_size known.
      - aligned_starts := all ((s - part_start) % sectors_per_unit == 0).
      - over_coverage := #units * sectors_per_unit - total_sectors.
    Score tuple (lower is better):
      (not ok, not aligned, over_coverage, pref_rank, bs)
    """
    S = total_sectors(ranges)
    scored = []
    for bs in candidates:
        spu = max(1, bs // sector_size)
        # Map ranges to unit indices
        units = sectors_to_units(ranges, part_start, spu)
        cnt = len(units)
        exp = expected_units_from_size(file_size, bs) if file_size else None
        ok  = (exp is not None and cnt == exp)

        aligned = all(((s - part_start) % spu) == 0 for (s, _) in ranges)
        over_cov = max(0, cnt * spu - S)

        pref_rank = pref_order.index(bs) if bs in pref_order else len(pref_order)

        score = (0 if ok else 1,
                 0 if aligned else 1,
                 over_cov,
                 pref_rank,
                 bs)  # final tie-break prefers smaller bs

        scored.append((score, bs, spu, units, cnt, exp, aligned, over_cov))

    if not scored:
        return 0, 0, []  # (unit_size, sectors_per_unit, candidates)

    scored.sort(key=lambda t: t[0])
    best = scored[0]
    best_bs, best_spu, best_units, best_cnt, best_exp, best_aligned, best_over = \
        best[1], best[2], best[3], best[4], best[5], best[6], best[7]

    # Collect all equal-top candidates for reporting
    top_score = scored[0][0]
    top_list = sorted({bs for (sc, bs, *_rest) in scored if sc == top_score})

    if debug:
        sys.stderr.write(f"[infer] picked unit_size={best_bs} (spu={best_spu}) "
                         f"cnt={best_cnt} exp={best_exp} aligned={best_aligned} over={best_over}; "
                         f"candidates={top_list}\n")
    return best_bs, best_spu, top_list

# -------------------- DB helpers (diagnostic) --------------------
def db_connect():
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS, autocommit=False
    )

def fetch_file_size(base_test_case, cftt_task, filename_like, debug=False):
    sql = """
        SELECT size
          FROM ground_truth
         WHERE base_test_case = %s
           AND cftt_task      = %s
           AND LOWER(file_name) LIKE CONCAT('%', %s, '%')
         ORDER BY LENGTH(file_name) DESC
         LIMIT 1
    """
    conn = db_connect(); cur = conn.cursor()
    try:
        cur.execute(sql, (base_test_case, cftt_task, filename_like.lower()))
        row = cur.fetchone()
        if debug: sys.stderr.write(f"[DB] size for {filename_like} -> {row}\n")
        return int(row[0]) if row and row[0] is not None else 0
    finally:
        cur.close(); conn.close()

def _find_gt_rows(conn, base_test_case, cftt_task, filename_like, debug=False):
    sql = """
        SELECT id, file_name, dfr_blocks
          FROM ground_truth
         WHERE base_test_case = %s
           AND cftt_task      = %s
           AND (
                 LOWER(file_name) LIKE CONCAT('%', %s, '%')
              OR LOWER(file_name) LIKE CONCAT('%', %s, '%')
           )
    """
    base = Path(filename_like).name.lower()
    with conn.cursor() as cur:
        cur.execute(sql, (base_test_case, cftt_task, filename_like.lower(), base))
        rows = cur.fetchall()
        if debug:
            sys.stderr.write(f"[DB] matched {len(rows)} row(s) for '{filename_like}' in {base_test_case}/{cftt_task}\n")
            for r in rows[:10]:
                sys.stderr.write(f"     id={r[0]} file_name={r[1]} dfr_blocks={r[2]}\n")
        return rows

def update_blocks(base_test_case, cftt_task, filename_like, blocks_str,
                  *, update_all_matches=False, debug=False):
    conn = db_connect()
    upd = 0; same = 0; miss = 0
    try:
        rows = _find_gt_rows(conn, base_test_case, cftt_task, filename_like, debug=debug)
        if not rows:
            miss += 1
            if debug: sys.stderr.write(f"[DB] NO MATCH for '{filename_like}' in {base_test_case}/{cftt_task}\n")
        else:
            if not update_all_matches and len(rows) > 1:
                rows = sorted(rows, key=lambda r: len(r[1] or ""), reverse=True)[:1]
            with conn.cursor() as cur:
                for (row_id, file_name, current) in rows:
                    if (current or "") == (blocks_str or ""):
                        same += 1
                        if debug: sys.stderr.write(f"[DB] UNCHANGED id={row_id} name={file_name} (already {current})\n")
                        continue
                    cur.execute("UPDATE ground_truth SET dfr_blocks = %s WHERE id = %s",
                                (blocks_str, row_id))
                    if debug: sys.stderr.write(f"[DB] UPDATED  id={row_id} name={file_name} -> {blocks_str}\n")
                    upd += 1
        conn.commit()
    finally:
        conn.close()
    return upd, same, miss

# -------------------- istat-style formatting (NO istat calls) --------------------
def wrap_numbers(nums, per_line=16):
    lines = []
    for i in range(0, len(nums), per_line):
        lines.append(" ".join(str(n) for n in nums[i:i+per_line]))
    return "\n".join(lines)

def wrap_ranges_csv(ranges_csv, max_len=78):
    out, cur = [], ""
    for token in [t.strip() for t in ranges_csv.split(",") if t.strip()]:
        piece = (", " if cur else "") + token
        if len(cur) + len(piece) > max_len:
            out.append(cur)
            cur = token
        else:
            cur += piece
    if cur:
        out.append(cur)
    return "\n".join(out)

def fsstat_fat_params(image, part_start):
    """Return (sector_size, sectors_per_cluster, data_area_start_abs_sector)."""
    txt = run(["fsstat", "-o", str(part_start), image])
    def gi(pat, flags=re.I):
        m = re.search(pat, txt, flags)
        return int(m.group(1)) if m else None

    sector_size = gi(r"Sector Size:\s*(\d+)")
    spc         = gi(r"Sectors Per Cluster:\s*(\d+)")
    reserved    = gi(r"Reserved (?:Sector Count|Sectors):\s*(\d+)")
    nfats       = gi(r"Number of FATs:\s*(\d+)")
    fat_len     = gi(r"(?:Length|Size) of FAT:\s*(\d+)\s*sectors")
    root_ents   = gi(r"Root Directory Entries:\s*(\d+)")  # FAT12/16 only; FAT32 has root cluster instead

    if sector_size is None:
        sector_size = SECTOR_SIZE
    if None in (spc, reserved, nfats, fat_len):
        raise RuntimeError("fsstat did not provide enough FAT geometry (spc/reserved/nfats/fat_len).")

    # FAT12/16: fixed root directory region before data area; FAT32 root is in data area
    root_dir_secs = 0 if root_ents is None else ((root_ents * 32) + (sector_size - 1)) // sector_size

    data_area_start = part_start + reserved + (nfats * fat_len) + root_dir_secs
    return sector_size, spc, data_area_start

# -------------------- main --------------------
def main():
    ap = argparse.ArgumentParser(
        description="Compute FS units/sectors from absolute ranges; optionally print istat-like output without calling istat."
    )
    ap.add_argument("--image", required=True, help="Path to dd image")
    ap.add_argument("--base-test-case", required=True, help="ground_truth.base_test_case (to fetch file size)")
    ap.add_argument("--cftt-task", default=DEFAULT_TASK, help="ground_truth.cftt_task (default: deleted_file_recovery)")
    ap.add_argument("--filename", required=True, help="File name (used for DB lookup and reporting)")
    ap.add_argument("--ranges", required=True, help='Absolute sector ranges, e.g. "204-211, 220 - 227"')
    ap.add_argument("--part-start", type=int, default=None, help="Override partition start sector (optional)")
    ap.add_argument("--unit-mode", choices=["fs","sector","auto"], default="fs",
                    help="What to PRINT as 'blocks' in JSON. fs=blocks/clusters, sector=FS-relative sectors.")
    ap.add_argument("--store-mode", choices=["fs","sector"], default="sector",
                    help="What to WRITE to DB dfr_blocks (default: sector = FS-relative sectors).")
    ap.add_argument("--force-unit-size", type=int, default=0,
                    help="Override unit size in bytes (e.g., 512 to treat each sector as a unit).")
    ap.add_argument("--update-db", action="store_true", help="Write chosen value (--store-mode) to DB as CSV")
    ap.add_argument("--update-all-matches", action="store_true", help="If multiple rows match filename, update all")
    ap.add_argument("--istat-style", choices=["off", "ext", "ntfs", "fat"], default="off",
                    help="Print istat-like output WITHOUT calling istat (uses only --ranges and fsstat geometry).")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    # Parse ranges
    ranges = parse_ranges(args.ranges)
    if not ranges:
        sys.exit("No valid sector ranges provided.")

    # Partition selection
    if args.part_start is None:
        parts = parse_mmls(args.image)
        part = pick_partition(parts, ranges)
        if not part:
            sys.exit("Could not map sector ranges to any partition. Are these absolute sectors?")
        part_start = part["start"]
        if args.debug:
            sys.stderr.write(f"[i] partition: slot={part.get('slot')} start={part_start} desc={part.get('desc')}\n")
    else:
        part_start = args.part_start
        if args.debug:
            sys.stderr.write(f"[i] using override part_start={part_start}\n")

    # Get GT file size (for expectation check and inference scoring)
    gt_size = fetch_file_size(args.base_test_case, args.cftt_task, args.filename, debug=args.debug)

    # FS geometry → either forced, fsstat, or robust inference fallback
    unit_size_source = "fsstat"
    candidates_used = []

    if args.force_unit_size > 0:
        fs_type = "forced"
        unit_size = args.force_unit_size
        sectors_per_unit = max(1, unit_size // SECTOR_SIZE)
        unit_size_source = "forced"
        if args.debug:
            sys.stderr.write(f"[i] FORCED unit_size={unit_size} sectors_per_unit={sectors_per_unit}\n")
    else:
        # Try fsstat first
        try:
            fs_type, unit_size, sectors_per_unit = fsstat_info(args.image, part_start)
            if args.debug:
                sys.stderr.write(f"[i] fs_type={fs_type} unit_size={unit_size}B sectors_per_unit={sectors_per_unit}\n")
        except Exception as ex:
            if args.debug:
                sys.stderr.write(f"[!] fsstat failed: {ex}\n")
            fs_type = "unknown"
            unit_size = 0
            sectors_per_unit = 0

        need_infer = False
        if unit_size <= 0 or sectors_per_unit <= 0:
            need_infer = True
            if args.debug:
                sys.stderr.write("[!] fsstat did not yield valid unit size; inferring via mapping\n")
        else:
            # Validate fsstat geometry quickly: check alignment + over-coverage + size-consistency
            units_fsstat = sectors_to_units(ranges, part_start, sectors_per_unit)
            exp_units = expected_units_from_size(gt_size, unit_size) if gt_size else None
            ok_count = (exp_units is not None and len(units_fsstat) == exp_units)
            aligned = all(((s - part_start) % sectors_per_unit) == 0 for (s, _) in ranges)
            over_cov = max(0, len(units_fsstat) * sectors_per_unit - total_sectors(ranges))

            if args.debug:
                sys.stderr.write(f"[chk] fsstat units={len(units_fsstat)} exp={exp_units} "
                                 f"aligned={aligned} over_cov={over_cov}\n")

            if (exp_units is not None and not ok_count) or (not aligned) or (over_cov > 64):
                need_infer = True
                if args.debug:
                    sys.stderr.write("[!] fsstat geometry looks inconsistent; trying inference\n")

        if need_infer:
            inferred_bs, inferred_spu, cand = infer_unit_size_by_mapping(
                ranges, part_start, file_size=gt_size, debug=args.debug
            )
            if inferred_bs > 0 and inferred_spu > 0:
                unit_size, sectors_per_unit = inferred_bs, inferred_spu
                unit_size_source = "inferred"
                candidates_used = cand
            else:
                unit_size, sectors_per_unit = SECTOR_SIZE, 1
                unit_size_source = "fallback_sector"
                if args.debug:
                    sys.stderr.write("[!] inference failed; falling back to 1 sector per unit\n")

    # Compute both views
    rel_secs = fs_relative_sectors(ranges, part_start)
    fs_units = sectors_to_units(ranges, part_start, sectors_per_unit)

    # ---- istat-style textual output (no istat calls) ----
    if args.istat_style != "off":
        spu = max(1, int(sectors_per_unit))
        if args.istat_style == "ext":
            # EXT: Direct Blocks only (metadata Indirect/Double/Triple require inode parsing and are not derivable from ranges)
            print("Direct Blocks:")
            print(wrap_numbers(fs_units))
            print("\nIndirect Blocks:\n")
            print("Double Indirect Blocks:\n")
            print("Triple Indirect Blocks:")
            return

        if args.istat_style == "ntfs":
            # NTFS: Clusters are FS-relative cluster indices; fs_units already match
            clusters_csv = compress_ranges(fs_units)
            print("Clusters:")
            print(wrap_ranges_csv(clusters_csv))
            return

        if args.istat_style == "fat":
            # FAT: Convert units -> 2-based cluster numbers using data-area start from fsstat
            sector_size, spc, data_start_abs = fsstat_fat_params(args.image, part_start)
            # sectors_per_unit (spu) should equal spc for FAT; we still compute generally
            data_units_start = (data_start_abs - part_start) // spu  # unit index at which Cluster 2 begins
            clusters = [2 + (u - data_units_start) for u in fs_units]
            clusters_csv = compress_ranges(clusters)
            print("Clusters:")
            print(wrap_ranges_csv(clusters_csv))
            return

    # If unit-mode 'auto': pick whichever matches GT size (if known), else prefer fs units
    if args.unit_mode == "auto":
        exp_fs = expected_units_from_size(gt_size, unit_size) if gt_size else None
        if exp_fs is not None and exp_fs == len(fs_units):
            unit_mode_effective = "fs"
        else:
            unit_mode_effective = "sector"
    else:
        unit_mode_effective = args.unit_mode

    # Choose what to PRINT in JSON as "blocks"
    if unit_mode_effective == "sector":
        blocks_list = rel_secs
        block_unit_name = "fs-relative-sector"
        effective_unit_size = SECTOR_SIZE
    else:  # fs
        blocks_list = fs_units
        block_unit_name = "fs-unit"  # ext block or FAT/NTFS cluster
        effective_unit_size = unit_size

    # Choose what to STORE to DB (CSV) — store compressed ranges for readability/size
    store_list = blocks_list
    store_csv  = format_csv(store_list, spaced=True)

    blocks_ranges_printed = compress_ranges(blocks_list)

    # ground_truth.size for expectation check (applies to what you PRINT)
    expected_units = expected_units_from_size(gt_size, effective_unit_size) if (gt_size and effective_unit_size) else None
    match = (expected_units == len(blocks_list)) if expected_units is not None else None

    # Emit JSON
    result = {
        "filename": args.filename,
        "base_test_case": args.base_test_case,
        "cftt_task": args.cftt_task,
        "partition_start": part_start,
        "fs_type": fs_type,
        "unit_size_source": unit_size_source,
        "inference_candidates": candidates_used or "NA",
        "print_mode": unit_mode_effective,
        "store_mode": args.store_mode,
        "unit_name_printed": block_unit_name,
        "unit_size_printed_bytes": effective_unit_size,
        "sector_ranges_abs": ranges,
        "blocks_list_printed": blocks_list,
        "blocks_ranges_printed": blocks_ranges_printed,
        "store_value_db_csv": store_csv,
        "ground_truth_size": gt_size,
        "expected_units_from_size": (expected_units if expected_units is not None else "NA"),
        "match": ("yes" if match else ("no" if match is not None else "NA")),
        "fs_units_info": {
            "fs_units": fs_units,
            "fs_units_ranges": compress_ranges(fs_units),
            "fs_unit_size": unit_size,
            "sectors_per_unit": sectors_per_unit
        },
        "fs_relative_sectors_info": {
            "fs_relative_sectors": rel_secs,
            "fs_relative_sectors_ranges": compress_ranges(rel_secs)
        }
    }
    print(json.dumps(result, indent=2))

    # Optional DB update
    if args.update_db:
        updated, unchanged, notfound = update_blocks(
            args.base_test_case, args.cftt_task, args.filename, store_csv,
            update_all_matches=args.update_all_matches, debug=args.debug
        )
        if args.debug:
            sys.stderr.write(f"[✓] DB summary: updated=%d, unchanged=%d, not_found=%d\n" % (updated, unchanged, notfound))

if __name__ == "__main__":
    main()
