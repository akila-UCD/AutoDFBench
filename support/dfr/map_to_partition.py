#!/usr/bin/env python3
import argparse, re, sys
from typing import List, Tuple, Dict

SECTOR_SIZE = 512

def parse_partitions(spec: str):
    """
    spec: 'sdd1:61-651235,sdd2:651236-1302471,sdd3:1302472-1953707'
    returns list of (name, start, end) sorted by start
    """
    parts=[]
    for tok in re.split(r'\s*,\s*', spec.strip()):
        if not tok: continue
        m = re.fullmatch(r'([^:]+):\s*(\d+)\s*-\s*(\d+)', tok)
        if not m:
            sys.exit(f"Bad partition token: {tok}")
        name, s, e = m.group(1), int(m.group(2)), int(m.group(3))
        if e < s: sys.exit(f"Partition end < start: {tok}")
        parts.append((name, s, e))
    parts.sort(key=lambda x: x[1])
    return parts

def parse_ranges(text: str) -> List[Tuple[int,int]]:
    """
    Accepts 'S-E, S2 - E2' (spaces ok) and singletons 'N' as N-N.
    """
    pairs = []
    for s,e in re.findall(r'(\d+)\s*-\s*(\d+)', text):
        s, e = int(s), int(e)
        if e < s: sys.exit(f"Range end < start: {s}-{e}")
        pairs.append((s,e))
    # add singletons not part of pairs
    seen = set()
    for s,e in pairs: seen.add(s); seen.add(e)
    for n in re.findall(r'\b(\d+)\b', text):
        ni = int(n)
        if ni in seen: continue
        pairs.append((ni, ni))
    # dedup & sort
    return sorted(set(pairs))

def which_partition(sector: int, parts) -> str:
    for name, start, end in parts:
        if start <= sector <= end:
            return name
    return ""

def map_file(name: str, ranges: List[Tuple[int,int]], parts):
    # collect all partitions touched by the file’s sectors
    touched = set()
    for s,e in ranges:
        # fast check: just test endpoints (optional: sample inside if you want)
        p1 = which_partition(s, parts)
        p2 = which_partition(e, parts)
        if not p1 or not p2 or p1 != p2:
            # fall back to a stricter scan across the range edges
            for probe in (s, e, (s+e)//2):
                p = which_partition(probe, parts)
                if p: touched.add(p)
        else:
            touched.add(p1)
    return sorted(touched)

def main():
    ap = argparse.ArgumentParser(description="Map files (by sector ranges) to partitions.")
    ap.add_argument("--partitions", required=True,
                    help="Comma list: 'sdd1:61-651235,sdd2:651236-1302471,...'")
    ap.add_argument("--file", action="append", default=[],
                    help="Format: 'Name: S-E, S2-E2 ...'. Repeat for multiple files.")
    ap.add_argument("--from-bytes", action="store_true",
                    help="If the ranges are in BYTES (not sectors), convert using sector_size=512.")
    args = ap.parse_args()

    parts = parse_partitions(args.partitions)
    if not args.file:
        print("No --file entries given.", file=sys.stderr)
        sys.exit(1)

    print("file,partitions,status")
    for f in args.file:
        if ":" not in f:
            print(f"{f},,BAD_SPEC"); continue
        fname, rng = f.split(":", 1)
        fname = fname.strip()
        ranges = parse_ranges(rng)
        if args.from_bytes:
            # convert byte ranges to sector ranges (floor for start, floor for end)
            ranges = [ (s//SECTOR_SIZE, e//SECTOR_SIZE) for s,e in ranges ]
        parts_hit = map_file(fname, ranges, parts)

        if not parts_hit:
            status = "NO_MATCH"
        elif len(parts_hit) == 1:
            status = "OK"
        else:
            status = "CROSSES_PARTITIONS"

        print(f"{fname},{'|'.join(parts_hit)},{status}")

if __name__ == "__main__":
    main()
