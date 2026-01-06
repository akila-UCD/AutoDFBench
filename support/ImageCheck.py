#!/usr/bin/env python3
# support/ImageCheck.py
from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
from collections import Counter, defaultdict
from functools import lru_cache

# NEW: pHash deps
import numpy as np
from PIL import Image as PILImage

try:
    _popcount = int.bit_count
except AttributeError:  # pragma: no cover
    def _popcount(n: int) -> int:
        return bin(n).count("1")

@dataclass
class _Block:
    index: int
    offset: int
    size: int
    hexdigest: str

@dataclass
class _Match:
    carved_index: int
    carved_offset: int
    size: int
    orig_index: int
    orig_offset: int
    hexdigest: str

def _sha256_hex(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

# --------------------------- pHash utilities (NEW) ---------------------------

@lru_cache(maxsize=16_384)
def _dct_matrix(n: int) -> np.ndarray:
    """DCT-II transform matrix (orthonormal)."""
    k = np.arange(n)[:, None]
    n0 = np.arange(n)[None, :]
    M = np.cos((np.pi / n) * (n0 + 0.5) * k)
    M[0, :] = 1 / np.sqrt(n)
    M[1:, :] *= np.sqrt(2 / n)
    return M

def _dct2(a: np.ndarray) -> np.ndarray:
    n, m = a.shape
    Cn = _dct_matrix(n)
    Cm = _dct_matrix(m)
    return Cn @ a @ Cm.T

def _bits_to_hex(bits: np.ndarray) -> str:
    """Pack boolean array (length 64) into 16-char hex."""
    v = 0
    for b in bits.astype(np.uint8):
        v = (v << 1) | int(b)
    return f"{v:016x}"

@lru_cache(maxsize=16_384)
def _phash_hex(path: str, hash_size: int = 8, highfreq_factor: int = 4) -> Optional[str]:
    """
    Perceptual hash (pHash) => 64-bit hex.
    - Resize to (hash_size*highfreq_factor)^2 (default 32x32)
    - 2D DCT, take top-left (hash_size x hash_size)
    - Threshold by median (excluding DC)
    """
    try:
        with PILImage.open(path) as im:
            im = im.convert("L").resize(
                (hash_size * highfreq_factor, hash_size * highfreq_factor),
                PILImage.Resampling.LANCZOS
            )
            A = np.asarray(im, dtype=np.float32)
    except Exception:
        return None

    dct = _dct2(A)
    low = dct[:hash_size, :hash_size].copy()
    flat = low.flatten()
    # Exclude DC (flat[0]) from median
    med = np.median(flat[1:]) if flat.size > 1 else flat[0]
    bits = flat > med
    # Force length 64 even if hash_size changed
    if bits.size >= 64:
        bits = bits[:64]
    else:
        bits = np.pad(bits, (0, 64 - bits.size), constant_values=False)
    return _bits_to_hex(bits)

def _hamming_hex(h1: Optional[str], h2: Optional[str]) -> Optional[int]:
    if not h1 or not h2:
        return None
    try:
        return (int(h1, 16) ^ int(h2, 16)).bit_count()
    except Exception:
        return None

# --------------------------- Block iter/index/match ---------------------------

def _iter_blocks(path: str, block_size: int, stride: Optional[int],
                 include_partial: bool, ignore_zero: bool) -> Iterable[_Block]:
    stride = block_size if stride is None else stride
    if stride <= 0 or block_size <= 0:
        raise ValueError("block_size and stride must be positive")

    fsize = os.path.getsize(path)
    idx = 0
    with open(path, "rb") as f:
        pos = 0
        while pos < fsize:
            f.seek(pos)
            chunk = f.read(block_size)
            if not chunk:
                break
            actual = len(chunk)
            if actual < block_size and not include_partial:
                break
            if ignore_zero and chunk == b"\x00" * actual:
                pos += stride
                idx += 1
                continue
            yield _Block(index=idx, offset=pos, size=actual, hexdigest=_sha256_hex(chunk))
            pos += stride
            idx += 1

def _build_lookup(blocks: Iterable[_Block]) -> Dict[Tuple[int, str], List[_Block]]:
    table: Dict[Tuple[int, str], List[_Block]] = defaultdict(list)
    for b in blocks:
        table[(b.size, b.hexdigest)].append(b)
    return table

def _find_matches(lookup: Dict[Tuple[int, str], List[_Block]],
                  carved_blocks: Iterable[_Block]) -> List[_Match]:
    out: List[_Match] = []
    for cb in carved_blocks:
        key = (cb.size, cb.hexdigest)
        if key in lookup:
            for ob in lookup[key]:
                out.append(_Match(
                    carved_index=cb.index,
                    carved_offset=cb.offset,
                    size=cb.size,
                    orig_index=ob.index,
                    orig_offset=ob.offset,
                    hexdigest=cb.hexdigest
                ))
    return out

def _best_alignment_offset(matches: List[_Match]) -> Tuple[int, int]:
    if not matches:
        return (0, 0)
    ctr = Counter(m.orig_offset - m.carved_offset for m in matches)
    off, votes = ctr.most_common(1)[0]
    return off, votes

def _select_alignment(matches: List[_Match], best_off: int, tol: int = 0) -> List[_Match]:
    return [m for m in matches if abs((m.orig_offset - m.carved_offset) - best_off) <= tol]

def _longest_contiguous_run_blocks(matches: List[_Match], stride: int) -> int:
    if not matches:
        return 0
    ms = sorted(matches, key=lambda x: (x.carved_offset, x.orig_offset))
    longest, cur = 1, 1
    for i in range(1, len(ms)):
        a, b = ms[i-1], ms[i]
        if (b.carved_offset - a.carved_offset == stride) and (b.orig_offset - a.orig_offset == stride):
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 1
    return longest

def _coverage_unique_bytes(matches: List[_Match]) -> Tuple[int, int]:
    if not matches:
        return 0, 0
    intervals = sorted((m.orig_offset, m.orig_offset + m.size) for m in matches)
    total = 0
    longest = 0
    cur_s, cur_e = intervals[0]
    for s, e in intervals[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            seg = cur_e - cur_s
            total += seg
            longest = max(longest, seg)
            cur_s, cur_e = s, e
    seg = cur_e - cur_s
    total += seg
    longest = max(longest, seg)
    return total, longest

# --------------------------- BER + sequential bytes ---------------------------

def _bit_error_rate(orig_path: str, carved_path: str, best_off: int, chunk: int = 1 << 20) -> Tuple[int, int, float]:
    o_size = os.path.getsize(orig_path)
    c_size = os.path.getsize(carved_path)
    if best_off >= 0:
        c_start, o_start = 0, best_off
    else:
        c_start, o_start = -best_off, 0
    o_tail = max(0, o_size - o_start)
    c_tail = max(0, c_size - c_start)
    overlap = min(o_tail, c_tail)
    if overlap <= 0:
        return (0, 0, 0.0)
    diff_bits = 0
    total_bits = 0
    with open(orig_path, "rb") as fo, open(carved_path, "rb") as fc:
        fo.seek(o_start); fc.seek(c_start)
        left = overlap
        while left > 0:
            n = min(chunk, left)
            a = fo.read(n); b = fc.read(n)
            if not a or not b:
                break
            for x, y in zip(a, b):
                total_bits += 8
                diff_bits += _popcount(x ^ y)
            left -= n
    rate = (diff_bits / total_bits) if total_bits else 0.0
    return diff_bits, total_bits, rate

def _sequential_byte_compare(orig_path: str, carved_path: str, align_off: int, chunk: int = 1 << 20):
    o_size = os.path.getsize(orig_path)
    c_size = os.path.getsize(carved_path)
    if align_off >= 0:
        o_start, c_start = align_off, 0
    else:
        o_start, c_start = 0, -align_off
    o_tail = max(0, o_size - o_start)
    c_tail = max(0, c_size - c_start)
    total_bytes = max(o_tail, c_tail)
    overlap = min(o_tail, c_tail)
    if total_bytes == 0:
        return {
            "alignment_offset_bytes": align_off,
            "diff_bytes": 0,
            "total_bytes": 0,
            "byte_similarity": 1.0,
            "first_diff_rel": None,
            "first_diff_orig_abs": None,
            "first_diff_carved_abs": None,
            "longest_equal_run": 0,
            "longest_equal_run_fraction": None,
            "orig_start": o_start,
            "carved_start": c_start,
        }
    diff_overlap = 0
    first_diff_rel = None
    longest_equal_run = 0
    cur_equal_run = 0
    with open(orig_path, "rb") as fo, open(carved_path, "rb") as fc:
        fo.seek(o_start); fc.seek(c_start)
        left = overlap; rel_off = 0
        while left > 0:
            n = min(chunk, left)
            a = fo.read(n); b = fc.read(n)
            if not a or not b:
                break
            for i in range(n):
                if a[i] == b[i]:
                    cur_equal_run += 1
                else:
                    diff_overlap += 1
                    if first_diff_rel is None:
                        first_diff_rel = rel_off + i
                    longest_equal_run = max(longest_equal_run, cur_equal_run)
                    cur_equal_run = 0
            rel_off += n
            left -= n
    longest_equal_run = max(longest_equal_run, cur_equal_run)
    trailing = total_bytes - overlap
    diff_bytes = diff_overlap + trailing
    if first_diff_rel is None and trailing > 0:
        first_diff_rel = overlap
    byte_similarity = 1.0 - (diff_bytes / total_bytes)
    longest_equal_run_fraction = (None if total_bytes == 0 else (longest_equal_run / total_bytes))
    if first_diff_rel is not None:
        first_diff_orig_abs = o_start + first_diff_rel
        first_diff_carved_abs = c_start + first_diff_rel
    else:
        first_diff_orig_abs = None
        first_diff_carved_abs = None
    return {
        "alignment_offset_bytes": align_off,
        "diff_bytes": diff_bytes,
        "total_bytes": total_bytes,
        "byte_similarity": byte_similarity,
        "first_diff_rel": first_diff_rel,
        "first_diff_orig_abs": first_diff_orig_abs,
        "first_diff_carved_abs": first_diff_carved_abs,
        "longest_equal_run": longest_equal_run,
        "longest_equal_run_fraction": longest_equal_run_fraction,
        "orig_start": o_start,
        "carved_start": c_start,
    }

# --------------------------- Public interface ---------------------------

class ImageCheck:
    """
    Block-hash alignment + sequential byte/bit comparison + pHash helpers.
    """

    # ---- pHash helpers (NEW) ----
    @staticmethod
    def phash_hex(path: str, hash_size: int = 8, highfreq_factor: int = 4) -> Optional[str]:
        return _phash_hex(path, hash_size=hash_size, highfreq_factor=highfreq_factor)

    @staticmethod
    def phash_hamming(hex1: Optional[str], hex2: Optional[str]) -> Optional[int]:
        return _hamming_hex(hex1, hex2)

    # ---- main compare ----
    @staticmethod
    def block_hash_compare(
        orig_path: str,
        carved_path: str,
        block_size: int = 512,
        stride: Optional[int] = None,
        include_partial: bool = True,
        ignore_zero: bool = True,
    ) -> dict:
        stride = block_size if stride is None else stride
        orig_blocks = list(_iter_blocks(orig_path, block_size, stride, include_partial, ignore_zero))
        carved_blocks = list(_iter_blocks(carved_path, block_size, stride, include_partial, ignore_zero))
        lookup = _build_lookup(orig_blocks)
        cand = _find_matches(lookup, carved_blocks)
        best_off, votes = _best_alignment_offset(cand)
        aligned = _select_alignment(cand, best_off, tol=0)

        matched_carved_idx = {m.carved_index for m in aligned}
        matched_orig_idx   = {m.orig_index   for m in aligned}
        total_unique_bytes, longest_run_bytes = _coverage_unique_bytes(aligned)
        legacy_longest_blocks = _longest_contiguous_run_blocks(aligned, stride)
        block_match_rate = (len(matched_carved_idx) / len(carved_blocks)) if carved_blocks else 0.0

        seq_lock  = _sequential_byte_compare(orig_path, carved_path, align_off=0)
        seq_align = _sequential_byte_compare(orig_path, carved_path, align_off=best_off)

        diff_bits, total_bits, ber = _bit_error_rate(orig_path, carved_path, best_off)
        ber_out = round(ber, 12) if total_bits else None

        gt_bytes = os.path.getsize(orig_path)

        return {
            "params": {
                "block_size": block_size,
                "stride": stride,
                "include_partial": include_partial,
                "ignore_zero": ignore_zero,
            },
            "sizes": {
                "original_bytes": gt_bytes,
                "carved_bytes": os.path.getsize(carved_path),
            },
            "indexing": {
                "original_blocks": len(orig_blocks),
                "carved_blocks": len(carved_blocks),
            },
            "alignment": {
                "total_candidate_matches": len(cand),
                "best_alignment_offset_bytes": best_off,
                "alignment_votes": votes,
                "aligned_matches": len(aligned),
            },
            "matching": {
                "unique_covered_bytes": total_unique_bytes,
                "longest_contiguous_run_bytes": longest_run_bytes,
                "run_coverage_unique": round((longest_run_bytes / gt_bytes) if gt_bytes else 0.0, 6),
                "longest_contiguous_run_blocks": legacy_longest_blocks,
                "block_match_rate": round(block_match_rate, 6),
                "matched_carved_blocks": len(matched_carved_idx),
                "matched_orig_blocks": len(matched_orig_idx),
            },
            # lockstep (zero-offset) view by default
            "sequential_bytes": {
                "mode": "lockstep_zero_offset",
                "alignment_offset_bytes": seq_lock["alignment_offset_bytes"],
                "overlap_start_in_original": seq_lock["orig_start"],
                "overlap_start_in_carved": seq_lock["carved_start"],
                "total_bytes_compared": seq_lock["total_bytes"],
                "diff_byte_count": seq_lock["diff_bytes"],
                "byte_mismatch_rate": (None if seq_lock["total_bytes"] == 0 else round(seq_lock["diff_bytes"] / seq_lock["total_bytes"], 12)),
                "byte_similarity": (None if seq_lock["total_bytes"] == 0 else round(seq_lock["byte_similarity"], 12)),
                "first_diff_rel_offset": seq_lock["first_diff_rel"],
                "first_diff_orig_abs": seq_lock["first_diff_orig_abs"],
                "first_diff_carved_abs": seq_lock["first_diff_carved_abs"],
                "longest_equal_byte_run": seq_lock["longest_equal_run"],
                "longest_equal_byte_run_fraction": seq_lock["longest_equal_run_fraction"],
                "aligned": {  # aligned diagnostics
                    "mode": "aligned_best_offset",
                    "alignment_offset_bytes": seq_align["alignment_offset_bytes"],
                    "overlap_start_in_original": seq_align["orig_start"],
                    "overlap_start_in_carved": seq_align["carved_start"],
                    "total_bytes_compared": seq_align["total_bytes"],
                    "diff_byte_count": seq_align["diff_bytes"],
                    "byte_mismatch_rate": (None if seq_align["total_bytes"] == 0 else round(seq_align["diff_bytes"] / seq_align["total_bytes"], 12)),
                    "byte_similarity": (None if seq_align["total_bytes"] == 0 else round(seq_align["byte_similarity"], 12)),
                    "first_diff_rel_offset": seq_align["first_diff_rel"],
                    "first_diff_orig_abs": seq_align["first_diff_orig_abs"],
                    "first_diff_carved_abs": seq_align["first_diff_carved_abs"],
                    "longest_equal_byte_run": seq_align["longest_equal_run"],
                    "longest_equal_byte_run_fraction": seq_align["longest_equal_run_fraction"],
                }
            },
            "bit_error_rate": {
                "overlap_diff_bits": diff_bits,
                "overlap_total_bits": total_bits,
                "overlap_rate": ber_out,
            },
        }
