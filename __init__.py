"""
filipino_variants -- extract spelling variants of Filipino words.

Pipeline (one module per segment):

    reader     -> stream the input in word-safe chunks            (Divide)
    dictionary -> load / query the list of valid Filipino words
    counting   -> count + dictionary-filter each chunk, then merge (Conquer)
    blocking   -> skeleton keys split the vocabulary into buckets (Divide, Greedy)
    alignment  -> weighted edit-distance DP between two words     (Dynamic Programming)
    detection  -> compare words bucket by bucket, apply thresholds (Conquer, Greedy)
    output     -> write the CSV
    config     -> every linguistic rule, cost and default threshold
    cli        -> command-line wiring of all segments
"""
