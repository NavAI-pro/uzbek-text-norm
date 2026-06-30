"""Behavior tests for uzbek_text_norm. Run: ``pytest`` (or ``python -m pytest``)."""

from uzbek_text_norm import (
    UzbekNormalizer,
    clean,
    cyrillic_to_latin,
    normalize,
    normalize_hypothesis,
    normalize_reference,
    number_to_ordinal_words,
    number_to_words,
)


def test_cardinals_basic():
    assert number_to_words(0) == "nol"
    assert number_to_words(5) == "besh"
    assert number_to_words(25) == "yigirma besh"
    assert number_to_words(2024) == "ikki ming yigirma to'rt"
    assert number_to_words(25341) == "yigirma besh ming uch yuz qirq bir"


def test_cardinals_leading_bir():
    # Final group keeps "bir"; coefficient-1 scale words keep "bir".
    assert number_to_words(100) == "bir yuz"
    assert number_to_words(137) == "bir yuz o'ttiz yetti"
    assert number_to_words(1000) == "bir ming"
    assert number_to_words(1000000) == "bir million"
    assert number_to_words(1000000000) == "bir milliard"


def test_cardinals_bare_hundred_multiplier():
    # A hundred multiplying a scale is bare ("yuz ming", not "bir yuz ming").
    assert number_to_words(10000) == "o'n ming"
    assert number_to_words(100000) == "yuz ming"
    assert number_to_words(100000000) == "yuz million"
    assert number_to_words(1500000) == "bir million besh yuz ming"


def test_ordinals():
    assert number_to_ordinal_words(1) == "birinchi"
    assert number_to_ordinal_words(2) == "ikkinchi"
    assert number_to_ordinal_words(3) == "uchinchi"
    assert number_to_ordinal_words(4) == "to'rtinchi"
    assert number_to_ordinal_words(10) == "o'ninchi"
    assert number_to_ordinal_words(20) == "yigirmanchi"
    assert number_to_ordinal_words(21) == "yigirma birinchi"
    assert number_to_ordinal_words(100) == "yuzinchi"     # exact power drops "bir"
    assert number_to_ordinal_words(1000) == "minginchi"
    assert number_to_ordinal_words(2024) == "ikki ming yigirma to'rtinchi"


def test_ordinal_in_text():
    assert normalize_reference("2024-yil") == "ikki ming yigirma toʻrtinchi yil"
    assert normalize_reference("5-sinf") == "beshinchi sinf"
    assert normalize_reference("21-asr") == "yigirma birinchi asr"
    assert normalize_reference("2-chi") == "ikkinchi"               # bare marker absorbed
    assert normalize_reference("5-inchi o'rin") == "beshinchi oʻrin"
    assert normalize_hypothesis("2024-йил") == "ikki ming yigirma toʻrtinchi yil"


def test_cardinal_without_hyphen_unchanged():
    assert normalize_reference("137 kishi") == "bir yuz oʻttiz yetti kishi"
    assert normalize_reference("3 kun") == "uch kun"


def test_numbers_get_okina_after_clean():
    assert normalize_reference("137") == "bir yuz oʻttiz yetti"
    assert normalize_reference("2024").startswith("ikki ming yigirma toʻrt")


def test_thousands_separator():
    assert normalize_reference("1,000,000") == "bir million"
    assert normalize_reference("1 000") == "bir ming"


def test_apostrophe_folding():
    assert clean("o'zbek tili") == "oʻzbek tili"
    assert clean("G'alaba") == "gʻalaba"
    assert clean("oʼzbek") == "oʻzbek"  # U+02BC also folds


def test_ascii_apostrophe_option():
    n = UzbekNormalizer(apostrophe="'")
    assert n.normalize("o'zbek") == "o'zbek"


def test_cyrillic_to_latin():
    assert cyrillic_to_latin("ўзбек") == "oʻzbek"
    assert cyrillic_to_latin("қалам") == "qalam"
    assert cyrillic_to_latin("ертага") == "yertaga"  # leading е -> ye
    assert cyrillic_to_latin("мен") == "men"          # internal е -> e
    assert cyrillic_to_latin("шаҳар") == "shahar"


def test_drop_tags():
    assert normalize_reference("salom noise dunyo") == "salom dunyo"
    assert normalize_hypothesis("salom hesitation dunyo") == "salom dunyo"


def test_hypothesis_matches_reference_across_scripts():
    assert normalize_hypothesis("Салом") == normalize_reference("salom")
    assert normalize_hypothesis("Ғалаба") == normalize_reference("gʻalaba")


def test_punctuation_stripped():
    assert normalize_reference("Salom, dunyo!") == "salom dunyo"
    assert normalize_reference("«iqtibos»") == "iqtibos"


def test_general_keeps_tags_and_transliterates():
    out = normalize("Салом noise")
    assert out.split()[0] == "salom"
    assert "noise" in out.split()  # general mode does not drop tags


def test_disable_ordinals():
    n = UzbekNormalizer(ordinals=False)
    assert n.normalize("5-sinf") == "beshsinf"  # no ordinal, hyphen stripped


def test_empty_and_none():
    assert normalize_reference("") == ""
    assert normalize_reference(None) == ""


# --- source-artifact folding (symmetric on ref + hyp) -------------------------

def test_cyrillic_homoglyph_macron_u():
    # Cyrillic "ӯ"/"Ӯ" (U+04EF/04EE) used for Uzbek Latin "oʻ" in otherwise-Latin text.
    assert clean("Ӯzbekiston") == "oʻzbekiston"
    assert normalize_reference("Ӯzbekistonda ӯz") == "oʻzbekistonda oʻz"
    # also reachable via the transliteration map (hypothesis path)
    assert cyrillic_to_latin("ӯзбек") == "oʻzbek"


def test_stray_cyrillic_a_homoglyph():
    assert clean("sаlom") == "salom"  # the "а" here is Cyrillic U+0430


def test_zero_width_and_bom_stripped():
    assert normalize_reference("﻿agar") == "agar"          # BOM
    assert clean("so​lom") == "solom"                      # zero-width space


def test_unicode_hyphen_variants_merge():
    # Non-breaking / figure / horizontal-bar hyphens merge like a plain "-".
    assert clean("narx‑navo") == "narxnavo"   # non-breaking hyphen
    assert clean("ob‐havo") == "obhavo"       # hyphen U+2010
    assert clean("ob-havo") == "obhavo"            # plain hyphen (baseline)


def test_vulgar_fractions_stripped():
    # ½ ¼ ¾ are stripped like other symbols; surrounding digits are still spelled.
    assert normalize_reference("29¾ duym") == "yigirma toʻqqiz duym"
    assert normalize_reference("24½ duym") == "yigirma toʻrt duym"


def test_artifacts_are_symmetric():
    # A reference with a homoglyph and a clean Latin hypothesis must match.
    assert normalize_reference("Ӯzbekiston") == normalize_hypothesis("Oʻzbekiston")
