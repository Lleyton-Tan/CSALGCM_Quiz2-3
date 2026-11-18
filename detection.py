"""
SEGMENT: DETECTION  (Conquer -- search level, Greedy ordering)
Solves each bucket independently: words are ordered greedily by frequency (so
word1 is the dominant form), cheaply pre-filtered by length, aligned with the
DP, and accepted only if they pass the operation / cost / ratio thresholds.
"""
from .alignment import align
from .blocking import build_buckets


def find_variants(counts, min_len=5, max_cost=150, max_ops=2,
                  max_ratio=0.30, min_count=1):
    """Yield (word1, word2, count1, count2, character_difference).
    `max_cost` is in hundredths (150 == 1.5)."""
    for words in build_buckets(counts, min_len, min_count):
        words.sort(key=lambda w: (-counts[w], w))          # greedy: frequent first
        for i in range(len(words) - 1):
            w1 = words[i]
            for j in range(i + 1, len(words)):
                w2 = words[j]
                if abs(len(w1) - len(w2)) > max_ops:       # cheap length filter
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
