"""
uzbek_text_norm.core
====================
Self-contained text normalization for Uzbek ASR / NLP.

This module depends only on the Python standard library (``re``), so this
single file can be vendored (copy-pasted) into any project if you don't want
the package dependency.

Normalization pipeline (applied in this order):

  1. Cyrillic -> Latin transliteration   (optional; for mixed-script input)
  2. Numbers  -> spelled-out Uzbek words  ("2024" -> "ikki ming yigirma toʻrt")
  3. Cleaning : lowercase, fold every apostrophe variant to the Uzbek okina
                (ʻ, U+02BB), strip punctuation, collapse whitespace, and fold
                source artifacts (Cyrillic homoglyphs ӯ/а, BOM/zero-width chars,
                Unicode hyphen variants, vulgar fractions) symmetrically
  4. Tags     -> drop annotation tokens   (e.g. "noise", "hesitation")

The two presets ``normalize_reference`` and ``normalize_hypothesis`` define one
fixed normalization, so ASR scoring against them is reproducible across systems
and runs:

  * reference  = clean + numbers + drop-tags                  (no transliteration)
  * hypothesis = transliterate + clean + numbers + drop-tags

Why these steps matter for fair Word Error Rate (WER):

  * Uzbek is written in both Latin and Cyrillic. A model may emit one script
    while the reference uses the other; transliterating to a single script
    avoids penalizing a correct word for its alphabet.
  * The Latin okina (oʻ, gʻ) is typed many different ways ( ' ʼ ʻ ‘ ’ ` ).
    Folding them to one code point avoids spurious substitutions.
  * References often spell numbers out ("ikki ming") while a model emits digits
    ("2024") (or vice versa). Spelling digits out makes the comparison fair.
"""

from __future__ import annotations

import re
from typing import Iterable

__all__ = [
    "UzbekNormalizer",
    "normalize",
    "normalize_reference",
    "normalize_hypothesis",
    "clean",
    "cyrillic_to_latin",
    "spell_numbers_in_text",
    "number_to_words",
    "number_to_ordinal_words",
    "DEFAULT_TAGS",
    "OKINA",
]

# The Uzbek okina (left half ring) used in oʻ / gʻ. U+02BB MODIFIER LETTER TURNED COMMA.
OKINA = "ʻ"

# Annotation tokens dropped from both references and hypotheses by the ASR presets.
DEFAULT_TAGS = ("noise", "hesitation")

# Every apostrophe-like glyph that should fold to the okina.
_APOS = r"[\'‘’ʻʼ\x60]"

# Punctuation / symbols stripped during cleaning.
_PUNCT = r'[\.,?:\-!;()«»…\]\[/*–‽+&_\\\\$½√>€™•¼¾}{~—=“”"″‟„%]'

# Zero-width / BOM artifacts removed entirely; Unicode hyphen variants folded to an
# ASCII hyphen so they merge like a normal "-" (en/em dash already in _PUNCT).
_ZERO_WIDTH = re.compile("[\ufeff\u200b\u200c\u200d\u2060]")  # BOM, ZWSP, ZWNJ, ZWJ, WJ
_UNI_HYPHEN = re.compile("[\u2010\u2011\u2012\u2015\u2212]")  # hyphen / nb-hyphen / figure / horiz-bar / minus


# --------------------------------------------------------------------------- #
# 1. Cyrillic -> Latin transliteration                                        #
# --------------------------------------------------------------------------- #

# Multi-character mappings are applied before single-character ones.
_CYR2LAT_MULTI = {
    "ў": "oʻ", "ӯ": "oʻ", "қ": "q", "ғ": "gʻ", "ҳ": "h", "ё": "yo", "ю": "yu",
    "я": "ya", "ш": "sh", "ч": "ch", "ц": "ts",
}
_CYR2LAT_ONE = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x",
    "э": "e", "ъ": "ʻ", "ь": "",
}
# Cyrillic "е" -> "ye" at a word start or after a vowel / soft|hard sign, else "e".
_E_TO_YE = re.compile(r"(?:(?<=^)|(?<=[\s аеёиоуўэюяьъ]))е")


