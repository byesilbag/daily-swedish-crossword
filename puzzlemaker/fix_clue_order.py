#!/usr/bin/env python3
"""Puts the clues of two-clue cells in the order the app expects.

The app draws a clue cell's first <clue> in the top half and the second in
the bottom half. The top half belongs to the word that starts in the cell to
the right, the bottom half to the word that starts below (every hand-made
puzzle follows this). generate_puzzle.py used to emit them in slot order, so
about half of its two-clue cells were swapped. This rewrites XML files in
place, touching only the order of <clue> elements.

    python3 scripts/fix_clue_order.py deploy/public/daily/*.xml
"""
import re
import sys

WORD = re.compile(r'<word id="(\d+)" x="(\d+)(?:-\d+)?" y="(\d+)(?:-\d+)?"')
CELL = re.compile(r'(<cell x="(\d+)" y="(\d+)" type="clue"[^>]*>)(.*?)(</cell>)', re.S)
CLUE = re.compile(r'<clue word="(\d+)"[^>]*>.*?</clue>', re.S)


def fix(xml: str) -> tuple[str, int]:
    starts = {m[1]: (int(m[2]), int(m[3])) for m in WORD.finditer(xml)}
    swapped = 0

    def reorder(m):
        nonlocal swapped
        x, y = int(m[2]), int(m[3])
        clues = [c for c in CLUE.finditer(m[4])]
        if len(clues) != 2:
            return m[0]
        if starts.get(clues[0][1]) == (x, y + 1) and starts.get(clues[1][1]) == (x + 1, y):
            swapped += 1
            return m[1] + clues[1][0] + clues[0][0] + m[5]
        return m[0]

    return CELL.sub(reorder, xml), swapped


if __name__ == "__main__":
    total = 0
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            xml = f.read()
        out, n = fix(xml)
        if n:
            with open(path, "w", encoding="utf-8") as f:
                f.write(out)
        total += n
    print(f"{total} cells fixed in {len(sys.argv) - 1} files")
