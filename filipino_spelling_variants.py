#!/usr/bin/env python3
"""
Filipino spelling-variant extractor
===================================

Reads a large (up to ~1 GB+) .txt (space-separated) or .csv (comma-separated)
file of Filipino words and writes a CSV of word pairs that are *spelling
variants of the same lexical item*.

A dictionary of valid Filipino words (JSON, e.g. tagalog_dict.json) is used to
discard every word of the dataset that is not in it BEFORE any pairing happens.

Output columns:
    word1, word2, word1_count, word2_count, character_difference

Usage:
    python filipino_spelling_variants.py input.txt -d tagalog_dict.json -o variants.csv
    python filipino_spelling_variants.py big.csv -d tagalog_dict.json -o variants.csv --workers 4

ALGORITHM OVERVIEW
------------------
1. DIVIDE AND CONQUER (data level) -- The file is never loaded whole.  It is
   divided into chunks (split only at word boundaries).  Each chunk is solved
   independently (optionally in parallel): its words are counted and then
   FILTERED AGAINST THE DICTIONARY, so only valid Filipino words survive.
   The partial, already-filtered Counters are merged (map-reduce).  Filtering
   inside the conquer step keeps every partial result, and the merged
   vocabulary, small.

2. DIVIDE AND CONQUER (search level) -- Comparing every word with every other
   word is O(V^2).  Instead the vocabulary is divided into small buckets by a
   "skeleton key": a normal form that erases the orthographic alternations
   known to produce variants (o/u, e/i, k/c, ph/f, doubled consonants, ...).
   Only words inside the same bucket are ever compared; buckets are solved
   independently and their results merged.

3. DYNAMIC PROGRAMMING -- Inside a bucket, two words are aligned with a
   *weighted* edit-distance DP (Needleman-Wunsch / Levenshtein style) whose
   cost table encodes linguistic knowledge: cheap, attested alternations
   (o<->u 0.5, k<->c 0.5, ...) vs. forbidden edits (any other substitution or
   insertion/deletion costs 2.0, which is above the acceptance threshold).
   The DP table also supports back-tracking, which yields the human readable
   `character_difference` (e.g. "o->u", "k->c; tt->t").

4. GREEDY -- (a) The skeleton key is computed by greedy, longest-match-first
   left-to-right rewriting.  (b) Words in a bucket are ordered greedily by
   frequency, so word1 is always the more frequent (the "dominant") form.
   (c) The DP is relaxed with greedy branch-and-bound pruning: any cell whose
   accumulated cost already exceeds the threshold is dropped, so most
   non-variant pairs are rejected after a handful of cells.

WHY THE EXAMPLES BEHAVE AS REQUIRED
-----------------------------------
 politiko / pulitiko : one o->u substitution (cost 0.5)             -> variant
 opo / upo           : only 3 letters; one vowel swap there changes
                       identity (minimum-length guard, --min-len)   -> rejected
 polittico / pulitiko: o->u (0.5) + tt->t (1.25) + c->k (0.5) = 2.25,
                       3 edit operations, above the 1.5 / 2-op limit -> rejected
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor

# --------------------------------------------------------------------------- #
# 1. Linguistic knowledge (all costs in hundredths so arithmetic is exact)
# --------------------------------------------------------------------------- #
VOWELS = set("aeiou")

# Attested single-letter alternations in Filipino orthography.
SUB_COSTS = {}
for _a, _b, _c in [
    ("o", "u", 50),   # politiko / pulitiko
    ("e", "i", 50),   # lalake / lalaki
    ("k", "c", 50),   # kultura / cultura
    ("f", "p", 50),   # pilipino / filipino
    ("c", "s", 75),   # sine / cine
    ("d", "r", 75),   # dito / rito
    ("b", "v", 75),   # bapor / vapor
]:
    SUB_COSTS[(_a, _b)] = _c
    SUB_COSTS[(_b, _a)] = _c

# Multi-character correspondences: (string in A, string in B, cost)
_RULES = [
    ("ph", "f", 50),   # telepono / telefono-style
    ("ny", "ñ", 50),   # senyora / señora
    ("ks", "x", 50),   # taksi / taxi
    ("ts", "ch", 50),  # tsokolate / chokolate
    ("uw", "w", 50),   # kuwento / kwento
    ("ow", "w", 50),
    ("iy", "y", 50),   # kasiya / kasya-style
    ("ey", "y", 50),
]
RULES = []
for _s, _t, _c in _RULES:
    RULES.append((_s, _t, _c))
    RULES.append((_t, _s, _c))

# Insertion/deletion of these symbols is allowed at a small cost.
# NOTE: y and w are deliberately NOT here.  Inserting/deleting them (alone or as a
# y<->w swap) changes the word: gawan != gayan.  Only the glide spellings in RULES
# (uw/w, ow/w, iy/y, ey/y) are accepted, e.g. kuwento / kwento.
INDEL_COSTS = {"h": 75, "-": 50, "'": 50, "’": 50}
DOUBLE_CONSONANT_COST = 125      # tt <-> t (only acceptable as the sole edit)
FORBIDDEN = 200                  # any non-attested edit (exceeds every threshold)

# --------------------------------------------------------------------------- #
# 2. Reading the input (streaming, chunked, divide & conquer / map-reduce)
# --------------------------------------------------------------------------- #
# Words = letters, optionally joined by internal hyphen/apostrophe.
# Splitting on this regex handles BOTH "space separated" txt and
# "comma separated" csv (commas, quotes, newlines, tabs are all separators).
TOKEN_RE = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*")


def _is_wordchar(ch):
    return ch.isalpha() or ch in "-'’"


def iter_chunks(path, chunk_chars, encoding):
    """Yield text chunks that never cut a word in half (constant memory)."""
    with open(path, "r", encoding=encoding, errors="replace", newline="") as f:
        carry = ""
        while True:
            data = f.read(chunk_chars)
            if not data:
                if carry:
                    yield carry
                return
            buf = carry + data
            cut = len(buf)
            while cut > 0 and _is_wordchar(buf[cut - 1]):
                cut -= 1
            if cut == 0:            # one gigantic token; keep reading
                carry = buf
                continue
            yield buf[:cut]
            carry = buf[cut:]


def load_dictionary(path):
    """
    Load the dictionary of valid Filipino words into a lowercase set.
    Accepts {"data": [...]}, any JSON object holding word lists, a bare JSON
    list, or a plain text file (one word per line).
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    words = []
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        words = raw.split()
    else:
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, str):
                words.append(cur)
            elif isinstance(cur, list):
                stack.extend(cur)
            elif isinstance(cur, dict):
                stack.extend(cur.values())
    out = set()
    for w in words:
        w = w.strip().lower()
        if w:
            out.add(w)
    return out


