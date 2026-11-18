"""
SEGMENT: COUNTING  (Conquer -- data level, map-reduce)
Each chunk is solved independently: tokenise, count, then drop every distinct
word that is not in the dictionary.  Partial results are merged into one
Counter.  Chunks can be processed in parallel with a bounded in-flight window.
"""
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor

from . import dictionary
from .reader import iter_chunks, tokenize


def count_chunk(chunk):
    """MAP step for one chunk -> (filtered_counter, tokens_seen, tokens_kept)."""
    counts = Counter(tokenize(chunk))
    seen = sum(counts.values())
    if dictionary.filtering_enabled():
        # filter distinct words only (cheaper than filtering every token)
        counts = Counter({w: c for w, c in counts.items() if dictionary.is_valid(w)})
    return counts, seen, sum(counts.values())


def count_words(path, chunk_chars=16_000_000, workers=1, encoding="utf-8",
                valid_words=None):
    """REDUCE step: merge partial results.  Returns (Counter, seen, kept)."""
    total, seen, kept = Counter(), 0, 0
    chunks = iter_chunks(path, chunk_chars, encoding)

    def merge(res):
        nonlocal seen, kept
        c, s_, k_ = res
        total.update(c)
        seen += s_
        kept += k_

    if workers <= 1:
        dictionary.set_dictionary(valid_words)
        for ch in chunks:
            merge(count_chunk(ch))
        return total, seen, kept

    with ProcessPoolExecutor(max_workers=workers,
                             initializer=dictionary.set_dictionary,
                             initargs=(valid_words,)) as ex:
        pending = deque()
        for ch in chunks:
            pending.append(ex.submit(count_chunk, ch))
            if len(pending) >= workers * 2:
                merge(pending.popleft().result())
        while pending:
            merge(pending.popleft().result())
    return total, seen, kept
