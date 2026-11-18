"""
SEGMENT: CLI
Wires every segment together:
    reader -> dictionary -> counting -> blocking -> alignment -> detection -> output
"""
import argparse
import os
import sys
import time

from .config import DEFAULTS as D
from .counting import count_words
from .detection import find_variants
from .dictionary import load_dictionary
from .output import write_pairs


def build_parser():
    ap = argparse.ArgumentParser(description="Extract Filipino spelling-variant pairs.")
    ap.add_argument("input", help="input .txt (space-separated) or .csv (comma-separated)")
    ap.add_argument("-o", "--output", default=D["output"])
    ap.add_argument("-d", "--dictionary", default=D["dictionary"],
                    help="JSON dictionary of valid Filipino words; other words are discarded")
    ap.add_argument("--no-dictionary", action="store_true", help="disable dictionary filtering")
    ap.add_argument("--encoding", default=D["encoding"])
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1),
                    help="processes for counting (default: min(4, CPUs))")
    ap.add_argument("--chunk-mb", type=int, default=D["chunk_mb"])
    ap.add_argument("--min-len", type=int, default=D["min_len"])
    ap.add_argument("--max-cost", type=float, default=D["max_cost"])
    ap.add_argument("--max-ops", type=int, default=D["max_ops"])
    ap.add_argument("--max-ratio", type=float, default=D["max_ratio"])
    ap.add_argument("--min-count", type=int, default=D["min_count"])
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    t0 = time.time()
    size_mb = os.path.getsize(args.input) / 1e6

    valid_words = None
    if not args.no_dictionary:
        if not os.path.isfile(args.dictionary):
            ap.error(f"dictionary file not found: {args.dictionary} "
                     f"(use -d PATH, or --no-dictionary)")
        valid_words = load_dictionary(args.dictionary)
        print(f"[0/3] Loaded dictionary: {len(valid_words):,} valid words", file=sys.stderr)

    print(f"[1/3] Counting + dictionary-filtering words in {args.input} "
          f"({size_mb:,.1f} MB) ...", file=sys.stderr)
    counts, seen, kept = count_words(args.input, args.chunk_mb * 1_000_000,
                                     args.workers, args.encoding, valid_words)
    pct = 100.0 * kept / seen if seen else 0.0
    print(f"      {seen:,} tokens read; {kept:,} kept ({pct:.1f}%), "
          f"{seen - kept:,} discarded as not in dictionary; "
          f"{len(counts):,} distinct valid words ({time.time() - t0:.1f}s)", file=sys.stderr)

    print("[2/3] Finding spelling variants ...", file=sys.stderr)
    rows = list(find_variants(counts, args.min_len, int(round(args.max_cost * 100)),
                              args.max_ops, args.max_ratio, args.min_count))

    n = write_pairs(rows, args.output)
    print(f"[3/3] Wrote {n:,} pairs to {args.output}", file=sys.stderr)
    print(f"Done in {time.time() - t0:.1f}s", file=sys.stderr)