_DICT = None            # per-process dictionary (None => no filtering)
_STRIP = str.maketrans("", "", "-'’")


def _init_worker(dictionary):
    global _DICT
    _DICT = dictionary


def _is_valid(word):
    """A word is valid if it is in the dictionary.  Hyphens/apostrophes are
    ignored for the lookup (the dictionary stores 'magaral', the text may
    contain 'mag-aral'); the word itself is kept exactly as written."""
    return word in _DICT or word.translate(_STRIP) in _DICT


def count_chunk(chunk):
    """
    Conquer step for ONE chunk: tokenise, count (case-insensitive), then drop
    every distinct word that is not in the dictionary.
    Returns (filtered_counter, tokens_seen, tokens_kept).
    """
    counts = Counter(TOKEN_RE.findall(chunk.lower()))
    seen = sum(counts.values())
    if _DICT is not None:
        # filter distinct words only (far cheaper than filtering every token)
        counts = Counter({w: c for w, c in counts.items() if _is_valid(w)})
    return counts, seen, sum(counts.values())


def count_words(path, chunk_chars=16_000_000, workers=1, encoding="utf-8",
                dictionary=None):
    """Divide the file into chunks, count+filter each, merge partial results.
    Returns (Counter, tokens_seen, tokens_kept)."""
    total, seen, kept = Counter(), 0, 0
    chunks = iter_chunks(path, chunk_chars, encoding)

    def merge(res):
        nonlocal seen, kept
        c, s_, k_ = res
        total.update(c)
        seen += s_
        kept += k_

    if workers <= 1:
        _init_worker(dictionary)
        for ch in chunks:
            merge(count_chunk(ch))
        return total, seen, kept
    # Bounded in-flight window keeps memory low even for multi-GB inputs.
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker,
                             initargs=(dictionary,)) as ex:
        pending = deque()
        for ch in chunks:
            pending.append(ex.submit(count_chunk, ch))
            if len(pending) >= workers * 2:
                merge(pending.popleft().result())
        while pending:
            merge(pending.popleft().result())
    return total, seen, kept