def cyrillic_to_latin(text: str) -> str:
    """Transliterate Uzbek Cyrillic to Latin. Lowercases the input."""
    text = (text or "").lower()
    text = _E_TO_YE.sub("ye", text)
    text = text.replace("е", "e")
    for c, l in _CYR2LAT_MULTI.items():
        text = text.replace(c, l)
    for c, l in _CYR2LAT_ONE.items():
        text = text.replace(c, l)
    return text


# --------------------------------------------------------------------------- #
# 2. Numbers -> spelled-out Uzbek words                                        #
# --------------------------------------------------------------------------- #

_ONES = {1: "bir", 2: "ikki", 3: "uch", 4: "to'rt", 5: "besh", 6: "olti",
         7: "yetti", 8: "sakkiz", 9: "to'qqiz"}
_TENS = {10: "o'n", 20: "yigirma", 30: "o'ttiz", 40: "qirq", 50: "ellik",
         60: "oltmish", 70: "yetmish", 80: "sakson", 90: "to'qson"}
_SCALES = ((10 ** 9, "milliard"), (10 ** 6, "million"), (10 ** 3, "ming"), (1, ""))
_VOWELS = "aeiou"

# Number words are emitted with a plain ASCII apostrophe (to'rt, o'n); the
# cleaning step folds those to the okina (toʻrt, oʻn) so output is consistent.


def _spell_group(n: int, *, leading_bir: bool) -> str:
    """Spell an integer in 1..999.

    ``leading_bir`` decides how a hundreds digit of 1 is read: in the final
    ("ones") group, 100 is "bir yuz"; as a multiplier of a higher scale
    (the 100 in "yuz ming") it is the bare "yuz".
    """
    parts = []
    hundreds, rest = divmod(n, 100)
    if hundreds == 1:
        parts.append("bir yuz" if leading_bir else "yuz")
    elif hundreds:
        parts.append(_ONES[hundreds] + " yuz")
    if rest:
        if rest < 10:
            parts.append(_ONES[rest])
        else:
            tens, ones = divmod(rest, 10)
            parts.append(_TENS[tens * 10] + ((" " + _ONES[ones]) if ones else ""))
    return " ".join(parts)


def number_to_words(n: int) -> str:
    """Spell a non-negative integer as Uzbek cardinal words (ASCII apostrophes).

    Conventions (verified against gold Uzbek references):
      * final group keeps "bir": 1 -> "bir", 100 -> "bir yuz", 137 -> "bir yuz ..."
      * a scale word whose coefficient is exactly 1 keeps "bir":
        1000 -> "bir ming", 1_000_000 -> "bir million", 1e9 -> "bir milliard"
      * a hundred *multiplying* a scale is bare: 100_000 -> "yuz ming",
        1e8 -> "yuz million"; 10_000 -> "o'n ming"

    Example: ``number_to_words(2024)`` -> ``ikki ming yigirma to'rt``.
    """
    if n < 0:
        raise ValueError("number_to_words expects a non-negative integer")
    if n == 0:
        return "nol"
    if n >= 10 ** 12:  # beyond milliard scale -> read digit by digit
        return " ".join(("nol" if d == "0" else _ONES[int(d)]) for d in str(n))
    out = []
    for div, name in _SCALES:
        q, n = divmod(n, div)
        if not q:
            continue
        is_ones_group = name == ""
        if q == 1 and not is_ones_group:
            out.append("bir " + name)                 # bir ming / bir million / bir milliard
        elif is_ones_group:
            out.append(_spell_group(q, leading_bir=True))
        else:
            out.append(_spell_group(q, leading_bir=False) + " " + name)
    return " ".join(out)


# Ordinals: spell the cardinal, then suffix only the LAST word.
#   "-(i)nchi": consonant-final -> "inchi" (to'rt -> to'rtinchi),
#               vowel-final     -> "nchi"  (ikki -> ikkinchi, yigirma -> yigirmanchi)
# Exact powers drop the leading "bir": 100 -> yuzinchi, 1000 -> minginchi.
_ORDINAL_DROP_BIR = {"bir yuz": "yuz", "bir ming": "ming",
                     "bir million": "million", "bir milliard": "milliard"}


