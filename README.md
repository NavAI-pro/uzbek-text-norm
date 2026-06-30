# uzbek-text-norm

**Self-contained text normalization for Uzbek ASR & NLP.**
Cyrillic→Latin transliteration · numbers→words · apostrophe / punctuation / casing cleanup.

Comparing Uzbek speech-recognition systems is unfair unless every transcript is
normalized the same way. Uzbek is written in **two alphabets** (Latin and Cyrillic),
the Latin okina (oʻ, gʻ) is typed with **half a dozen different apostrophe glyphs**,
and references spell numbers **as words** while models often emit **digits**. Any of
these mismatches inflates Word Error Rate (WER) for reasons that have nothing to do
with recognition quality.

This package gives you one fixed, **reproducible** normalizer to apply to every
transcript, so WER/CER numbers are comparable across systems and runs. It has **zero
runtime dependencies** (standard library only) and the whole engine lives in a single file
([`uzbek_text_norm/core.py`](uzbek_text_norm/core.py)) that you can copy-paste into
any project.

---

## Install

```bash
pip install uzbek-text-norm            # from PyPI (once published)
# or, from this folder:
pip install .
```

No build step required to just use it — `core.py` depends only on `re`:

```bash
# vendor it: copy one file into your repo
cp uzbek_text_norm/core.py your_project/uzbek_norm.py
```

---

## Quick start

```python
from uzbek_text_norm import normalize_reference, normalize_hypothesis

# Gold reference (Latin Uzbek) — ordinals + numbers spelled out
normalize_reference("2024-yil, G'alaba! 137 kishi")
# -> 'ikki ming yigirma toʻrtinchi yil gʻalaba bir yuz oʻttiz yetti kishi'

# Model output that came out in Cyrillic — still matches the Latin gold
normalize_hypothesis("Ғалаба")            # -> 'gʻalaba'
normalize_hypothesis("Ғалаба") == normalize_reference("g'alaba")   # True
```

CLI:

```bash
echo "Салом дунё" | uzbek-text-norm --mode hypothesis     # -> salom dunyo
uzbek-text-norm input.txt > normalized.txt                # one sentence per line
uzbek-text-norm --demo                                    # show what each step does
```

---

## What it does (the pipeline)

Applied in this order:

| # | Step | Example |
|---|------|---------|
| 1 | **Cyrillic → Latin** transliteration *(optional)* | `шаҳар` → `shahar`, `ўзбек` → `oʻzbek` |
| 2 | **Numbers → Uzbek words** (cardinals + **ordinals**) | `2024` → `ikki ming yigirma toʻrt`; `137` → `bir yuz oʻttiz yetti`; `2024-yil` → `ikki ming yigirma toʻrtinchi yil`; `5-sinf` → `beshinchi sinf` |
| 3 | **Clean**: lowercase, fold apostrophes to the okina `ʻ`, strip punctuation, collapse spaces, **fold source artifacts** | `G'alaba!` → `gʻalaba`; `Ӯzbekiston` → `oʻzbekiston`; `29¾` → `29` |
| 4 | **Drop annotation tags** | `salom noise dunyo` → `salom dunyo` |

Step 3 also folds, **symmetrically on both reference and hypothesis**, the kinds of
encoding artifacts that show up in real corpora: Cyrillic homoglyphs inside Latin text
(`ӯ`/`Ӯ` → `oʻ`, stray `а` → `a`), BOM / zero-width characters, Unicode hyphen variants
(non-breaking, figure, minus → merged like `-`), and vulgar fractions (`½ ¼ ¾`). These
never reach a token comparison, so a correct word is not penalized for a stray code point.

Two ready-made presets:

- `normalize_reference(text)` — for gold references (Latin): steps 2–4 (no transliteration).
- `normalize_hypothesis(text)` — for model output: steps 1–4 (handles Cyrillic output).

Why each step matters for fair WER:

- **Transliteration** — a correct word in the "wrong" alphabet would otherwise count as an error.
- **Apostrophe folding** — `o'` `oʻ` `oʼ` `o‘` `o’` all become one code point, so `oʻzbek` isn't a substitution against `o'zbek`.
- **Number spelling** — `2024` vs `ikki ming yigirma toʻrt` (and ordinal `2024-yil` vs `ikki ming yigirma toʻrtinchi yil`) is a formatting difference, not a recognition error.
- **Tag dropping** — `noise` / `hesitation` markers in references aren't spoken words.

---

## Scoring ASR (WER / CER)

Use the presets on **both** sides so reference and hypothesis are treated identically.
`jiwer` is the only extra dependency (`pip install "uzbek-text-norm[score]"`):

```python
from jiwer import wer, cer
from uzbek_text_norm import normalize_reference, normalize_hypothesis

refs  = ["2024-yil bo'ldi", "G'alaba"]
hyps  = ["ikki ming yigirma to'rt yil bo'ldi", "Ғалаба"]   # 2nd is Cyrillic

R = [normalize_reference(r) for r in refs]
H = [normalize_hypothesis(h) for h in hyps]

print(f"WER = {wer(R, H) * 100:.2f}")
print(f"CER = {cer(R, H) * 100:.2f}")
```

### Score a manifest in one command

Have a JSON/JSONL manifest with a reference and a prediction column? Get WER/CER
directly — normalization is applied for you (this is the exact recipe behind the
benchmark numbers):

```bash
uzbek-text-score preds.jsonl --ref-field text --hyp-field pred
#  set        N      WER      CER
#  ------------------------------
#  OVERALL  3837    8.67     2.10

