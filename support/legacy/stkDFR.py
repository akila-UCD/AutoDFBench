#!/usr/bin/env python3
import argparse
import subprocess
import json
import re
import sys
from datetime import datetime
import pytz
import os
import unicodedata

# ---------- Timestamp conversion ----------
def convert_to_epoch(timestamp_str):
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

        # e.g. 2012-02-03 15:10:01 (GMT)
        m = re.match(r"^(.*\d{2}:\d{2}:\d{2}) \(([\w/+:-]+)\)$", s)
        if m:
            base_time = m.group(1).strip()
            tz_abbr = m.group(2).strip()
            dt_naive = datetime.strptime(base_time, "%Y-%m-%d %H:%M:%S")
            if tz_abbr in timezone_map:
                tz = pytz.timezone(timezone_map[tz_abbr])
                return int(tz.localize(dt_naive).timestamp())
            return int(dt_naive.replace(tzinfo=pytz.UTC).timestamp())

        # e.g. Fri Feb 03 15:10:01 GMT 2012
        m2 = re.match(r"^(\w{3}) (\w{3})\s+(\d{1,2}) (\d{2}:\d{2}:\d{2}) (\w{2,4}) (\d{4})$", s)
        if m2:
            _, mon, day, time_part, tz_abbr, year = m2.groups()
            day = f"{int(day):02d}"
            dt_naive = datetime.strptime(f"{year} {mon} {day} {time_part}", "%Y %b %d %H:%M:%S")
            if tz_abbr in timezone_map:
                tz = pytz.timezone(timezone_map[tz_abbr])
                return int(tz.localize(dt_naive).timestamp())
            return int(dt_naive.replace(tzinfo=pytz.UTC).timestamp())

        # e.g. Fri Feb 03 15:10:01 2012
        m3 = re.match(r"^(\w{3}) (\w{3})\s+(\d{1,2}) (\d{2}:\d{2}:\d{2}) (\d{4})$", s)
        if m3:
            _, mon, day, time_part, year = m3.groups()
            day = f"{int(day):02d}"
            dt = datetime.strptime(f"{year} {mon} {day} {time_part}", "%Y %b %d %H:%M:%S")
            return int(dt.replace(tzinfo=pytz.UTC).timestamp())

        # e.g. 2012-02-03 15:10:01.239155000 +0000
        s = re.sub(r"(\.\d{6})\d+", r"\1", s)
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
            print(f"[WARN] Skipping invalid offset token: {token}", file=sys.stderr)
    return offsets

