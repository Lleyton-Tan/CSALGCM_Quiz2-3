def is_wordchar(ch, word_joiners=""):
    
    return ch.isalpha() or ch in word_joiners


def iter_chunks(path, chunk_chars, encoding="utf-8", word_joiners=""):
    
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
            while cut > 0 and is_wordchar(buf[cut - 1], word_joiners):
                cut -= 1
            if cut == 0:            
                carry = buf
                continue
            yield buf[:cut]
            carry = buf[cut:]
