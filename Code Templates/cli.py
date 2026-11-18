import argparse
import dataclasses
import os

from .config import VariantConfig
from .pipeline import run_pipeline
from .presets import PRESETS


def build_parser():
    ap = argparse.ArgumentParser(description="Extract spelling-variant pairs.")
    ap.add_argument("input", help="input .txt (space-separated) or .csv (comma-separated)")
    ap.add_argument("-o", "--output", default="spelling_variants.csv")
    ap.add_argument("-d", "--dictionary", default=None,
                    help="optional dictionary (JSON/txt); words not in it are discarded")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--preset", choices=sorted(PRESETS), default="generic")
    src.add_argument("--config", help="JSON file with VariantConfig fields")
    ap.add_argument("--dump-config", metavar="PATH",
                    help="write the effective config to PATH as JSON and exit")
    ap.add_argument("--workers", type=int)
    ap.add_argument("--encoding")
    ap.add_argument("--chunk-mb", type=int)
    ap.add_argument("--min-len", type=int)
    ap.add_argument("--max-cost", type=float, help="in edits, e.g. 1.5")
    ap.add_argument("--max-ops", type=int)
    ap.add_argument("--max-ratio", type=float)
    ap.add_argument("--min-count", type=int)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    cfg = VariantConfig.from_json(a.config) if a.config else PRESETS[a.preset]
    over = {}
    if a.workers is not None:
        over["workers"] = a.workers
    elif cfg.workers == 1:
        over["workers"] = min(4, os.cpu_count() or 1)
    for flag, field in [("encoding", "encoding"), ("min_len", "min_len"),
                        ("max_ops", "max_ops"), ("max_ratio", "max_ratio"),
                        ("min_count", "min_count")]:
        if getattr(a, flag) is not None:
            over[field] = getattr(a, flag)
    if a.chunk_mb is not None:
        over["chunk_chars"] = a.chunk_mb * 1_000_000
    if a.max_cost is not None:
        over["max_cost"] = int(round(a.max_cost * 100))
    cfg = dataclasses.replace(cfg, **over)

    if a.dump_config:
        cfg.to_json(a.dump_config)
        print(f"Config written to {a.dump_config}")
        return
    if a.dictionary and not os.path.isfile(a.dictionary):
        ap.error(f"dictionary file not found: {a.dictionary}")
    run_pipeline(a.input, cfg, a.output, a.dictionary)
