#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
import json

# -----------------------------
# Helpers to run commands safely
# -----------------------------
def run_cmd(cmd, text=True):
    """Run a command and return (returncode, stdout, stderr)."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text
    )
    out, err = proc.communicate()
    return proc.returncode, out if out is not None else "", err if err is not None else ""

def run_cmd_bytes(cmd):
    """Run a command and return (returncode, stdout_bytes, stderr_text)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return proc.returncode, out if out is not None else b"", (err.decode("utf-8", "ignore") if err else "")

# -----------------------------
# Parse mmls (capture *all* rows)
# -----------------------------
# Example row:
# 004:  000       0000000034   0000976561   0000976528   <Description>
MMLS_ROW = re.compile(
    r"^\s*(?P<slot>\d{3}):\s+(?P<part_id>[\d-]{3,})\s+(?P<start>\d+)\s+(?P<end>\d+)\s+(?P<length>\d+)\s+(?P<desc>.+)$"
)

def parse_mmls(image, mmls_path="/home/akila/tsk465/bin/mmls"):
    rc, out, err = run_cmd([mmls_path, image], text=True)
    if rc != 0:
        print(f"[ERROR] mmls failed on {image}: {err.strip()}", file=sys.stderr)
        sys.exit(1)
    entries = []
    for line in out.splitlines():
        m = MMLS_ROW.match(line)
        if not m:
            continue
        d = m.groupdict()
        entries.append({
            "slot": d["slot"],
            "part_id": d["part_id"].strip(),
            "start": int(d["start"]),
            "end": int(d["end"]),
            "length": int(d["length"]),
            "desc": d["desc"].strip()
        })
    return entries

def is_numeric_partition(entry):
    return entry["part_id"].isdigit()

def is_unallocated_gap(entry):
    return entry["part_id"].startswith("-") and "Unallocated" in entry["desc"]

# -----------------------------
# Filesystem detection with fsstat
# -----------------------------
def is_filesystem(image, offset, fsstat_path="/home/akila/tsk465/bin/fsstat"):
    rc, out, err = run_cmd([fsstat_path, "-o", str(offset), image], text=True)
    return rc == 0 and bool(out.strip())

# -----------------------------
# File listing with fls (regular files)
# -----------------------------
FLS_LINE = re.compile(r"^(?P<type>[dlr-]/[dlr-])\s+(?P<del>\*)?\s*(?P<inode>[^:]+):\s+(?P<path>\S.*)$")

def list_files(image, offset, fls_path="/home/akila/tsk465/bin/fls"):
    rc, out, err = run_cmd([fls_path, "-r", "-p", "-o", str(offset), image], text=True)
    if rc != 0:
        return []
    files = []
    for line in out.splitlines():
        m = FLS_LINE.match(line)
        if not m:
            continue
        ftype = m.group("type")
        inode = m.group("inode").strip()
        fpath = m.group("path").strip()
        deleted = bool(m.group("del"))
        if ftype.startswith("r/"):  # regular files only
            files.append((inode, fpath, deleted))
    return files

# -----------------------------
# Scan file content with icat
# -----------------------------
def scan_file(image, offset, inode, keyword, ignore_case=False, max_bytes=None, icat_path="/home/akila/tsk465/bin/icat"):
    """Yield (line_no, line_text) for lines containing keyword."""
    cmd = [icat_path, "-o", str(offset), image, inode]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    read_bytes = 0
    line_no = 0
    needle = keyword
    needle_ci = keyword.lower()

    for raw in proc.stdout:
        read_bytes += len(raw)
        line_no += 1
        text = raw.decode("utf-8", errors="ignore")
        hay = text if not ignore_case else text.lower()
        if (needle if not ignore_case else needle_ci) in hay:
            yield line_no, text.rstrip("\r\n")
        if max_bytes and read_bytes >= max_bytes:
            break

    proc.stdout.close()
    proc.wait()

# -----------------------------
# Read RAW region (by sectors) and search
# -----------------------------
def dd_region(image, start_sector, length_sectors, bs=512):
    """Return bytes of a region using dd (sectors)."""
    cmd = [
        "dd",
        f"if={image}",
        f"bs={bs}",
        f"skip={start_sector}",
        f"count={length_sectors}",
        "status=none"
    ]
    rc, out_bytes, err = run_cmd_bytes(cmd)
    if rc != 0:
        raise RuntimeError(f"dd failed: {err.strip()}")
    return out_bytes

