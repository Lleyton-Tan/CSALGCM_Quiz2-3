"""
SEGMENT: CONFIG
All linguistic knowledge and tunable defaults live here.  Edit this file to
change which alternations count as spelling variants; no other module needs to
change.  Costs are in hundredths so arithmetic stays exact.
"""

VOWELS = set("aeiou")

# --- Single-letter substitutions that are attested spelling alternations -----
_SUBS = [
    ("o", "u", 50),   # politiko / pulitiko
    ("e", "i", 50),   # lalake / lalaki
    ("k", "c", 50),   # kultura / cultura
    ("f", "p", 50),   # pilipino / filipino
    ("c", "s", 75),   # sine / cine
    ("d", "r", 75),   # dito / rito
    ("b", "v", 75),   # bapor / vapor
]
SUB_COSTS = {}
for _a, _b, _c in _SUBS:
    SUB_COSTS[(_a, _b)] = _c
    SUB_COSTS[(_b, _a)] = _c

# --- Multi-character correspondences: (string in A, string in B, cost) -------
_RULES = [
    ("ph", "f", 50),
    ("ny", "ñ", 50),
    ("ks", "x", 50),
    ("ts", "ch", 50),
    ("uw", "w", 50),   # kuwento / kwento
    ("ow", "w", 50),
    ("iy", "y", 50),   # kasiya / kasya
    ("ey", "y", 50),
]
RULES = []
for _s, _t, _c in _RULES:
    RULES.append((_s, _t, _c))
    RULES.append((_t, _s, _c))

# --- Insertions / deletions --------------------------------------------------
# y and w are deliberately NOT here: gawan != gayan.  Only the glide rules
# above (uw/w, ow/w, iy/y, ey/y) are accepted.
INDEL_COSTS = {"h": 75, "-": 50, "'": 50, "’": 50}
DOUBLE_CONSONANT_COST = 125      # tt <-> t (only acceptable as the sole edit)
FORBIDDEN = 200                  # cost of any non-attested edit (above all limits)

# --- Skeleton-key (blocking) tables -----------------------------------------
# Rewrites applied greedily, left to right, in this order.
KEY_REWRITES = [
    ("ñ", "ny"), ("x", "ks"), ("ph", "f"), ("ch", "ts"),
    ("uw", "w"), ("ow", "w"), ("iy", "y"), ("ey", "y"),
]
KEY_CLASS_MAP = {"o": "u", "e": "i", "c": "k", "s": "k",
                 "f": "p", "d": "r", "v": "b"}
KEY_DROP_CHARS = "h-'’"

# --- Tokenisation ------------------------------------------------------------
# Words = letters, optionally joined by internal hyphen/apostrophe.
TOKEN_PATTERN = r"[^\W\d_]+(?:[-'’][^\W\d_]+)*"
WORD_JOINERS = "-'’"

# --- Default thresholds (also the CLI defaults) -----------------------------
DEFAULTS = {
    "min_len": 5,          # shorter words are never paired (opo/upo)
    "max_cost": 1.5,       # max total weighted edit cost
    "max_ops": 2,          # max number of edit operations
    "max_ratio": 0.30,     # max cost per letter of the longer word
    "min_count": 1,        # ignore words rarer than this
    "chunk_mb": 16,        # million characters per chunk
    "dictionary": "tagalog_dict.json",
    "output": "spelling_variants.csv",
    "encoding": "utf-8",
}
