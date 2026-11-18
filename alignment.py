"""
SEGMENT: ALIGNMENT  (Dynamic Programming)
Weighted edit distance between two words with back-tracking.

Cell value = (total_cost, number_of_operations); tuples compare
lexicographically so cheaper, then shorter, alignments win.  Cells whose cost
already exceeds `max_cost` are never expanded (greedy branch-and-bound
pruning), so most non-variants die after a few cells.
"""
from .config import (DOUBLE_CONSONANT_COST, INDEL_COSTS, RULES, SUB_COSTS, VOWELS)

_INF = (10 ** 9, 10 ** 9)
_NAMES = {"-": "hyphen", "'": "apostrophe", "’": "apostrophe"}


def _show(ch):
    return _NAMES.get(ch, ch)


def align(a, b, max_cost):
    """Return (cost, ops, [descriptions]) or None if no alignment <= max_cost.
    Descriptions read from `a` to `b`, e.g. 'o->u', 'tt->t', 'uw->w'."""
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
                        relax(i + 1, j + 1, cur, c, 1, i, j, f"{a[i]}->{b[j]}")
            if i < n:                                              # deletion
                ch = a[i]
                if ch in INDEL_COSTS:
                    relax(i + 1, j, cur, INDEL_COSTS[ch], 1, i, j, f"{_show(ch)}->(none)")
                if i > 0 and ch == a[i - 1] and ch not in VOWELS and ch.isalpha():
                    relax(i + 1, j, cur, DOUBLE_CONSONANT_COST, 1, i, j, f"{ch}{ch}->{ch}")
            if j < m:                                              # insertion
                ch = b[j]
                if ch in INDEL_COSTS:
                    relax(i, j + 1, cur, INDEL_COSTS[ch], 1, i, j, f"(none)->{_show(ch)}")
                if j > 0 and ch == b[j - 1] and ch not in VOWELS and ch.isalpha():
                    relax(i, j + 1, cur, DOUBLE_CONSONANT_COST, 1, i, j, f"{ch}->{ch}{ch}")
            for s, t, c in RULES:                                  # multi-char
                if a.startswith(s, i) and b.startswith(t, j):
                    relax(i + len(s), j + len(t), cur, c, 1, i, j, f"{s}->{t}")

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