def number_to_ordinal_words(n: int) -> str:
    """Spell a non-negative integer as an Uzbek ordinal.

    Example: ``number_to_ordinal_words(2024)`` -> ``ikki ming yigirma to'rtinchi``.
    """
    words = _ORDINAL_DROP_BIR.get(number_to_words(n)) or number_to_words(n)
    head, sep, last = words.rpartition(" ")
    last = last + ("nchi" if last and last[-1] in _VOWELS else "inchi")
    return f"{head} {last}" if sep else last


# <digits>-<word>  marks an ordinal (2024-yil, 5-sinf, 21-asr). A bare ordinal
# marker (-chi / -nchi / -inchi) is absorbed; any other word is kept.
_THOUSANDS_SEP = re.compile(r"(?<=\d)[,\s](?=\d{3}\b)")
_ORDINAL_PATTERN = re.compile(r"(\d+)[-‐-―]([^\W\d_]+)")
_BARE_ORDINAL_MARKER = re.compile(r"(?i)^(?:chi|nchi|inchi)$")
_DIGIT_RUN = re.compile(r"\d+")


def spell_numbers_in_text(text: str, *, ordinals: bool = True) -> str:
    """Replace digit runs in ``text`` with spelled-out Uzbek words.

    Thousands separators (``1,000`` / ``1 000``) are removed first. When
    ``ordinals`` is true, a ``<digits>-<word>`` token (e.g. ``2024-yil``) is
    read as an ordinal (``ikki ming yigirma toʻrtinchi yil``).
    """
    text = _THOUSANDS_SEP.sub("", text)
    if ordinals:
        def _ord(m: "re.Match") -> str:
            word = number_to_ordinal_words(int(m.group(1)))
            suffix = m.group(2)
            return word if _BARE_ORDINAL_MARKER.match(suffix) else f"{word} {suffix}"
        text = _ORDINAL_PATTERN.sub(_ord, text)
    return _DIGIT_RUN.sub(lambda m: number_to_words(int(m.group())), text)


# --------------------------------------------------------------------------- #
# 3. Cleaning                                                                  #
# --------------------------------------------------------------------------- #

_FOLD_O = re.compile(r"(?i)(o)" + _APOS)
_FOLD_G = re.compile(r"(?i)(g)" + _APOS)
_OTHER_APOS = re.compile(r"[‘’ʼ]")
_PUNCT_RE = re.compile(_PUNCT)
_WS = re.compile(r"\s+")


def clean(
    text: str,
    *,
    lowercase: bool = True,
    fold_apostrophes: bool = True,
    strip_punctuation: bool = True,
    collapse_whitespace: bool = True,
    apostrophe: str = OKINA,
) -> str:
    """Lowercase, fold apostrophes to the okina, strip punctuation, collapse spaces.

    Also folds source artifacts symmetrically (so a reference and a hypothesis
    that differ only by an artifact still match): BOM / zero-width characters are
    dropped, Unicode hyphen variants and the soft hyphen are normalized, vulgar
    fractions are stripped, and Cyrillic homoglyphs that appear inside otherwise
    Latin Uzbek text are folded (``а`` -> ``a``, ``ӯ``/``Ӯ`` -> ``oʻ``).
    """
    text = text or ""
    text = _ZERO_WIDTH.sub("", text)     # drop BOM / zero-width artifacts
    text = _UNI_HYPHEN.sub("-", text)    # fold Unicode hyphens to ASCII "-" (then stripped/merged)
    if lowercase:
        text = text.lower()
    if fold_apostrophes:
        text = _FOLD_O.sub(r"\1ʻ", text)   # o' / o‘ ... -> oʻ
        text = _FOLD_G.sub(r"\1ʻ", text)   # g' / g‘ ... -> gʻ
        text = _OTHER_APOS.sub("ʻ", text)
    if strip_punctuation:
        text = _PUNCT_RE.sub("", text)
    # Fold Cyrillic homoglyphs that appear in otherwise-Latin Uzbek text so refs and
    # hyps match: stray Cyrillic "а"->"a", and "ӯ"/"Ӯ" (U+04EF/04EE, U-with-macron) ->
    # "oʻ" (a non-standard spelling of the Cyrillic short-U "ў"). Soft hyphen -> space.
    text = text.replace("а", "a").replace("ӯ", "oʻ").replace("Ӯ", "oʻ").replace("­", " ")
    if collapse_whitespace:
        text = _WS.sub(" ", text).strip()
    if fold_apostrophes:
        text = text.replace("'", "ʻ")
        if apostrophe != OKINA:
            text = text.replace(OKINA, apostrophe)
    return text


