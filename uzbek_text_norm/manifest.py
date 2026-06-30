"""Normalize the text fields of a NeMo-style JSON / JSONL manifest.

Each line is a JSON object, e.g.::

    {"audio_filepath": "a.wav", "duration": 3.2, "text": "2024-yil", "pred_text": "Салом"}

By default the reference field ``text`` is normalized with the *reference* preset
and the hypothesis field ``pred_text`` (when present) with the *hypothesis*
preset. Every other field is preserved untouched.

Usage::

    uzbek-norm-manifest test_omni_asr.json                # -> test_omni_asr.norm.json
    uzbek-norm-manifest in.jsonl -o out.jsonl
    uzbek-norm-manifest in.json  -o -                     # write to stdout
    uzbek-norm-manifest in.json  --keep-original          # keep text_raw / pred_text_raw
    uzbek-norm-manifest in.json  --text-mode hypothesis   # 'text' holds model output

Also runnable as ``python -m uzbek_text_norm.manifest``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Callable, Iterable, Iterator, Optional

from . import __version__
from .core import UzbekNormalizer, normalize_hypothesis, normalize_reference

_GENERAL = UzbekNormalizer(transliterate_cyrillic=True, drop_tags=()).normalize
_MODES = {"reference": normalize_reference, "hypothesis": normalize_hypothesis,
          "general": _GENERAL}


def _derive_output(path: str) -> str:
    for ext in (".jsonl", ".json"):
        if path.endswith(ext):
            return path[: -len(ext)] + ".norm" + ext
    return path + ".norm"


def normalize_manifest(
    lines: Iterable[str],
    *,
    text_field: Optional[str] = "text",
    text_norm: Callable[[str], str] = normalize_reference,
    pred_field: Optional[str] = "pred_text",
    pred_norm: Callable[[str], str] = normalize_hypothesis,
    keep_original: bool = False,
) -> Iterator[str]:
    """Yield normalized JSON lines (no trailing newline) for each manifest row."""
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        row = json.loads(raw)
        for field, fn in ((text_field, text_norm), (pred_field, pred_norm)):
            if field and isinstance(row.get(field), str):
                if keep_original:
                    row[field + "_raw"] = row[field]
                row[field] = fn(row[field])
        yield json.dumps(row, ensure_ascii=False)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="uzbek-norm-manifest",
        description="Normalize the text fields of a NeMo-style JSON/JSONL manifest.",
    )
    p.add_argument("input", help="input .json/.jsonl manifest (one JSON object per line)")
    p.add_argument("-o", "--output",
                   help="output path, or '-' for stdout (default: <input>.norm.json)")
    p.add_argument("--text-field", default="text",
                   help="reference field name (default: %(default)s)")
    p.add_argument("--text-mode", default="reference",
                   choices=["reference", "hypothesis", "general", "none"],
                   help="how to normalize the reference field (default: %(default)s)")
    p.add_argument("--pred-field", default="pred_text",
                   help="hypothesis field name (default: %(default)s)")
    p.add_argument("--pred-mode", default="hypothesis",
                   choices=["reference", "hypothesis", "general", "none"],
                   help="how to normalize the hypothesis field (default: %(default)s)")
    p.add_argument("--keep-original", action="store_true",
                   help="store the un-normalized text in <field>_raw")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)

    text_field = None if args.text_mode == "none" else args.text_field
    pred_field = None if args.pred_mode == "none" else args.pred_field

    out_path = args.output or _derive_output(args.input)
    out = sys.stdout if out_path == "-" else open(out_path, "w", encoding="utf-8")
    n = 0
    try:
        with open(args.input, encoding="utf-8") as f:
            for line in normalize_manifest(
                f,
                text_field=text_field, text_norm=_MODES.get(args.text_mode, normalize_reference),
                pred_field=pred_field, pred_norm=_MODES.get(args.pred_mode, normalize_hypothesis),
                keep_original=args.keep_original,
            ):
                out.write(line + "\n")
                n += 1
    finally:
        if out is not sys.stdout:
            out.close()
    if out_path != "-":
        print(f"normalized {n} rows -> {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
