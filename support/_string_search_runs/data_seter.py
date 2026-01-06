#!/usr/bin/env python3
# parse_string_hits.py
# Extract (id, keyword, file, file_line) from a "strings search" text report.
# Supports detailed "Hit [####]:" blocks and colon-separated index summary lines.

import re, csv, sys, io
from pathlib import Path
from typing import List, Dict, Optional

Hit = Dict[str, str]

# ---------- Regex patterns ----------
RE_HIT_HEADER = re.compile(r'^Hit\s*\[(\d+)\]\s*:\s*(.*?)\s*\(', re.UNICODE)
RE_FILE_LINE  = re.compile(r'^File:\s*(.+)$', re.UNICODE)
RE_DD_LINE    = re.compile(r'^\s*dd\s+bs=', re.UNICODE)
# Hexdump lines like:
# 00000000  <hex bytes>  |ASCII...|
RE_HEXDUMP_ASCII_COL = re.compile(
    r'^\s*[0-9A-Fa-f]{8}\s+(?:[0-9A-Fa-f]{2}\s+){1,16}\|\s*(.*?)\s*\|?\s*$',
    re.UNICODE
)

# Fallback index/summary lines:
# 0910:DireWolf:1510617279:2950424:LIVE-Extinct-Lupus-apfs-ascii.txt:apfs:utf-8
RE_INDEX_LINE = re.compile(
    r'^(\d+):([^:]+):(\d+):(\d+):([^:]+):([^:]+):([^\s:]+)\s*$',
    re.UNICODE
)

def extract_ascii_from_hexdump(line: str) -> Optional[str]:
    m = RE_HEXDUMP_ASCII_COL.match(line)
    return m.group(1) if m else None

def parse_hits(lines: List[str]) -> List[Hit]:
    results: List[Hit] = []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]

        # -------- Case 1: Detailed "Hit [####]:" block --------
        m = RE_HIT_HEADER.match(line)
        if m:
            hit_id_num = m.group(1)
            keyword    = m.group(2).strip()
            hit_id_str = f"Hit [{hit_id_num}]"

            file_path = ""
            ascii_parts: List[str] = []

            # Find "File:" line
            j = i + 1
            while j < n and not lines[j].startswith("Hit ["):
                mf = RE_FILE_LINE.match(lines[j])
                if mf:
                    file_path = mf.group(1).strip()
                    j += 1
                    break
                j += 1

            # Find the 'dd' command line (optional but typical)
            dd_idx = None
            k = j
            while k < n and not lines[k].startswith("Hit ["):
                if RE_DD_LINE.match(lines[k] or ""):
                    dd_idx = k
                    break
                k += 1

            # Collect ASCII from hexdump lines after dd (or directly after File: if no dd line)
            start_idx = (dd_idx + 1) if dd_idx is not None else j
            last_ascii_row = -1
            k = start_idx
            while k < n and not lines[k].startswith("Hit ["):
                ascii_seg = extract_ascii_from_hexdump(lines[k])
                if ascii_seg is not None:
                    ascii_parts.append(ascii_seg)
                    last_ascii_row = k
                    k += 1
                    continue
                if last_ascii_row != -1:
                    break
                k += 1

            file_line = "".join(ascii_parts).strip()
            results.append({
                "id": hit_id_str,
                "keyword": keyword,
                "file": file_path,
                "file_line": file_line,
            })

            i = max(k, j, i + 1)
            continue

        # -------- Case 2: Fallback colon-separated index line --------
        m2 = RE_INDEX_LINE.match(line)
        if m2:
            hit_id_num = m2.group(1)
            keyword    = m2.group(2).strip()
            file_path  = m2.group(5).strip()
            hit_id_str = f"Hit [{hit_id_num}]"
            results.append({
                "id": hit_id_str,
                "keyword": keyword,
                "file": file_path,
                "file_line": "",  # not available in summary lines
            })
            i += 1
            continue

        i += 1

    return results

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="Parse strings-search report to CSV with (id, keyword, file, file_line)."
    )
    ap.add_argument("input", help="Path to input TXT report")
    ap.add_argument("-o", "--output", default="hits_out.csv", help="Output CSV path")
    args = ap.parse_args()

    with io.open(args.input, "r", encoding="utf-8", errors="replace") as f:
        lines = [ln.rstrip("\n") for ln in f]

    rows = parse_hits(lines)

    with io.open(args.output, "w", encoding="utf-8", newline="") as fw:
        writer = csv.DictWriter(fw, fieldnames=["id", "keyword", "file", "file_line"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.output}")
