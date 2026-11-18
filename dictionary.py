"""
SEGMENT: DICTIONARY
Loads the dictionary of valid Filipino words and answers "is this a word?".
The dictionary is held in a per-process global so worker processes can load it
once (via an initializer) instead of receiving it with every chunk.
"""
import json

_DICT = None                                 # None => no filtering
_STRIP = str.maketrans("", "", "-'’")


def load_dictionary(path):
    """
    Return a lowercase set of words.  Accepts {"data": [...]}, any JSON object
    holding word lists, a bare JSON list, or a plain text file (one per line).
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
    return {w.strip().lower() for w in words if w.strip()}


def set_dictionary(dictionary):
    """Install the dictionary for this process (also the worker initializer)."""
    global _DICT
    _DICT = dictionary


def filtering_enabled():
    return _DICT is not None


def is_valid(word):
    """In the dictionary?  Hyphens/apostrophes are ignored for the lookup
    ('mag-aral' matches 'magaral') but the word itself is kept as written."""
    return word in _DICT or word.translate(_STRIP) in _DICT