# --------------------------------------------------------------------------- #
# 3. Divide & conquer on the vocabulary: skeleton keys (greedy rewriting)
# --------------------------------------------------------------------------- #
# Applied greedily, left to right, in this fixed order.
_KEY_REWRITES = [
    ("ñ", "ny"), ("x", "ks"), ("ph", "f"), ("ch", "ts"),
    ("uw", "w"), ("ow", "w"), ("iy", "y"), ("ey", "y"),
]
_KEY_CLASS = str.maketrans({"o": "u", "e": "i", "c": "k", "s": "k",
                            "f": "p", "d": "r", "v": "b"})
_KEY_DROP = str.maketrans("", "", "h-'’")


def skeleton_key(word):
    """Normal form that is identical for every word the DP could accept."""
    for src, dst in _KEY_REWRITES:
        if src in word:
            word = word.replace(src, dst)
    out = []
    for ch in word:                       # collapse doubled consonants
        if out and ch == out[-1] and ch not in VOWELS:
            continue
        out.append(ch)
    return "".join(out).translate(_KEY_DROP).translate(_KEY_CLASS)


# --------------------------------------------------------------------------- #
# 4. Dynamic programming: weighted alignment with back-tracking
# --------------------------------------------------------------------------- #
_INF = (10 ** 9, 10 ** 9)


def _show(ch):
    return {"-": "hyphen", "'": "apostrophe", "’": "apostrophe"}.get(ch, ch)


def align(a, b, max_cost):
    """
    Weighted edit-distance DP between a and b.
    Cell value = (total_cost, number_of_operations); tuples compare
    lexicographically, so cheaper (then shorter) alignments win.

    Cells whose cost already exceeds `max_cost` are never expanded (greedy
    branch-and-bound pruning).  Returns (cost, ops, [descriptions]) or None.
    """
    n, m = len(a), len(b)
    dp = [[_INF] * (m + 1) for _ in range(n + 1)]
    bp = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = (0, 0)

    def relax(i, j, cur, dc, do, pi, pj, desc):
        cand = (cur[0] + dc, cur[1] + do)
        if cand[0] <= max_cost and cand < dp[i][j]:
            dp[i][j] = cand
            bp[i][j] = (pi, pj, desc)

    for i in range(n + 1):
        for j in range(m + 1):
            cur = dp[i][j]
            if cur == _INF:
                continue
            if i < n and j < m:
                if a[i] == b[j]:                                   # match
                    relax(i + 1, j + 1, cur, 0, 0, i, j, None)
                else:                                              # substitution
                    c = SUB_COSTS.get((a[i], b[j]))
                    if c is not None:
                        relax(i + 1, j + 1, cur, c, 1, i, j, f"{a[i]} vs. {b[j]}")
            if i < n:                                              # deletion
                ch = a[i]
                if ch in INDEL_COSTS:
                    relax(i + 1, j, cur, INDEL_COSTS[ch], 1, i, j, f"{_show(ch)} vs. (none)")
                if i > 0 and ch == a[i - 1] and ch not in VOWELS and ch.isalpha():
                    relax(i + 1, j, cur, DOUBLE_CONSONANT_COST, 1, i, j, f"{ch}{ch} vs. {ch}")
            if j < m:                                              # insertion
                ch = b[j]
                if ch in INDEL_COSTS:
                    relax(i, j + 1, cur, INDEL_COSTS[ch], 1, i, j, f"(none) vs. {_show(ch)}")
                if j > 0 and ch == b[j - 1] and ch not in VOWELS and ch.isalpha():
                    relax(i, j + 1, cur, DOUBLE_CONSONANT_COST, 1, i, j, f"{ch} vs. {ch}{ch}")
            for s, t, c in RULES:                                  # multi-char
                if a.startswith(s, i) and b.startswith(t, j):
                    relax(i + len(s), j + len(t), cur, c, 1, i, j, f"{s} vs. {t}")

    end = dp[n][m]
    if end == _INF:
        return None
    ops, i, j = [], n, m                                           # back-track
    while (i, j) != (0, 0):
        pi, pj, desc = bp[i][j]
        if desc:
            ops.append(desc)
        i, j = pi, pj
    ops.reverse()
    return end[0], end[1], ops


