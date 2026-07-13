"""Tests for zkm.extraction_cache.ExtractionCache."""

from __future__ import annotations

import json
from pathlib import Path

from zkm.extraction_cache import _SCHEMA_VERSION, _STATE_DIR, ExtractionCache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SHA = "a" * 64  # fake 64-char hex digest
SHA2 = "b" * 64

ENTITIES = [{"type": "person", "value": "Frank Müller"}]
ENTITIES2 = [{"type": "org", "value": "Stadtwerke"}]


def make_cache(store: Path, extractor: str = "ner") -> ExtractionCache:
    return ExtractionCache(store, extractor_name=extractor)


# ---------------------------------------------------------------------------
# Miss cases
# ---------------------------------------------------------------------------


def test_miss_on_empty_store(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    assert cache.get(SHA, model_name="spacy", model_version="3.7.2") is None


def test_miss_different_model_version(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")
    assert cache.get(SHA, model_name="spacy", model_version="3.8.0") is None


def test_miss_different_model_name(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")
    assert cache.get(SHA, model_name="gliner", model_version="0.2.0") is None


def test_miss_different_body_sha256(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")
    assert cache.get(SHA2, model_name="spacy", model_version="3.7.2") is None


# ---------------------------------------------------------------------------
# Hit cases
# ---------------------------------------------------------------------------


def test_hit_returns_entities(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")
    result = cache.get(SHA, model_name="spacy", model_version="3.7.2")
    assert result == ENTITIES


def test_hit_empty_entity_list(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, [], model_name="spacy", model_version="3.7.2")
    assert cache.get(SHA, model_name="spacy", model_version="3.7.2") == []


def test_multiple_model_variants_coexist(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")
    cache.put(SHA, ENTITIES2, model_name="gliner", model_version="0.2.0")

    assert cache.get(SHA, model_name="spacy", model_version="3.7.2") == ENTITIES
    assert cache.get(SHA, model_name="gliner", model_version="0.2.0") == ENTITIES2


def test_put_overwrites_existing_variant(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")
    cache.put(SHA, ENTITIES2, model_name="spacy", model_version="3.7.2")
    assert cache.get(SHA, model_name="spacy", model_version="3.7.2") == ENTITIES2


def test_overwrite_preserves_other_variants(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")
    cache.put(SHA, ENTITIES2, model_name="gliner", model_version="0.2.0")
    # Overwrite spaCy variant
    cache.put(SHA, [{"type": "loc", "value": "Berlin"}], model_name="spacy", model_version="3.7.2")
    # GLiNER variant must still be intact
    assert cache.get(SHA, model_name="gliner", model_version="0.2.0") == ENTITIES2


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------


def test_schema_version_bump_causes_miss(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")

    # Corrupt the schema version on disk
    path = cache._entry_path(SHA)
    data = json.loads(path.read_text())
    data["_schema_version"] = _SCHEMA_VERSION + 99
    path.write_text(json.dumps(data))

    assert cache.get(SHA, model_name="spacy", model_version="3.7.2") is None


def test_schema_version_bump_put_overwrites(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")

    # Corrupt the schema version on disk
    path = cache._entry_path(SHA)
    data = json.loads(path.read_text())
    data["_schema_version"] = _SCHEMA_VERSION + 99
    path.write_text(json.dumps(data))

    # A fresh put should recover: old variants (from stale schema) are dropped
    cache.put(SHA, ENTITIES2, model_name="spacy", model_version="3.7.2")
    assert cache.get(SHA, model_name="spacy", model_version="3.7.2") == ENTITIES2


# ---------------------------------------------------------------------------
# Isolation between extractors
# ---------------------------------------------------------------------------


def test_different_extractors_independent(tmp_path: Path) -> None:
    ner_cache = make_cache(tmp_path, extractor="ner")
    receipt_cache = make_cache(tmp_path, extractor="receipt")

    ner_cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")

    assert ner_cache.get(SHA, model_name="spacy", model_version="3.7.2") == ENTITIES
    assert receipt_cache.get(SHA, model_name="spacy", model_version="3.7.2") is None


def test_different_extractors_separate_dirs(tmp_path: Path) -> None:
    ner_cache = make_cache(tmp_path, extractor="ner")
    receipt_cache = make_cache(tmp_path, extractor="receipt")

    ner_cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")
    receipt_cache.put(SHA, ENTITIES2, model_name="spacy", model_version="3.7.2")

    ner_dir = tmp_path / _STATE_DIR / "ner"
    receipt_dir = tmp_path / _STATE_DIR / "receipt"
    assert ner_dir.exists()
    assert receipt_dir.exists()
    assert ner_dir != receipt_dir


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


def test_corrupted_json_treated_as_miss(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")

    path = cache._entry_path(SHA)
    path.write_bytes(b"not json{{{")

    assert cache.get(SHA, model_name="spacy", model_version="3.7.2") is None


def test_file_layout_uses_sha_prefix(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.put(SHA, ENTITIES, model_name="spacy", model_version="3.7.2")

    expected = tmp_path / _STATE_DIR / "ner" / (SHA[:2]) / f"{SHA[2:]}.json"
    assert expected.exists()
