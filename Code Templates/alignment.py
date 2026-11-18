from functools import partial

_INF = (10 ** 9, 10 ** 9)
_NAMES = {"-": "hyphen", "'": "apostrophe", "’": "apostrophe"}


def _show(ch):
    return _NAMES.get(ch, ch)


def align(a, b, max_cost, sub_costs=None, indel_costs=None, rules=(),
          double_cost=None, vowels="aeiou"):
    
    sub_costs = sub_costs or {}
    indel_costs = indel_costs or {}
    n, m = len(a), len(b)
    dp = [[_INF] * (m + 1) for _ in range(n + 1)]
    bp = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = (0, 0)

    def relax(i, j, cur, dc, do, pi, pj, desc):
        cand = (cur[0] + dc, cur[1] + do)
        if cand[0] <= max_cost and cand < dp[i][j]:
            dp[i][j] = cand
            bp[i][j] = (pi, pj, desc)

    def doubled(w, k):
        return k > 0 and w[k] == w[k - 1] and w[k] not in vowels and w[k].isalpha()

    for i in range(n + 1):
        for j in range(m + 1):
            cur = dp[i][j]
            if cur == _INF:
                continue
            if i < n and j < m:
                if a[i] == b[j]:                                   
                    relax(i + 1, j + 1, cur, 0, 0, i, j, None)
                else:                                              
                    c = sub_costs.get((a[i], b[j]))
                    if c is not None:
                        relax(i + 1, j + 1, cur, c, 1, i, j, f"{a[i]}->{b[j]}")
            if i < n:                                              
                ch = a[i]
                if ch in indel_costs:
                    relax(i + 1, j, cur, indel_costs[ch], 1, i, j, f"{_show(ch)}->(none)")
                if double_cost is not None and doubled(a, i):
                    relax(i + 1, j, cur, double_cost, 1, i, j, f"{ch}{ch}->{ch}")
            if j < m:                                              
                ch = b[j]
                if ch in indel_costs:
                    relax(i, j + 1, cur, indel_costs[ch], 1, i, j, f"(none)->{_show(ch)}")
                if double_cost is not None and doubled(b, j):
                    relax(i, j + 1, cur, double_cost, 1, i, j, f"{ch}->{ch}{ch}")
            for s, t, c in rules:                                 
                if a.startswith(s, i) and b.startswith(t, j):
                    relax(i + len(s), j + len(t), cur, c, 1, i, j, f"{s}->{t}")

    end = dp[n][m]
    if end == _INF:
        return None
    ops, i, j = [], n, m                                           
    while (i, j) != (0, 0):
        pi, pj, desc = bp[i][j]
        if desc:
            ops.append(desc)
        i, j = pi, pj
    ops.reverse()
    return end[0], end[1], ops


def make_aligner(sub_costs=None, indel_costs=None, rules=(),
                 double_cost=None, vowels="aeiou"):
    """Return `align_fn(a, b, max_cost)` with the knowledge tables bound."""
    return partial(align, sub_costs=sub_costs, indel_costs=indel_costs,
                   rules=list(rules), double_cost=double_cost, vowels=vowels)
