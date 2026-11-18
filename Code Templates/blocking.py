from collections import defaultdict


def make_key_function(rewrites=(), class_map=None, drop_chars="",
                      collapse_doubles=True, vowels="aeiou"):
    
    class_tbl = str.maketrans(class_map or {})
    drop_tbl = str.maketrans("", "", drop_chars)
    vowel_set = set(vowels)
    rewrites = list(rewrites)

    def key(word):
        for src, dst in rewrites:                 
            if src in word:
                word = word.replace(src, dst)
        if collapse_doubles:                      
            out = []
            for ch in word:
                if out and ch == out[-1] and ch not in vowel_set:
                    continue
                out.append(ch)
            word = "".join(out)
        return word.translate(drop_tbl).translate(class_tbl)   

    return key


def build_buckets(counts, key_fn, min_len=1, min_count=1):
    
    buckets = defaultdict(list)
    for w, c in counts.items():
        if len(w) >= min_len and c >= min_count:
            buckets[key_fn(w)].append(w)
    return [ws for ws in buckets.values() if len(ws) >= 2]