# --------------------------------------------------------------------------- #
# 5. Variant detection
# --------------------------------------------------------------------------- #
def find_variants(counts, min_len=5, max_cost=150, max_ops=2,
                  max_ratio=0.30, min_count=1):
    # --- Divide: bucket the vocabulary by skeleton key ---
    buckets = defaultdict(list)
    for w, c in counts.items():
        if len(w) >= min_len and c >= min_count:
            buckets[skeleton_key(w)].append(w)

    # --- Conquer: verify pairs inside each bucket only ---
    for words in buckets.values():
        if len(words) < 2:
            continue
        # Greedy ordering: most frequent first => word1 is the dominant form.
        words.sort(key=lambda w: (-counts[w], w))
        for i in range(len(words) - 1):
            w1 = words[i]
            for j in range(i + 1, len(words)):
                w2 = words[j]
                if abs(len(w1) - len(w2)) > max_ops:         # cheap length filter
                    continue
                res = align(w1, w2, max_cost)
                if res is None:
                    continue
                cost, ops, diff = res
                if ops == 0 or ops > max_ops:
                    continue
                if cost / 100.0 / max(len(w1), len(w2)) > max_ratio:
                    continue
                yield (w1, w2, counts[w1], counts[w2], "; ".join(diff))


# --------------------------------------------------------------------------- #
# 6. CLI
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Extract Filipino spelling-variant pairs.")
    ap.add_argument("input", help="input .txt (space-separated) or .csv (comma-separated)")
    ap.add_argument("-o", "--output", default="spelling_variants.csv")
    ap.add_argument("-d", "--dictionary", default="tagalog_dict.json",
                    help="JSON dictionary of valid Filipino words; words of the "
                         "dataset not in it are discarded (default: tagalog_dict.json)")
    ap.add_argument("--no-dictionary", action="store_true",
                    help="disable dictionary filtering")
    ap.add_argument("--encoding", default="utf-8")
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1),
                    help="processes for counting (default: min(4, CPUs))")
    ap.add_argument("--chunk-mb", type=int, default=16,
                    help="characters (millions) read per chunk (default 16)")
    ap.add_argument("--min-len", type=int, default=5,
                    help="shorter words are never paired, e.g. opo/upo (default 5)")
    ap.add_argument("--max-cost", type=float, default=1.5,
                    help="max total weighted edit cost (default 1.5)")
    ap.add_argument("--max-ops", type=int, default=2,
                    help="max number of edit operations (default 2)")
    ap.add_argument("--max-ratio", type=float, default=0.30,
                    help="max cost per letter of the longer word (default 0.30)")
    ap.add_argument("--min-count", type=int, default=1,
                    help="ignore words occurring fewer times than this (default 1)")
    args = ap.parse_args()

    t0 = time.time()
    size_mb = os.path.getsize(args.input) / 1e6
    dictionary = None
    if not args.no_dictionary:
        if not os.path.isfile(args.dictionary):
            ap.error(f"dictionary file not found: {args.dictionary} "
                     f"(use -d PATH, or --no-dictionary)")
        dictionary = load_dictionary(args.dictionary)
        print(f"[0/3] Loaded dictionary: {len(dictionary):,} valid words", file=sys.stderr)
    print(f"[1/3] Counting + dictionary-filtering words in {args.input} "
          f"({size_mb:,.1f} MB) ...", file=sys.stderr)
    counts, seen, kept = count_words(args.input, args.chunk_mb * 1_000_000,
                                     args.workers, args.encoding, dictionary)
    pct = 100.0 * kept / seen if seen else 0.0
    print(f"      {seen:,} tokens read; {kept:,} kept ({pct:.1f}%), "
          f"{seen - kept:,} discarded as not in dictionary; "
          f"{len(counts):,} distinct valid words ({time.time() - t0:.1f}s)",
          file=sys.stderr)

    print("[2/3] Finding spelling variants ...", file=sys.stderr)
    rows = list(find_variants(counts, args.min_len, int(round(args.max_cost * 100)),
                              args.max_ops, args.max_ratio, args.min_count))
    rows.sort(key=lambda r: (-(r[2] + r[3]), r[0], r[1]))

    print(f"[3/3] Writing {len(rows):,} pairs to {args.output}", file=sys.stderr)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["word1", "word2", "word1_count", "word2_count", "character_difference"])
        wr.writerows(rows)
    print(f"Done in {time.time() - t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
