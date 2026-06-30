"""Training-side text filtering — NOT used for eval scoring.

At **eval** we transliterate model output to Latin and keep every sample (we
expect Latin transcripts from the systems under test), so the eval presets
(`normalize_reference` / `normalize_hypothesis`) never drop anything.

At **training**, a transcript containing non-Uzbek-Latin letters (stray Cyrillic
like ы/щ, Arabic, CJK, accented Latin) almost always signals a wrong/foreign
label. This module detects (and optionally drops) such samples. Punctuation,
digits, whitespace and the okina (ʻ) are ignored — only *letters* outside the
Uzbek-Latin alphabet flag a sample.

CLI (also `python -m uzbek_text_norm.training`)::

    uzbek-train-filter train.jsonl                 # report only
    uzbek-train-filter train.jsonl --write         # -> train.latin.jsonl + train.nonlatin.jsonl
    uzbek-train-filter train.jsonl --write --transliterate-cyrillic
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter
from typing import Set

from . import __version__
from .core import cyrillic_to_latin

# Uzbek Latin alphabet (lowercase base letters).
UZBEK_LATIN = set("abcdefghijklmnopqrstuvwxyz")
# Non-letters that are legitimate in Uzbek text and must never flag a sample.
_IGNORE = set(" -'ʻʼ‘’`")


def non_latin_letters(text: str) -> Set[str]:
    """Return the set of *letter* characters in ``text`` outside Uzbek-Latin.

    Ignores spaces, digits, punctuation/symbols and apostrophe variants — those
    are handled by normal cleaning and do not indicate a foreign transcript.
    """
    bad = set()
    for ch in (text or "").lower():
        if ch in UZBEK_LATIN or ch in _IGNORE or ch.isspace() or ch.isdigit():
            continue
        if unicodedata.category(ch).startswith("L"):  # any letter not in the alphabet
            bad.add(ch)
    return bad


def is_uzbek_latin(text: str) -> bool:
    """True if ``text`` contains no non-Uzbek-Latin letters."""
    return not non_latin_letters(text)


def script_name(ch: str) -> str:
    o = ord(ch)
    if 0x0400 <= o <= 0x04FF:
        return "Cyrillic"
    if 0x0600 <= o <= 0x06FF:
        return "Arabic"
    if 0x4E00 <= o <= 0x9FFF or 0x3040 <= o <= 0x30FF or 0xAC00 <= o <= 0xD7A3:
        return "CJK/Kana/Hangul"
    if 0x80 <= o <= 0x24F:
        return "Latin-ext(accented)"
    return "other"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="uzbek-train-filter",
        description="Flag/drop manifest rows whose transcript has non-Uzbek-Latin letters "
                    "(training-side cleanup; not for eval).",
    )
    p.add_argument("input", help="input .json/.jsonl manifest (one JSON object per line)")
    p.add_argument("--field", default="text", help="transcript field (default: %(default)s)")
    p.add_argument("--write", action="store_true",
                   help="write <input>.latin.jsonl (kept) and <input>.nonlatin.jsonl (dropped)")
    p.add_argument("--transliterate-cyrillic", action="store_true",
                   help="first map Cyrillic->Latin, then re-check (recovers Cyrillic-only contamination)")
    p.add_argument("--examples", type=int, default=5, help="how many dropped examples to print")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = p.parse_args(argv)

    base = a.input.rsplit(".", 1)[0]
    keep_f = open(base + ".latin.jsonl", "w", encoding="utf-8") if a.write else None
    drop_f = open(base + ".nonlatin.jsonl", "w", encoding="utf-8") if a.write else None

    total = kept = dropped = 0
    scripts: Counter = Counter()
    chars: Counter = Counter()
    examples = []
    for line in open(a.input, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        total += 1
        row = json.loads(line)
        text = row.get(a.field, "") or ""
        if a.transliterate_cyrillic:
            text = cyrillic_to_latin(text)
        bad = non_latin_letters(text)
        if bad:
            dropped += 1
            for ch in bad:
                chars[ch] += 1
                scripts[script_name(ch)] += 1
            if len(examples) < a.examples:
                examples.append(row.get(a.field, "")[:100])
            if drop_f:
                drop_f.write(line + "\n")
        else:
            kept += 1
            if keep_f:
                keep_f.write((json.dumps(row, ensure_ascii=False) if a.transliterate_cyrillic
                              and (row.update({a.field: text}) or True) else line) + "\n")

    if keep_f:
        keep_f.close()
        drop_f.close()
    pct = 100 * dropped / max(total, 1)
    print(f"{a.input}")
    print(f"  total={total}  kept={kept}  dropped={dropped} ({pct:.2f}%)")
    print(f"  scripts={dict(scripts.most_common())}")
    print(f"  top non-Latin letters={dict(chars.most_common(15))}")
    for e in examples:
        print("  e.g.:", e)
    if a.write:
        print(f"  wrote {base}.latin.jsonl ({kept}) and {base}.nonlatin.jsonl ({dropped})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
