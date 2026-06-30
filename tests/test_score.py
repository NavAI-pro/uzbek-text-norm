"""Tests for the manifest scorer. Skipped if `jiwer` is not installed."""
import json

import pytest

from uzbek_text_norm import score_manifest, score_pairs

pytest.importorskip("jiwer")  # scoring needs jiwer ([score] extra)


def test_perfect_match():
    r = score_pairs(["salom dunyo"], ["salom dunyo"])
    assert r["wer"] == 0.0 and r["cer"] == 0.0 and r["n"] == 1


def test_cyrillic_hypothesis_matches_latin_reference():
    # model emits Cyrillic, gold is Latin -> normalization makes them match
    assert score_pairs(["gʻalaba"], ["Ғалаба"])["wer"] == 0.0


def test_numbers_normalized_before_scoring():
    assert score_pairs(["2024-yil"], ["ikki ming yigirma toʻrtinchi yil"])["wer"] == 0.0


def test_real_error_is_counted():
    r = score_pairs(["salom aziz dunyo"], ["salom dunyo"])  # one deletion of 3 words
    assert r["wer"] == pytest.approx(33.33, abs=0.1)


def test_score_manifest_jsonl(tmp_path):
    p = tmp_path / "m.jsonl"
    rows = [
        {"text": "salom dunyo", "pred": "salom dunyo", "dataset": "a"},
        {"text": "gʻalaba", "pred": "Ғалаба", "dataset": "b"},
    ]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    res = score_manifest(str(p), ref_field="text", hyp_field="pred", by="dataset")
    assert res["overall"]["n"] == 2
    assert res["overall"]["wer"] == 0.0
    assert set(res["groups"]) == {"a", "b"}


def test_score_manifest_json_array(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps([{"text": "bir ikki", "pred": "bir ikki"}]), encoding="utf-8")
    assert score_manifest(str(p), hyp_field="pred")["overall"]["n"] == 1


def test_empty_hypothesis_skipped_by_default(tmp_path):
    p = tmp_path / "m.jsonl"
    rows = [{"text": "salom", "pred": "salom"}, {"text": "dunyo", "pred": ""}]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert score_manifest(str(p), hyp_field="pred")["overall"]["n"] == 1
