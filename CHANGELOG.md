# Changelog

All notable changes to `uzbek-text-norm` are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [0.3.0]

### Added
- **Manifest scorer** (`uzbek_text_norm.score`): feed a JSON/JSONL manifest with a
  reference and a prediction column, get corpus-level WER/CER with the normalization
  applied — the exact recipe behind the benchmark numbers.
  - New CLI `uzbek-text-score` (`--ref-field`, `--hyp-field`, `--by`, `--json`,
    `--keep-empty-hyp`).
  - New API `score_manifest(...)` and `score_pairs(...)`, exported from the package.
- Tests for the scorer (skipped if `jiwer` is not installed).

## [0.2.0]

### Added
- **Symmetric source-artifact folding** in `clean()` (applies to both references and
  hypotheses), so a correct word is never penalized for an encoding artifact:
  - Cyrillic homoglyphs inside Latin Uzbek text: `ӯ`/`Ӯ` (U+04EF/U+04EE, "U with
    macron") → `oʻ`, in addition to the existing stray `а` (U+0430) → `a`.
  - BOM / zero-width characters (U+FEFF, U+200B, U+200C, U+200D, U+2060) are removed.
  - Unicode hyphen variants (U+2010 hyphen, U+2011 non-breaking, U+2012 figure,
    U+2015 horizontal bar, U+2212 minus) are folded to a plain `-` and then merged
    like any other hyphen.
  - Vulgar fraction `¾` (U+00BE) is now stripped, matching the existing `½`/`¼`.
- `ӯ` → `oʻ` added to the Cyrillic→Latin transliteration map.
- Tests covering every artifact-folding case.

### Notes
- This changes scoring output by a tiny, **symmetric** amount (identical for every
  system), so relative WER/CER comparisons are unaffected. Recompute any downstream
  WER/CER scores with this version.
- A genuinely foreign letter (e.g. `ö`) is intentionally **not** remapped — that would
  be an editorial choice rather than a normalization.

## [0.1.0]

- Initial release: Cyrillic→Latin transliteration, numbers→Uzbek words (cardinals +
  ordinals), apostrophe/punctuation/casing cleanup, annotation-tag dropping,
  `normalize_reference` / `normalize_hypothesis` presets, CLI, and manifest tooling.
