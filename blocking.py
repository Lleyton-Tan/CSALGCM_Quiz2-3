"""
SEGMENT: BLOCKING  (Divide -- search level, Greedy rewriting)
Comparing every word with every other is O(V^2).  `skeleton_key` maps a word to
a normal form that erases every alternation the DP accepts, so only words that
share a key ever need to be compared.  The key is built by greedy,
left-to-right, fixed-order rewriting.
"""
from collections import defaultdict

from .config import (KEY_CLASS_MAP, KEY_DROP_CHARS, KEY_REWRITES, VOWELS)

_CLASS = str.maketrans(KEY_CLASS_MAP)
_DROP = str.maketrans("", "", KEY_DROP_CHARS)


def skeleton_key(word):
    for src, dst in KEY_REWRITES:
        if src in word:
            word = word.replace(src, dst)
    out = []
    for ch in word:                       # collapse doubled consonants
        if out and ch == out[-1] and ch not in VOWELS:
            continue
        out.append(ch)
    return "".join(out).translate(_DROP).translate(_CLASS)


def build_buckets(counts, min_len, min_count):
    """Divide the vocabulary into {skeleton_key: [words]}; keep only buckets
    with at least two words."""
    buckets = defaultdict(list)
    for w, c in counts.items():
        if len(w) >= min_len and c >= min_count:
            buckets[skeleton_key(w)].append(w)
    return [ws for ws in buckets.values() if len(ws) >= 2]
