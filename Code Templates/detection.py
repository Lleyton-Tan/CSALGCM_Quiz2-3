from .blocking import build_buckets
from .config import COST_SCALE


def find_variants(counts, key_fn, align_fn, min_len=5, max_cost=150, max_ops=2,
                  max_ratio=0.30, min_count=1):

    for words in build_buckets(counts, key_fn, min_len, min_count):
        words.sort(key=lambda w: (-counts[w], w))          
        for i in range(len(words) - 1):
            w1 = words[i]
            for j in range(i + 1, len(words)):
                w2 = words[j]
                if abs(len(w1) - len(w2)) > max_ops:       
                    continue
                res = align_fn(w1, w2, max_cost)
                if res is None:
                    continue
                cost, ops, diff = res
                if ops == 0 or ops > max_ops:
                    continue
                if cost / COST_SCALE / max(len(w1), len(w2)) > max_ratio:
                    continue
                yield (w1, w2, counts[w1], counts[w2], "; ".join(diff))
