"""Command-line interface for uzbek_text_norm.

Examples
--------
    # normalize a file (one sentence per line) to stdout
    uzbek-text-norm input.txt > normalized.txt

    # pipe Cyrillic model output through the hypothesis preset
    echo "Салом дунё" | uzbek-text-norm --mode hypothesis

    # see what every step does
    uzbek-text-norm --demo
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .core import DEFAULT_TAGS, UzbekNormalizer


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="uzbek-text-norm",
        description="Normalize Uzbek text (transliteration, numbers->words, cleanup).",
    )
    p.add_argument("input", nargs="?", default="-",
                   help="input file, or '-' for stdin (default: stdin)")
    p.add_argument("--mode", choices=["general", "reference", "hypothesis"],
                   default="general",
                   help="general (default): transliterate, keep tags. "
                        "reference / hypothesis: ASR-scoring presets (drop tags).")
    p.add_argument("--cyrillic", action="store_true",
                   help="force Cyrillic->Latin transliteration")
    p.add_argument("--no-cyrillic", action="store_true",
                   help="disable Cyrillic->Latin transliteration")
    p.add_argument("--no-numbers", action="store_true",
                   help="disable digits->words conversion")
    p.add_argument("--ascii-apostrophe", action="store_true",
                   help="emit ASCII apostrophe (') instead of the okina (ʻ)")
    p.add_argument("--drop-tags", action="store_true",
                   help="drop annotation tags even in general mode")
    p.add_argument("--keep-tags", action="store_true",
                   help="keep annotation tags even in reference/hypothesis mode")
    p.add_argument("--tags", default=",".join(DEFAULT_TAGS),
                   help="comma-separated tags to drop (default: %(default)s)")
    p.add_argument("--demo", action="store_true",
                   help="print example normalizations and exit")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _make_normalizer(args: argparse.Namespace) -> UzbekNormalizer:
    transliterate = args.mode == "hypothesis"
    if args.cyrillic:
        transliterate = True
    if args.no_cyrillic:
        transliterate = False

    tag_set = {t for t in args.tags.split(",") if t}
    if args.mode in ("reference", "hypothesis") or args.drop_tags:
        drop = tag_set
    else:
        drop = set()
    if args.keep_tags:
        drop = set()

    return UzbekNormalizer(
        transliterate_cyrillic=transliterate,
        spell_numbers=not args.no_numbers,
        drop_tags=drop,
        apostrophe="'" if args.ascii_apostrophe else "ʻ",
    )


_DEMO = [
    ("2024-yil 137 kishi", "reference"),
    ("Ғалаба, дўстлар!", "hypothesis"),
    ("U 1,000,000 so'm topdi", "reference"),
    ("salom noise dunyo hesitation", "reference"),
]


def _print_demo() -> None:
    from .core import normalize_hypothesis, normalize_reference
    fn = {"reference": normalize_reference, "hypothesis": normalize_hypothesis}
    width = max(len(t) for t, _ in _DEMO)
    print(f"{'INPUT'.ljust(width)}  MODE        OUTPUT")
    print(f"{'-' * width}  ----------  ------")
    for text, mode in _DEMO:
        print(f"{text.ljust(width)}  {mode:<10}  {fn[mode](text)}")


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if args.demo:
        _print_demo()
        return 0

    norm = _make_normalizer(args)
    stream = sys.stdin if args.input == "-" else open(args.input, encoding="utf-8")
    try:
        for line in stream:
            sys.stdout.write(norm.normalize(line.rstrip("\n")) + "\n")
    finally:
        if stream is not sys.stdin:
            stream.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
