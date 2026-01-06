#!/usr/bin/env python3
from pathlib import Path
import argparse, json, math

def compare_sequential_bytes_and_bits(path_a: str, path_b: str, byte_sample_limit: int = 100):
    """
    Strict lockstep comparison of two files:
      • Byte-by-byte (records first diff byte offset, sample of mismatching byte offsets)
      • Bit-by-bit (MSB→LSB within each byte) to compute:
          - total differing bits
          - bit error rate (BER)
          - first differing bit offset (global bit index)
          - longest contiguous run of matching bits (and fraction of total bits)

    For unequal lengths, the shorter side is treated as 0x00 for the bit pass only,
    so we can compute BER and runs across the entire longer stream. For byte-equality
    runs, we only count when both sides have an actual byte and they’re equal.
    """
    pA, pB = Path(path_a), Path(path_b)
    size_a, size_b = pA.stat().st_size, pB.stat().st_size
    max_size = max(size_a, size_b)
    total_bits = max_size * 8

    # --- Byte-level stats ---
    diff_byte_count = 0
    first_diff_byte = None
    mismatch_byte_offsets_sample = []
    equal_bytes_run_cur = 0
    equal_bytes_run_max = 0

    # --- Bit-level stats ---
    bit_diff_count = 0
    first_diff_bit = None
    equal_bits_run_cur = 0
    equal_bits_run_max = 0
    global_bit_offset = 0  # increases by 8 each byte

    with pA.open("rb") as fa, pB.open("rb") as fb:
        offset = 0
        while True:
            a = fa.read(1)
            b = fb.read(1)
            if not a and not b:
                break  # both EOF

            # ----- BYTE COMPARISON -----
            # For byte equality, only count when both sides have a real byte
            if a and b and a != b:
                diff_byte_count += 1
                if first_diff_byte is None:
                    first_diff_byte = offset
                if len(mismatch_byte_offsets_sample) < byte_sample_limit:
                    mismatch_byte_offsets_sample.append(offset)
                # break any equal-bytes run
                equal_bytes_run_max = max(equal_bytes_run_max, equal_bytes_run_cur)
                equal_bytes_run_cur = 0
            elif a and b and a == b:
                equal_bytes_run_cur += 1
            else:
                # unequal lengths at this byte position -> counts as a mismatch byte
                diff_byte_count += 1
                if first_diff_byte is None:
                    first_diff_byte = offset
                if len(mismatch_byte_offsets_sample) < byte_sample_limit:
                    mismatch_byte_offsets_sample.append(offset)
                equal_bytes_run_max = max(equal_bytes_run_max, equal_bytes_run_cur)
                equal_bytes_run_cur = 0

            # ----- BIT COMPARISON & CONTIGUOUS MATCH RUN -----
            # Use 0x00 for missing side so we can cover entire longer stream
            va = a[0] if a else 0
            vb = b[0] if b else 0
            diff = va ^ vb

            # Count differing bits in this byte
            try:
                bit_diff_count += diff.bit_count()          # Python 3.8+
            except AttributeError:
                bit_diff_count += bin(diff).count("1")       # Fallback

            # Walk bits MSB→LSB to find longest contiguous run of equal bits
            # A bit is equal when the corresponding bit in 'diff' is 0.
            for bit in range(7, -1, -1):
                equal_bit = ((diff >> bit) & 1) == 0
                if equal_bit:
                    equal_bits_run_cur += 1
                else:
                    if first_diff_bit is None:
                        # global bit index: offset*8 + (7 - bit) for MSB→LSB
                        first_diff_bit = (offset * 8) + (7 - bit)
                    if equal_bits_run_cur > equal_bits_run_max:
                        equal_bits_run_max = equal_bits_run_cur
                    equal_bits_run_cur = 0

            offset += 1
            global_bit_offset += 8

    # flush trailing runs
    equal_bytes_run_max = max(equal_bytes_run_max, equal_bytes_run_cur)
    equal_bits_run_max = max(equal_bits_run_max, equal_bits_run_cur)

    # Summaries
    byte_equal = (diff_byte_count == 0) and (size_a == size_b)
    byte_similarity = 1.0 if max_size == 0 else (1.0 - (diff_byte_count / max_size))

    if total_bits == 0:
        ber = 0.0
        longest_equal_bits_frac = 1.0
    else:
        ber = bit_diff_count / total_bits
        longest_equal_bits_frac = equal_bits_run_max / total_bits

    return {
        "size_a": size_a,
        "size_b": size_b,
        "byte_level": {
            "equal": byte_equal,
            "first_diff_offset": first_diff_byte,       # byte offset, None if identical
            "diff_byte_count": diff_byte_count,
            "byte_similarity": byte_similarity,         # 1.0 == all bytes identical
            "longest_equal_byte_run": equal_bytes_run_max
        },
        "bit_level": {
            "first_diff_bit_offset": first_diff_bit,    # global bit index, None if identical
            "diff_bit_count": bit_diff_count,
            "bit_error_rate": ber,                      # BER
            "longest_equal_bit_run": equal_bits_run_max,
            "longest_equal_bit_run_fraction": longest_equal_bits_frac
        },
        # "mismatch_byte_offsets_sample": mismatch_byte_offsets_sample
    }