def get_tsk_version(default="The Sleuth Kit", fls_bin="fls"):
    try:
        res = subprocess.run([fls_bin, "-V"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        blob = (res.stdout or res.stderr or "").strip()
        line = blob.splitlines()[0] if blob else ""
        return line or default
    except Exception:
        return default

def derive_tool_from_fls(fls_bin: str, tool: str) -> str:
    return fls_bin.rsplit("/", 1)[0] + f"/{tool}" if "/" in fls_bin else tool

def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

# Prefix: "r/r * 36:", "-/r * 36-128-3:", "r/- * 0:", etc.
FLS_PREFIX_RE = re.compile(
    r"^\s*(?P<prefix>[a-z\-]\/[a-z\-])\s+(?P<star>\*)?\s*(?P<meta>[\d\-]+):\s*(?P<rest>.+)$",
    re.IGNORECASE
)

def run_fls(fls_bin, image_path, offset, force_fs=None, deleted_only=True):
    cmd = [fls_bin, "-r", "-l"]
    if deleted_only:
        cmd.append("-d")
    cmd += ["-o", str(offset)]
    if force_fs:
        cmd += ["-f", force_fs]
    cmd.append(image_path)
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        # Unwrap potential line wraps (rare)
        lines, current = [], ""
        for raw in res.stdout.splitlines():
            if FLS_PREFIX_RE.match(raw):
                if current:
                    lines.append(current)
                current = raw
            else:
                current = (current + " " + raw.strip()) if current else raw.strip()
        if current:
            lines.append(current)
        return lines
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or '').strip() or 'unknown error'
        print(f"[WARN] fls failed for offset {offset}: {msg}", file=sys.stderr)
        return []

_SPLIT = re.compile(r"\t+|\s{2,}")
def _looks_like_ts(token: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\([\w/+:-]+\)$", token.strip()))

def parse_fls_long_line(line, debug=False):
    m = FLS_PREFIX_RE.match(line)
    if not m:
        if debug:
            print(f"[DEBUG] skip: prefix regex didn't match -> {line!r}", file=sys.stderr)
        return None

    entry_type = (m.group("prefix") or "").lower()
    meta = m.group("meta") or ""
    rest = m.group("rest") or ""

    toks = _SPLIT.split(rest.strip())
    ts_idx = [i for i, t in enumerate(toks) if _looks_like_ts(t)]
    if len(ts_idx) < 4:
        if debug:
            print(f"[DEBUG] skip: <4 timestamps -> toks={toks}", file=sys.stderr)
        return None
    m_i, a_i, c_i, cr_i = ts_idx[-4:]

    name = " ".join(toks[:m_i]).strip()
    if not name:
        if debug:
            print(f"[DEBUG] skip: empty name -> {line!r}", file=sys.stderr)
        return None

    size = 0
    for i in range(cr_i + 1, len(toks)):
        if re.fullmatch(r"\d+", toks[i]):
            try:
                size = int(toks[i])
            except Exception:
                size = 0
            break

    return {
        "entry_type": entry_type,
        "meta": meta,
        "file_name": name,
        "mtime": toks[m_i].strip(),
        "atime": toks[a_i].strip(),
        "ctime": toks[c_i].strip(),
        "crtime": toks[cr_i].strip(),
        "file_size": size
    }

# ---------- istat parsing (Deleted time + Blocks) ----------
_BLOCK_HEADER_RE = re.compile(
    r"^(Direct Blocks|Sectors|Blocks|Data runs|Extent Details|Clusters)\s*:\s*(.*)$",
    re.IGNORECASE
)
_DATA_ATTR_RE = re.compile(r"^\s*Type:\s*\$DATA\b.*\bNon[-\s]?Resident\b.*$", re.IGNORECASE)

def _parse_deleted_from_istat(text: str) -> int:
    m = re.search(r"^\s*(Deleted|File Deleted|Inode Deleted)\s*:\s*(.+)$",
                  text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return 0
    ts = m.group(2).strip()
    val = convert_to_epoch(ts)
    return val if isinstance(val, int) and val >= 0 else 0

def _parse_blocks_from_istat(text: str):
    lines = text.splitlines()
    blocks = []

    def add_tokens(s: str):
        for m in re.finditer(r"(\d+)(?:\s*-\s*(\d+))?", s):
            start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else start
            if end >= start and (end - start) <= 200000:
                blocks.extend(range(start, end + 1))

    i = 0
    while i < len(lines):
        line = lines[i]
        m = _BLOCK_HEADER_RE.match(line.strip())
        if m:
            remainder = m.group(2)
            if remainder:
                add_tokens(remainder)
            j = i + 1
            while j < len(lines):
                stripped = lines[j].strip()
                if not stripped: break
                if re.match(r"^[A-Za-z].+:\s*$", stripped) and not re.match(r"^\d", stripped): break
                if lines[j].startswith(" ") or re.match(r"^[0-9\s,\-]+$", stripped):
                    add_tokens(stripped); j += 1
                else:
                    break
            i = j; continue

        if _DATA_ATTR_RE.match(line):
            j = i + 1; blank_seen = False
            while j < len(lines):
                stripped = lines[j].strip()
                if not stripped:
                    if blank_seen: j += 1; break
                    blank_seen = True; j += 1; continue
                if stripped.lower().startswith("type: "): break
                if re.match(r"^[0-9][0-9\s,\-]*$", stripped) or re.search(r"\b(run|extent|cluster)\b", stripped, re.IGNORECASE):
                    add_tokens(stripped)
                else:
                    break
                j += 1
            i = j; continue
        i += 1

    return sorted(set(blocks))

def _run_istat(istat_bin, image_path, offset, cand, force_fs=None):
    cmd = [istat_bin, "-o", str(offset)]
    if force_fs:
        cmd += ["-f", force_fs]
    cmd += [image_path, str(cand)]
    res = run_cmd(cmd)
    if res.returncode == 0:
        return res.stdout or ""
    return (res.stdout or "") + "\n" + (res.stderr or "")

def gather_istat_info(istat_bin, image_path, offset, meta, force_fs=None):
    candidates = []
    meta_str = str(meta or "")
    if meta_str:
        candidates.append(meta_str)
        base = re.match(r"(\d+)", meta_str)
        if base and base.group(1) != meta_str:
            candidates.append(base.group(1))

    deleted_ts_final = 0
    blocks_final = []

    for cand in candidates or [""]:
        if not cand:
            continue
        text = _run_istat(istat_bin, image_path, offset, cand, force_fs=force_fs)
        if not text:
            continue

        del_ts = _parse_deleted_from_istat(text)
        blks = _parse_blocks_from_istat(text)

        if del_ts and del_ts > 0:
            deleted_ts_final = del_ts
        if blks:
            blocks_final = blks

        if deleted_ts_final > 0 and blocks_final:
            break

    return deleted_ts_final or 0, blocks_final

# ---------- mmls + fsstat probing ----------
MMLS_ROW_RE = re.compile(
    r"""^\s*
        (?P<slot>\d{1,3}|-+):\s+
        (?:(?P<addr>\S+)\s+)? 
        (?P<start>\d+)\s+
        (?P<end>\d+)\s+
        (?P<length>\d+)\s+
        (?P<desc>.+)$
    """,
    re.IGNORECASE | re.VERBOSE
)

def run_mmls(mmls_bin, image_path):
    try:
        res = subprocess.run([mmls_bin, image_path], check=True, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"[WARN] mmls failed: {(e.stderr or e.stdout or '').strip()}", file=sys.stderr)
        return ""
    except FileNotFoundError:
        print(f"[WARN] mmls not found at '{mmls_bin}'", file=sys.stderr)
        return ""

def parse_mmls_offsets(mmls_text, include_all_data_parts=True):
    if not mmls_text:
        return []
    offsets = []
    bad = ("Unallocated", "Primary Table", "Secondary Table", "Extended", "GPT Header", "GPT Entry Array")
    for line in mmls_text.splitlines():
        mrow = MMLS_ROW_RE.match(line)
        if not mrow:
            continue
        desc = (mrow.group("desc") or "").strip()
        if any(b.lower() in desc.lower() for b in bad):
            continue
        if not include_all_data_parts:
            ok_kw = ("NTFS", "FAT", "exFAT", "EXT", "LINUX", "HFS", "APFS", "ISO9660")
            if not any(k in desc.upper() for k in ok_kw):
                continue
        try:
            start_sec = int(mrow.group("start"))
            if start_sec >= 0:
                offsets.append(start_sec)
        except ValueError:
            continue
    return sorted(set(offsets))

FSSTAT_TYPE_RE = re.compile(r"^\s*File System Type:\s*(.+)$", re.IGNORECASE | re.MULTILINE)

def probe_offsets_with_fsstat(fsstat_bin, image_path, candidates, force_fs=None):
    good = []
    for off in candidates:
        cmd = [fsstat_bin, "-o", str(off)]
        if force_fs:
            cmd += ["-f", force_fs]
        cmd.append(image_path)
        res = run_cmd(cmd)
        out = (res.stdout or "") + "\n" + (res.stderr or "")
        if res.returncode == 0 and FSSTAT_TYPE_RE.search(out):
            fs_line = FSSTAT_TYPE_RE.search(out).group(1).strip()
            print(f"[INFO] fsstat detected '{fs_line}' at sector {off}", file=sys.stderr)
            good.append(off)
    return sorted(set(good))

# ---------- Name normalization ----------
TSK_DUP_SUFFIX_RE = re.compile(r"^(?P<stem>.+?)(?P<ext>\.[^.\/\\\s]+)(?P<dup>\d+)$", re.UNICODE)

def normalize_request_name(name: str, strip_tsk_dup_suffix: bool) -> str:
    if not isinstance(name, str):
        return name
    base = os.path.basename(name).strip()
    base = unicodedata.normalize("NFC", base)
    if strip_tsk_dup_suffix:
        m = TSK_DUP_SUFFIX_RE.match(base)
        if m:
            base = m.group("stem") + m.group("ext")
    return base

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser(
        description="List deleted files via fls -l; enrich with istat Deleted time and block list; output JSON. Auto-detect offsets with mmls and fsstat probing."
    )
    ap.add_argument("image", help="Path to forensic image (dd/raw)")
    ap.add_argument("-o", "--offsets", default=None,
                    help='Comma-separated offsets in sectors, e.g. "61,2048". If omitted, auto-detect.')
    ap.add_argument("--base-test-case", required=True, help='Base test case, e.g. "DFR-02/ntfs-02"')
    ap.add_argument("--file-system", default="UNKNOWN", help="Label in JSON (FAT/NTFS/EXT/etc.)")
    ap.add_argument("--tool-used", default=None, help='Override tool string (defaults to "fls -V" output)')
    ap.add_argument("--check-meta", action="store_true", default=False, help="Include meta consistency checks (flag only)")
    ap.add_argument("--tsk-version", choices=["3.2", "latest"], default="latest",
                    help="Use TSK 3.2 (/home/akila/tsk322/bin/*) or system 'latest'.")
    ap.add_argument("--mmls-all", action="store_true", default=True,
                    help="Include all data partitions from mmls (skip only Unallocated/Table/Extended).")
    ap.add_argument("--mmls-filtered", dest="mmls_all", action="store_false",
                    help="Only include obvious filesystem partitions.")
    ap.add_argument("--force-fs", default=None, help="Force FS type for fls/istat/fsstat (fat, ntfs, ext)")
    ap.add_argument("--strip-tsk-dup-suffix", action="store_true", default=False,
                    help="Strip trailing TSK duplicate digits (e.g. 'file.txt1' -> 'file.txt').")
    ap.add_argument("--include-allocated", action="store_true",
                    help="Include allocated entries too (drop -d).")
    ap.add_argument("--debug", action="store_true",
                    help="Verbose parse logs to stderr")
    args = ap.parse_args()

    fls_bin = "/home/akila/tsk322/bin/fls" if args.tsk_version == "3.2" else "fls"
    istat_bin = derive_tool_from_fls(fls_bin, "istat")
    mmls_bin = derive_tool_from_fls(fls_bin, "mmls")
    fsstat_bin = derive_tool_from_fls(fls_bin, "fsstat")

    tool_used = args.tool_used or get_tsk_version("The Sleuth Kit", fls_bin)
    test_set = "FILE_SIZE_TESTS"

    result = {
        "base_test_case": args.base_test_case,
        "tool_used": tool_used,
        "test_set": test_set,
        "check_meta": bool(args.check_meta),
        "file_system": args.file_system,
        "file_count": 0,
        "files": []
    }

    # 1) Determine offsets
    if args.offsets:
        offsets = parse_offsets(args.offsets)
        print(f"[INFO] Using user-provided offsets: {offsets}", file=sys.stderr)
    else:
        print("[INFO] No offsets provided; running mmls to discover partitions...", file=sys.stderr)
        mmls_txt = run_mmls(mmls_bin, args.image)
        offsets = parse_mmls_offsets(mmls_txt, include_all_data_parts=args.mmls_all)
        if not offsets:
            print("[WARN] mmls found no data partitions; probing common sector offsets with fsstat...", file=sys.stderr)
            common_candidates = [0, 63, 128, 256, 512, 1024, 2048, 4096, 8192, 16384]
            offsets = probe_offsets_with_fsstat(fsstat_bin, args.image, common_candidates, force_fs=args.force_fs)
        if offsets:
            print(f"[INFO] Using offsets (sectors): {offsets}", file=sys.stderr)
        else:
            print("[ERROR] Could not identify any valid filesystem offsets.", file=sys.stderr)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

    # 2) Enumerate via fls/istat
    for off in offsets:
        print(f"[INFO] Processing offset {off}", file=sys.stderr)
        lines = run_fls(fls_bin, args.image, off, force_fs=args.force_fs,
                        deleted_only=not args.include_allocated)
        if not lines:
            continue

        if args.debug:
            for raw in lines:
                print(f"[DEBUG] raw: {raw}", file=sys.stderr)

        for ln in lines:
            parsed = parse_fls_long_line(ln, debug=args.debug)
            if not parsed:
                if args.debug:
                    print(f"[DEBUG] parse failed -> {ln}", file=sys.stderr)
                continue

            t = (parsed.get("entry_type") or "").lower()
            lhs, rhs = (t.split("/", 1) + [""])[:2]
            is_regular_file = (lhs == "r") or (rhs == "r")
            if not is_regular_file:
                if args.debug:
                    print(f"[DEBUG] skip: not regular file -> type={t} name={parsed.get('file_name')}", file=sys.stderr)
                continue

            mt = convert_to_epoch(parsed["mtime"]) if parsed["mtime"] else None
            at = convert_to_epoch(parsed["atime"]) if parsed["atime"] else None
            ct = convert_to_epoch(parsed["ctime"]) if parsed["ctime"] else None
            crt = convert_to_epoch(parsed["crtime"]) if parsed["crtime"] else None

            deleted_ts, blocks = gather_istat_info(
                istat_bin, args.image, off, parsed.get("meta"), force_fs=args.force_fs
            )

            norm_name = normalize_request_name(parsed["file_name"], strip_tsk_dup_suffix=args.strip_tsk_dup_suffix)

            entry = {
                "file_name": norm_name,
                "file_size": parsed["file_size"] if parsed["file_size"] is not None else 0,
                "deleted_timestamp": deleted_ts if isinstance(deleted_ts, int) and deleted_ts >= 0 else 0,
                "modified_timestamp": mt if mt is not None else 0,
                "changed_timestamp": ct if ct is not None else 0,
                "accessed_timestamp": at if at is not None else 0,
                "created_timestamp": crt if crt is not None else 0,
                "blocks": blocks if blocks else []
            }

            if args.debug:
                print(f"[DEBUG] + include: {t} {parsed.get('meta')} {norm_name}", file=sys.stderr)

            result["files"].append(entry)
            result["file_count"] = len(result["files"])

    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
