#!/usr/bin/env python3
import argparse
import subprocess
import json
import re
from datetime import datetime
import pytz

# ---------- Timestamp conversion ----------
def convert_to_epoch(timestamp_str):
    """
    Accepts:
      - 'YYYY-MM-DD HH:MM:SS (TZ)'
      - 'Fri Feb  3 15:08:50 2012'  (no TZ; treated as UTC)
      - 'Mon Jan 02 03:04:05 GMT 2012' (with TZ abbr)
      - 'YYYY-MM-DD HH:MM:SS[.ffffff] ±HHMM'
      - '0000-00-00 ...' -> 0
    """
    timezone_map = {
        "GMT": "UTC",
        "IST": "Asia/Kolkata",
        "UTC": "UTC",
        "EDT": "America/New_York",
        "EST": "America/New_York",
        "PDT": "America/Los_Angeles",
        "PST": "America/Los_Angeles",
        "CST": "America/Chicago",
        "CDT": "America/Chicago",
        "MST": "America/Denver",
        "MDT": "America/Denver",
    }
    try:
        s = (timestamp_str or "").strip()
        if not s:
            return None
        if s.startswith("0000-00-00"):
            return 0

        # Case A: 'YYYY-MM-DD HH:MM:SS (TZ)'
        m = re.match(r"^(.*\d{2}:\d{2}:\d{2}) \(([\w/+:-]+)\)$", s)
        if m:
            base_time = m.group(1).strip()
            tz_abbr = m.group(2).strip()
            dt_naive = datetime.strptime(base_time, "%Y-%m-%d %H:%M:%S")
            if tz_abbr in timezone_map:
                tz = pytz.timezone(timezone_map[tz_abbr])
                return int(tz.localize(dt_naive).timestamp())
            # unknown TZ -> treat as UTC
            return int(dt_naive.replace(tzinfo=pytz.UTC).timestamp())

        # Case B: 'Day Mon DD HH:MM:SS TZ YYYY'
        m2 = re.match(r"^(\w{3}) (\w{3})\s+(\d{1,2}) (\d{2}:\d{2}:\d{2}) (\w{2,4}) (\d{4})$", s)
        if m2:
            _, mon, day, time_part, tz_abbr, year = m2.groups()
            day = f"{int(day):02d}"
            dt_naive = datetime.strptime(f"{year} {mon} {day} {time_part}", "%Y %b %d %H:%M:%S")
            if tz_abbr in timezone_map:
                tz = pytz.timezone(timezone_map[tz_abbr])
                return int(tz.localize(dt_naive).timestamp())
            return int(dt_naive.replace(tzinfo=pytz.UTC).timestamp())

        # Case C: 'Day Mon DD HH:MM:SS YYYY' (no TZ) -> treat as UTC
        m3 = re.match(r"^(\w{3}) (\w{3})\s+(\d{1,2}) (\d{2}:\d{2}:\d{2}) (\d{4})$", s)
        if m3:
            _, mon, day, time_part, year = m3.groups()
            day = f"{int(day):02d}"
            dt = datetime.strptime(f"{year} {mon} {day} {time_part}", "%Y %b %d %H:%M:%S")
            return int(dt.replace(tzinfo=pytz.UTC).timestamp())

        # Case D: numeric timezone forms 'YYYY-MM-DD HH:MM:SS[.ffffff] ±HHMM'
        s = re.sub(r"(\.\d{6})\d+", r"\1", s)  # trim >microseconds
        fmt = "%Y-%m-%d %H:%M:%S.%f %z" if "." in s else "%Y-%m-%d %H:%M:%S %z"
        try:
            dt = datetime.strptime(s, fmt)
            return int(dt.timestamp())
        except Exception:
            pass

        return None
    except Exception:
        return None

# ---------- Helpers ----------
def parse_offsets(offset_arg):
    offsets = []
    for token in offset_arg.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            offsets.append(int(token))
        except ValueError:
            print(f"[WARN] Skipping invalid offset token: {token}")
    return offsets

def get_tsk_version(default="The Sleuth Kit", fls_bin="fls"):
    try:
        res = subprocess.run([fls_bin, "-V"], capture_output=True, text=True)
        blob = (res.stdout or res.stderr or "").strip()
        line = blob.splitlines()[0] if blob else ""
        return line or default
    except Exception:
        return default

def derive_istat_bin_from_fls(fls_bin: str) -> str:
    return fls_bin.rsplit("/", 1)[0] + "/istat" if "/" in fls_bin else "istat"

def run_fls_deleted_long(fls_bin, image_path, offset):
    cmd = [fls_bin, "-r", "-l", "-d", "-o", str(offset), image_path]
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        raw_lines = res.stdout.splitlines()
        # Merge wrapped '-l' lines in older TSK
        combined = []
        current = ""
        for ln in raw_lines:
            if FLS_PREFIX_RE.match(ln):
                if current:
                    combined.append(current)
                current = ln
            else:
                current = (current + " " + ln.strip()) if current else ln.strip()
        if current:
            combined.append(current)
        return combined
    except subprocess.CalledProcessError as e:
        print(f"[WARN] fls failed for offset {offset}: {e.stderr.strip() or 'unknown error'}")
        return []

# Example prefixes: "r/r * 36:", "-/r * 36-128-3:", "d/d * 123:"
FLS_PREFIX_RE = re.compile(r"^\s*([a-z\-]\/[a-z\-])\s+\*?\s*([\d\-]+):\s*(.+)$", re.IGNORECASE)

