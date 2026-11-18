import re
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor

from .dictionary import make_validator
from .reader import iter_chunks


def count_text(text, token_re, lowercase=True, is_valid=None):

    counts = Counter(token_re.findall(text.lower() if lowercase else text))
    seen = sum(counts.values())
    if is_valid is not None:
        counts = Counter({w: c for w, c in counts.items() if is_valid(w)})
    return counts, seen, sum(counts.values())



_STATE = None


def _init_worker(token_pattern, lowercase, valid_words, ignore_chars):
    global _STATE
    _STATE = (re.compile(token_pattern), lowercase,
              make_validator(valid_words, ignore_chars))


def _worker_count(chunk):
    return count_text(chunk, *_STATE)


def count_words(path, token_pattern, word_joiners="", chunk_chars=16_000_000,
                workers=1, encoding="utf-8", lowercase=True,
                valid_words=None, ignore_chars=""):
    """REDUCE step.  Returns (Counter, tokens_seen, tokens_kept)."""
    total, seen, kept = Counter(), 0, 0
    chunks = iter_chunks(path, chunk_chars, encoding, word_joiners)

    def merge(res):
        nonlocal seen, kept
        c, s_, k_ = res
        total.update(c)
        seen += s_
        kept += k_

    if workers <= 1:
        _init_worker(token_pattern, lowercase, valid_words, ignore_chars)
        for ch in chunks:
            merge(_worker_count(ch))
        return total, seen, kept

    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker,
                             initargs=(token_pattern, lowercase, valid_words,
                                       ignore_chars)) as ex:
        pending = deque()
        for ch in chunks:
            pending.append(ex.submit(_worker_count, ch))
            if len(pending) >= workers * 2:
                merge(pending.popleft().result())
        while pending:
            merge(pending.popleft().result())
    return total, seen, kept
