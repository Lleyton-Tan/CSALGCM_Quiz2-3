"""
SEGMENT: READER  (Divide -- data level)
Streams a .txt (space separated) or .csv (comma separated) file of any size in
chunks that never cut a word in half, so memory use stays constant.
The same tokeniser handles both formats: commas, quotes, spaces, tabs and
newlines are all just separators.
"""
import re

from .config import TOKEN_PATTERN, WORD_JOINERS

TOKEN_RE = re.compile(TOKEN_PATTERN)


def is_wordchar(ch):
    return ch.isalpha() or ch in WORD_JOINERS


def tokenize(text):
    """Lowercase `text` and return its list of words."""
    return TOKEN_RE.findall(text.lower())


def iter_chunks(path, chunk_chars, encoding="utf-8"):
    """Yield text chunks that end on a word boundary."""
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
            while cut > 0 and is_wordchar(buf[cut - 1]):
                cut -= 1
            if cut == 0:            # one gigantic token; keep reading
                carry = buf
                continue
            yield buf[:cut]
            carry = buf[cut:]
