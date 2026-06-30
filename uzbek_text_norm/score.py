"""Score an ASR manifest: WER / CER with the uzbek_text_norm presets applied.

A *manifest* is a JSON array or a JSONL file (one object per utterance) with a
reference-text field and a hypothesis-text field. Each reference is normalized
with :func:`normalize_reference`, each hypothesis with :func:`normalize_hypothesis`
(so model output in Cyrillic still matches a Latin reference), then corpus-level
WER and CER are computed with ``jiwer``.

This is the exact recipe used for the NavAI Uzbek ASR benchmark, so numbers are
reproducible: feed a manifest in, get scores out.

CLI::

    uzbek-text-score preds.jsonl                          # fields: text + pred
    uzbek-text-score preds.jsonl --ref-field text --hyp-field pred_text
    uzbek-text-score preds.jsonl --by dataset             # per-group breakdown
    uzbek-text-score preds.jsonl --json                   # machine-readable

Python::

    from uzbek_text_norm import score_manifest
    res = score_manifest("preds.jsonl", ref_field="text", hyp_field="pred")
    print(res["overall"]["wer"], res["overall"]["cer"])

``jiwer`` is the only extra dependency:  ``pip install "uzbek-text-norm[score]"``.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .core import OKINA, normalize_hypothesis, normalize_reference


def _need_jiwer():
    try:
        from jiwer import cer, wer
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "scoring needs `jiwer`. Install with:  pip install \"uzbek-text-norm[score]\""
        ) from e
    return wer, cer


def load_manifest(path: str) -> List[Dict[str, Any]]:
    """Read a JSON array *or* a JSONL file into a list of dicts."""
    if path == "-":
        text = sys.stdin.read()
    else:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    text = text.strip()
    if not text:
        return []
    if text[0] == "[":                       # JSON array
        return list(json.loads(text))
    return [json.loads(ln) for ln in text.splitlines() if ln.strip()]   # JSONL


def score_pairs(
    refs: Iterable[str],
    hyps: Iterable[str],
    *,
    apostrophe: str = OKINA,
) -> Dict[str, float]:
    """Normalize each (ref, hyp) and return corpus-level ``{wer, cer, n}`` (percent)."""
    wer, cer = _need_jiwer()
    R = [normalize_reference(r) for r in refs]
    H = [normalize_hypothesis(h) for h in hyps]
    if apostrophe != OKINA:
        R = [r.replace(OKINA, apostrophe) for r in R]
        H = [h.replace(OKINA, apostrophe) for h in H]
    keep: Tuple[List[str], List[str]] = ([], [])
    for r, h in zip(R, H):
        if r:                                # skip empty references (cannot be scored)
            keep[0].append(r); keep[1].append(h)
    if not keep[0]:
        return {"wer": float("nan"), "cer": float("nan"), "n": 0}
    return {
        "wer": round(wer(keep[0], keep[1]) * 100, 2),
        "cer": round(cer(keep[0], keep[1]) * 100, 2),
        "n": len(keep[0]),
    }


def score_manifest(
    path: str,
    *,
    ref_field: str = "text",
    hyp_field: str = "pred",
    by: Optional[str] = None,
    skip_empty_hyp: bool = True,
) -> Dict[str, Any]:
    """Score a manifest file. Returns ``{"overall": {...}, "groups": {name: {...}}}``.

    ``ref_field`` / ``hyp_field`` name the reference and hypothesis columns. With
    ``by`` set, also reports a per-value breakdown of that field. Rows missing the
    reference are skipped; rows with an empty hypothesis are skipped when
    ``skip_empty_hyp`` is true (they otherwise count as full errors).
    """
    rows = load_manifest(path)
    refs, hyps, groups = [], [], []
    for row in rows:
        r = str(row.get(ref_field) or "").strip()
        h = str(row.get(hyp_field) or "").strip()
        if not r:
            continue
        if skip_empty_hyp and not h:
            continue
        refs.append(r); hyps.append(h)
        groups.append(str(row.get(by)) if by else None)

    out: Dict[str, Any] = {"overall": score_pairs(refs, hyps)}
    if by:
        names = sorted(set(groups))
        out["groups"] = {
            g: score_pairs([r for r, gg in zip(refs, groups) if gg == g],
                           [h for h, gg in zip(hyps, groups) if gg == g])
            for g in names
        }
    return out


def _print_table(res: Dict[str, Any], by: Optional[str]) -> None:
    rows = []
    if by and res.get("groups"):
        for name, d in res["groups"].items():
            rows.append((name, d))
    rows.append(("OVERALL", res["overall"]))
    w = max(len(n) for n, _ in rows)
    print(f"{'set'.ljust(w)}   {'N':>7} {'WER':>8} {'CER':>8}")
    print("-" * (w + 27))
    for name, d in rows:
        print(f"{name.ljust(w)}   {d['n']:>7} {d['wer']:>8.2f} {d['cer']:>8.2f}")


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(
        prog="uzbek-text-score",
        description="WER/CER for an ASR manifest, with uzbek_text_norm normalization.",
    )
    ap.add_argument("manifest", help="JSON array or JSONL file ('-' for stdin)")
    ap.add_argument("--ref-field", default="text", help="reference column (default: text)")
    ap.add_argument("--hyp-field", default="pred",
                    help="hypothesis/prediction column (default: pred)")
    ap.add_argument("--by", default=None, help="also break down by this field (e.g. dataset)")
    ap.add_argument("--keep-empty-hyp", action="store_true",
                    help="count empty predictions as errors instead of skipping them")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    a = ap.parse_args(argv)

    res = score_manifest(a.manifest, ref_field=a.ref_field, hyp_field=a.hyp_field,
                         by=a.by, skip_empty_hyp=not a.keep_empty_hyp)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        _print_table(res, a.by)


if __name__ == "__main__":
    main()