def parse_fls_long_line(line):
    m = FLS_PREFIX_RE.match(line)
    if not m:
        return None
    entry_type, meta, rest = m.groups()

    parts = rest.split("\t")
    if len(parts) < 2:
        parts = re.split(r"\s{2,}", rest)

    # Expected: name, mtime, atime, ctime, crtime, size, ...
    name = parts[0].strip() if len(parts) > 0 else ""
    mtime = parts[1].strip() if len(parts) > 1 else ""
    atime = parts[2].strip() if len(parts) > 2 else ""
    ctime = parts[3].strip() if len(parts) > 3 else ""
    crtime = parts[4].strip() if len(parts) > 4 else ""
    size_str = parts[5].strip() if len(parts) > 5 else ""

    try:
        size = int(size_str) if size_str else None
    except ValueError:
        size = None

    return {
        "entry_type": entry_type.lower(),
        "meta": meta,                 # keep full meta (e.g., '36-128-3')
        "file_name": name,
        "mtime": mtime,
        "atime": atime,
        "ctime": ctime,
        "crtime": crtime,
        "file_size": size
    }

def try_istat_deleted(istat_bin, image_path, offset, meta) -> int:
    """
    Try Deleted: time via istat.
    Attempt order:
      1) full meta (e.g., '36-128-3')
      2) base inode (e.g., '36')
    Return epoch seconds or 0.
    """
    candidates = []
    meta_str = str(meta)
    candidates.append(meta_str)
    base = re.match(r"(\d+)", meta_str)
    if base and base.group(1) != meta_str:
        candidates.append(base.group(1))

    for cand in candidates:
        cmd = [istat_bin, "-o", str(offset), image_path, cand]
        try:
            res = subprocess.run(cmd, check=True, capture_output=True, text=True)
            text = res.stdout or ""
        except subprocess.CalledProcessError as e:
            text = (e.stdout or "") + "\n" + (e.stderr or "")

        ts = _parse_deleted_from_istat(text)
        if ts and ts > 0:
            return ts
    return 0

def _parse_deleted_from_istat(text: str) -> int:
    # Support several labels and capitalisations
    m = re.search(r"^\s*(Deleted|File Deleted|Inode Deleted)\s*:\s*(.+)$",
                  text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return 0
    ts = m.group(2).strip()
    val = convert_to_epoch(ts)
    return val if isinstance(val, int) and val >= 0 else 0

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(description="List deleted files via fls -l; enrich with istat Deleted time; output JSON.")
    ap.add_argument("image", help="Path to forensic image")
    ap.add_argument("-o", "--offsets", required=True, help='Comma-separated offsets, e.g. "61,2048" (sectors)')
    ap.add_argument("--base-test-case", required=True, help='Base test case, e.g. "DFR-02/ntfs-02"')
    ap.add_argument("--file-system", default="UNKNOWN", help="File system label to include in JSON")
    ap.add_argument("--tool-used", default=None, help='Override tool string (defaults to "fls -V" output)')
    ap.add_argument("--check-meta", action="store_true", default=True)
    ap.add_argument("--tsk-version", choices=["3.2", "latest"], default="latest",
                    help="Choose which TSK version to use: '3.2' for /home/akila/tsk322/bin/*, 'latest' for system tools")
    args = ap.parse_args()

    # Decide binaries (istat matched to fls)
    fls_bin = "/home/akila/tsk322/bin/fls" if args.tsk_version == "3.2" else "fls"
    istat_bin = derive_istat_bin_from_fls(fls_bin)

    tool_used = args.tool_used or get_tsk_version("The Sleuth Kit", fls_bin)

    result = {
        "base_test_case": args.base_test_case,
        "tool_used": tool_used,
        "check_meta": bool(args.check_meta),
        "file_system": args.file_system,
        "include_orphans": False,
        "files": []
    }

    offsets = parse_offsets(args.offsets)
    if not offsets:
        print(json.dumps(result, indent=2))
        return

    for off in offsets:
        print(f"[INFO] Processing offset {off}")
        lines = run_fls_deleted_long(fls_bin, args.image, off)
        if not lines:
            continue
        for ln in lines:
            parsed = parse_fls_long_line(ln)
            if not parsed:
                continue

            # Keep only regular files (RHS 'r'): 'r/r', '-/r', etc.
            t = parsed["entry_type"]
            rhs = t.split("/", 1)[1] if "/" in t else t
            if rhs != "r":
                continue

            # Timestamps from fls -l
            mt = convert_to_epoch(parsed["mtime"]) if parsed["mtime"] else None
            at = convert_to_epoch(parsed["atime"]) if parsed["atime"] else None
            ct = convert_to_epoch(parsed["ctime"]) if parsed["ctime"] else None
            crt = convert_to_epoch(parsed["crtime"]) if parsed["crtime"] else None

            # Deleted time from istat (when available)
            deleted_ts = try_istat_deleted(istat_bin, args.image, off, parsed.get("meta"))

            entry = {
                "inode": parsed.get("meta", ""),  # <— include inode/meta in output
                "file_name": parsed["file_name"],
                "file_size": parsed["file_size"] if parsed["file_size"] is not None else 0,
                "deleted_timestamp": deleted_ts if isinstance(deleted_ts, int) and deleted_ts >= 0 else 0,
                "modified_timestamp": mt if mt is not None else 0,
                "changed_timestamp": ct if ct is not None else 0,
                "accessed_timestamp": at if at is not None else 0,
                "fbks": None
            }
            result["files"].append(entry)

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