# --------------------------------------------------------------------------- #
# Configurable normalizer + presets                                           #
# --------------------------------------------------------------------------- #


class UzbekNormalizer:
    """Configurable Uzbek text normalizer.

    Parameters
    ----------
    transliterate_cyrillic : bool
        Map Cyrillic to Latin first (use for model output that may be Cyrillic).
    spell_numbers : bool
        Replace digit runs with spelled-out Uzbek words.
    lowercase, fold_apostrophes, strip_punctuation, collapse_whitespace : bool
        Cleaning toggles (see :func:`clean`).
    drop_tags : Iterable[str]
        Whole-word tokens removed after cleaning (e.g. ``("noise", "hesitation")``).
    apostrophe : str
        Target glyph for the okina (default ``ʻ``). Set to ``"'"`` for ASCII output.
    """

    def __init__(
        self,
        *,
        transliterate_cyrillic: bool = False,
        spell_numbers: bool = True,
        ordinals: bool = True,
        lowercase: bool = True,
        fold_apostrophes: bool = True,
        strip_punctuation: bool = True,
        collapse_whitespace: bool = True,
        drop_tags: Iterable[str] = DEFAULT_TAGS,
        apostrophe: str = OKINA,
    ) -> None:
        self.transliterate_cyrillic = transliterate_cyrillic
        self.spell_numbers = spell_numbers
        self.ordinals = ordinals
        self.lowercase = lowercase
        self.fold_apostrophes = fold_apostrophes
        self.strip_punctuation = strip_punctuation
        self.collapse_whitespace = collapse_whitespace
        self.drop_tags = frozenset(drop_tags)
        self.apostrophe = apostrophe

    def normalize(self, text: str) -> str:
        text = text or ""
        if self.transliterate_cyrillic:
            text = cyrillic_to_latin(text)
        if self.spell_numbers:
            text = spell_numbers_in_text(text, ordinals=self.ordinals)
        text = clean(
            text,
            lowercase=self.lowercase,
            fold_apostrophes=self.fold_apostrophes,
            strip_punctuation=self.strip_punctuation,
            collapse_whitespace=self.collapse_whitespace,
            apostrophe=self.apostrophe,
        )
        if self.drop_tags:
            text = " ".join(w for w in text.split() if w not in self.drop_tags)
        return text

    __call__ = normalize


# Fixed presets for reproducible Uzbek ASR scoring.
_REFERENCE = UzbekNormalizer(transliterate_cyrillic=False)
_HYPOTHESIS = UzbekNormalizer(transliterate_cyrillic=True)


def normalize_reference(text: str) -> str:
    """Normalize a *gold reference* (Latin Uzbek): clean + numbers + drop-tags."""
    return _REFERENCE.normalize(text)


def normalize_hypothesis(text: str) -> str:
    """Normalize a *model hypothesis*: transliterate + clean + numbers + drop-tags."""
    return _HYPOTHESIS.normalize(text)


def normalize(
    text: str,
    *,
    transliterate_cyrillic: bool = True,
    spell_numbers: bool = True,
    drop_tags: Iterable[str] = (),
) -> str:
    """General-purpose normalization (transliterates by default, keeps tags).

    For ASR scoring use :func:`normalize_reference` / :func:`normalize_hypothesis`.
    """
    return UzbekNormalizer(
        transliterate_cyrillic=transliterate_cyrillic,
        spell_numbers=spell_numbers,
        drop_tags=drop_tags,
    ).normalize(text)
