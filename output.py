"""
SEGMENT: OUTPUT
Sorts the accepted pairs and writes the result CSV.
"""
import csv

HEADER = ["word1", "word2", "word1_count", "word2_count", "character_difference"]


def write_pairs(rows, path):
    rows = sorted(rows, key=lambda r: (-(r[2] + r[3]), r[0], r[1]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(HEADER)
        wr.writerows(rows)
    return len(rows)