def build_utf16_patterns(keyword, ignore_case=True):
    # ASCII bytes
    k_ascii = keyword.encode("utf-8", "ignore")
    patterns = []
    if ignore_case:
        patterns.append(re.compile(re.escape(k_ascii), flags=re.IGNORECASE))
    else:
        patterns.append(re.compile(re.escape(k_ascii)))

    # UTF-16LE and UTF-16BE (generate both original and lower-case if ASCII letters present)
    cases = [keyword]
    if ignore_case:
        cases = list({keyword, keyword.lower()})

    for k in cases:
        try:
            le = k.encode("utf-16le", "ignore")
            be = k.encode("utf-16be", "ignore")
            patterns.append(re.compile(re.escape(le)))
            patterns.append(re.compile(re.escape(be)))
        except Exception:
            # If encoding fails, skip
            pass

    # Lenient "optional nulls" between bytes (helps catch misalignment)
    # Example: 0x30(?:(?:\x00)?)0x39(?:(?:\x00)?)...
    # Only sensible for ASCII-range keywords
    if all(ord(c) < 128 for c in keyword):
        hex_bytes = [f"\\x{b:02x}" for b in k_ascii]
        # interleave optional \x00 between each
        pat = "".join([hb + "(?:\\x00)?" for hb in hex_bytes])
        try:
            patterns.append(re.compile(pat.encode("latin-1"), flags=0))
        except Exception:
            pass

    return patterns

def search_raw_bytes(data, keyword, ignore_case=False, context=64):
    """Return list of decoded context snippets around matches in raw bytes."""
    snippets = []
    patterns = build_utf16_patterns(keyword, ignore_case=ignore_case)
    # gather match offsets (deduplicate)
    offs = set()
    for pat in patterns:
        for m in pat.finditer(data):
            offs.add(m.start())
    for off in sorted(offs):
        start = max(0, off - context)
        end = min(len(data), off + context)
        chunk = data[start:end]
        # Try UTF-8, then UTF-16LE, then UTF-16BE
        for enc in ("utf-8", "utf-16le", "utf-16be"):
            try:
                txt = chunk.decode(enc, errors="ignore")
                if txt.strip():
                    snippets.append(txt.replace("\r", " ").replace("\n", " "))
                    break
            except Exception:
                continue
        else:
            # Fallback: hex preview
            snippets.append(chunk.hex())
    return snippets

# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Scan allocated files (TSK) and RAW regions (gaps + non-FS partitions) for a keyword; output JSON."
    )
    ap.add_argument("image", help="Path to disk image (e.g., ss-win-07-25-18.dd)")
    ap.add_argument("keyword", help='Keyword to search for (e.g., "DireWolf" or "0902")')
    ap.add_argument("--base-test-case", required=True, help='Base test case identifier to include in JSON (e.g., "CFTT-SS-v1.1-win")')
    ap.add_argument("--tool-used", required=True, help='Tool name/version to include in JSON (e.g., "TSK 4.6.5 + icat/fls + dd")')
    ap.add_argument("--case-sensitive", action="store_true", help="Case-sensitive search (default: case-insensitive)")
    ap.add_argument("--max-bytes", type=int, default=None, help="Optional limit on bytes read per *file* (icat)")
    ap.add_argument("--skip-files", action="store_true", help="Skip allocated/deleted files (only search RAW regions)")
    ap.add_argument("--skip-raw", action="store_true", help="Skip RAW regions (only search files)")
    args = ap.parse_args()

    image = args.image
    keyword = args.keyword
    ignore_case = not args.case_sensitive

    if not os.path.exists(image):
        print(f"[ERROR] Image not found: {image}", file=sys.stderr)
        print(json.dumps({
            "base_test_case": args.base_test_case,
            "file_contents_found": [],
            "tool_used": args.tool_used
        }, ensure_ascii=False))
        sys.exit(1)

    mmls_entries = parse_mmls(image)

    hits = []

    # ---------- 1) Allocated/deleted files via TSK ----------
    if not args.skip_files:
        # Use only numeric partitions that are real filesystems
        for e in mmls_entries:
            if not is_numeric_partition(e):
                continue
            if not is_filesystem(image, e["start"]):
                continue  # not a FS; will be scanned as RAW below
            files = list_files(image, e["start"])
            for inode, path, deleted in files:
                try:
                    for line_no, line in scan_file(image, e["start"], inode, keyword, ignore_case, args.max_bytes):
                        hits.append(line)
                except Exception as ex:
                    print(f"[WARN] icat failed at offset {e['start']} inode {inode} ({path}): {ex}", file=sys.stderr)

    # ---------- 2) RAW regions: GPT gaps + non-FS partitions ----------
    if not args.skip_raw:
        raw_regions = []
        for e in mmls_entries:
            # GPT unallocated gaps
            if is_unallocated_gap(e) and e["length"] > 0:
                raw_regions.append(("GAP", e))
            # Numeric partitions that are NOT filesystems
            elif is_numeric_partition(e) and not is_filesystem(image, e["start"]):
                raw_regions.append(("RAWPART", e))

        for rtype, e in raw_regions:
            try:
                data = dd_region(image, e["start"], e["length"], bs=512)
                snippets = search_raw_bytes(data, keyword, ignore_case=ignore_case, context=64)
                hits.extend(snippets)
            except Exception as ex:
                print(f"[WARN] RAW scan failed for {rtype} slot {e['slot']} start {e['start']} len {e['length']}: {ex}", file=sys.stderr)

    # ---------- Output JSON ----------
    result = {
        "base_test_case": args.base_test_case,
        "file_contents_found": hits,
        "os":"windows",
        "tool_used": args.tool_used
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