def compare_blocks(path_a: str, path_b: str, block_size: int, align: int = 0, max_list: int = 100):
    """Fixed-size block comparison with optional alignment. Pads last short blocks with zeros."""
    if block_size <= 0:
        raise ValueError("block_size must be > 0")
    if align < 0:
        raise ValueError("block_align must be >= 0")

    pA, pB = Path(path_a), Path(path_b)
    size_a, size_b = pA.stat().st_size, pB.stat().st_size

    eff_a = max(0, size_a - min(align, size_a))
    eff_b = max(0, size_b - min(align, size_b))

    nblocks_a = math.ceil(eff_a / block_size) if eff_a > 0 else 0
    nblocks_b = math.ceil(eff_b / block_size) if eff_b > 0 else 0
    total_blocks = max(nblocks_a, nblocks_b)

    match_blocks = 0
    mismatch_blocks = 0
    first_mismatch_block = None
    mismatch_indices_sample = []
    longest_equal_block_run = 0
    equal_block_run_cur = 0

    with pA.open("rb") as fa, pB.open("rb") as fb:
        fa.seek(min(align, size_a))
        fb.seek(min(align, size_b))

        for bi in range(total_blocks):
            a = fa.read(block_size) if bi < nblocks_a else b""
            b = fb.read(block_size) if bi < nblocks_b else b""

            if len(a) < block_size: a += b"\x00" * (block_size - len(a))
            if len(b) < block_size: b += b"\x00" * (block_size - len(b))

            if a == b:
                match_blocks += 1
                equal_block_run_cur += 1
            else:
                mismatch_blocks += 1
                if first_mismatch_block is None:
                    first_mismatch_block = bi
                if len(mismatch_indices_sample) < max_list:
                    mismatch_indices_sample.append(bi)
                longest_equal_block_run = max(longest_equal_block_run, equal_block_run_cur)
                equal_block_run_cur = 0

    longest_equal_block_run = max(longest_equal_block_run, equal_block_run_cur)
    block_match_rate = 1.0 if total_blocks == 0 else match_blocks / total_blocks

    return {
        "mode": "block_level",
        "block_size": block_size,
        "block_align": align,
        "total_blocks_compared": total_blocks,
        "matching_blocks": match_blocks,
        "mismatching_blocks": mismatch_blocks,
        "first_mismatch_block_index": first_mismatch_block,
        # "mismatch_block_indices_sample": mismatch_indices_sample,
        "block_match_rate": block_match_rate,
        "longest_equal_block_run": longest_equal_block_run,
        "longest_equal_block_run_fraction": (0.0 if total_blocks == 0 else longest_equal_block_run / total_blocks)
    }

def main():
    ap = argparse.ArgumentParser(
        description="Sequential byte+bit comparison with continuous bit-run stats, plus optional block-level comparison."
    )
    ap.add_argument("file_a")
    ap.add_argument("file_b")
    ap.add_argument("--byte-sample-limit", type=int, default=100,
                    help="Max mismatching byte offsets to include in sample (default: 100).")
    ap.add_argument("--block-size", type=int, default=0,
                    help="Enable block-level comparison with this block size (e.g., 4096). Omit or set 0 to skip.")
    ap.add_argument("--block-align", type=int, default=0,
                    help="Alignment offset (bytes) for block comparison (default: 0).")
    ap.add_argument("--block-list-max", type=int, default=100,
                    help="Max mismatching block indices to include in sample (default: 100).")
    args = ap.parse_args()

    result = {
        "path_a": str(Path(args.file_a).resolve()),
        "path_b": str(Path(args.file_b).resolve()),
        "sequential_compare": compare_sequential_bytes_and_bits(
            args.file_a, args.file_b, byte_sample_limit=args.byte_sample_limit
        ),
    }

    if args.block_size and args.block_size > 0:
        result["block_compare"] = compare_blocks(
            args.file_a, args.file_b,
            block_size=args.block_size,
            align=args.block_align,
            max_list=args.block_list_max,
        )

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