uzbek-text-score preds.jsonl --by dataset      # per-dataset breakdown
uzbek-text-score preds.jsonl --json            # machine-readable
```

```python
from uzbek_text_norm import score_manifest
res = score_manifest("preds.jsonl", ref_field="text", hyp_field="pred", by="dataset")
print(res["overall"]["wer"], res["overall"]["cer"])
```

Each row's reference is normalized with `normalize_reference` and its prediction with
`normalize_hypothesis`; rows with an empty prediction are skipped by default
(`--keep-empty-hyp` to count them as errors instead).

---

## Configurable API

```python
from uzbek_text_norm import UzbekNormalizer

norm = UzbekNormalizer(
    transliterate_cyrillic=True,   # map Cyrillic -> Latin first
    spell_numbers=True,            # digits -> Uzbek words
    strip_punctuation=True,
    fold_apostrophes=True,
    drop_tags=("noise", "hesitation"),
    apostrophe="ʻ",                # set to "'" for ASCII output
)
norm("Салом, 25 kishi!")           # -> 'salom yigirma besh kishi'
```

Lower-level building blocks are exported too:

```python
from uzbek_text_norm import cyrillic_to_latin, spell_numbers_in_text, number_to_words, clean

number_to_words(25341)             # 'yigirma besh ming uch yuz qirq bir'
cyrillic_to_latin("ўзбекистон")    # 'oʻzbekiston'
spell_numbers_in_text("kanal 5")   # 'kanal besh'
clean("  Salom,  Dunyo!! ")        # 'salom dunyo'
```

### CLI options

```
uzbek-text-norm [input]            # file path, or omit / '-' for stdin
  --mode {general,reference,hypothesis}   general (default): transliterate, keep tags
  --cyrillic / --no-cyrillic              force / disable transliteration
  --no-numbers                            keep digits as-is
  --ascii-apostrophe                      emit ' instead of ʻ
  --drop-tags / --keep-tags               override tag handling
  --tags noise,hesitation                 which tags to drop
  --demo                                  print examples and exit
```

### Normalize a NeMo manifest

```bash
uzbek-norm-manifest preds.jsonl                      # -> preds.norm.jsonl
uzbek-norm-manifest preds.jsonl -o - --keep-original # stdout, keep <field>_raw
```

Normalizes the `text` (reference) and `pred_text` (hypothesis) fields of a JSON/JSONL
manifest, preserving every other field. Override with `--text-field` / `--pred-field`
and `--text-mode` / `--pred-mode`.

---

## Notes & known limitations

- **Latin output, okina by default.** Output is lowercase Latin Uzbek using the okina
  `ʻ` (U+02BB) for `oʻ`/`gʻ`. Pass `apostrophe="'"` (or `--ascii-apostrophe`) for ASCII.
- **Numbers & ordinals.** Integers, grouped thousands (`1,000` / `1 000`), and ordinals
  (`<digits>-<word>`, e.g. `2024-yil` → `ikki ming yigirma toʻrtinchi yil`) are handled.
  Conventions (verified against gold refs): the final group keeps "bir" (`137` → *bir yuz
  oʻttiz yetti*, `1000` → *bir ming*), but a hundred *multiplying* a scale is bare
  (`100000` → *yuz ming*). Only the last word of an ordinal takes the `-(i)nchi` suffix
  (`21-asr` → *yigirma birinchi asr*); a bare marker (`5-chi`, `5-nchi`, `5-inchi`) is
  absorbed. Decimals are not parsed specially. Pass `ordinals=False` to disable.
- **Hyphens** are removed (compounds merged: `ob-havo` → `obhavo`), matching the dominant
  gold-reference convention — not replaced with a space. Unicode hyphen variants
  (non-breaking `‑`, figure `‒`, horizontal bar `―`, minus `−`) are folded to a plain
  hyphen first, so they merge identically.
- **Source artifacts** are folded symmetrically on references and hypotheses: BOM /
  zero-width characters (U+FEFF, U+200B–U+200D, U+2060) are dropped; Cyrillic homoglyphs
  embedded in Latin text are corrected (`а` → `a`, `ӯ`/`Ӯ` → `oʻ`); vulgar fractions
  (`½ ¼ ¾`) are stripped. A genuinely foreign letter (e.g. `ö`) is **not** guessed at — it
  is left as-is, since mapping it would be an editorial choice rather than a normalization.
- **Transliteration is one-directional** (Cyrillic → Latin) and tuned for Uzbek; it is a
  scoring-normalization tool, not a general Cyrillic transliterator.
- Integers ≥ 10¹² are read digit by digit.

---

## Tests

```bash
pip install "uzbek-text-norm[dev]"
pytest
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md). Latest: **0.3.0** adds a one-command manifest scorer
(`uzbek-text-score` / `score_manifest`). 0.2.0 added symmetric source-artifact folding
(Cyrillic homoglyphs, BOM/zero-width, Unicode hyphens, vulgar fractions).

## License

[MIT](LICENSE). Contributions and issues welcome.

Built and maintained by [NavAI](https://navai.pro). If it helps your work, a link back
is appreciated.
