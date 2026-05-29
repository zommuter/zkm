"""Tests against the committed synthetic corpus.

The corpus under tests/fixtures/corpus/ is generated from deterministic .eml
fixtures (see plugins/zkm-eml/scripts/generate_corpus.py) and committed as
opaque static input — core never imports zkm_eml at test time.

Staleness is signalled by the zkm-eml roundtrip test going red:
  cd plugins/zkm-eml && uv run pytest tests/test_corpus_roundtrip.py

To regenerate:
  cd plugins/zkm-eml && uv run python scripts/generate_corpus.py
  # then run convert over the .eml fixtures into a scratch store
  # and copy mail/messages/**/*.md into tests/fixtures/corpus/mail/
  # update CORPUS_MANIFEST.json
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from zkm.index import build_index, save_index
from zkm.query import search
from zkm.store import init_store

CORPUS = Path(__file__).parent / "fixtures" / "corpus"
MANIFEST = CORPUS / "CORPUS_MANIFEST.json"
MESSAGES_DIR = CORPUS / "mail" / "messages"


@pytest.fixture()
def corpus_store(tmp_path: Path) -> Path:
    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    dest = sdir / "mail" / "messages"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(MESSAGES_DIR, dest, dirs_exist_ok=True)
    return sdir


def test_corpus_manifest_exists() -> None:
    assert MANIFEST.exists(), "CORPUS_MANIFEST.json missing — regenerate corpus"
    data = json.loads(MANIFEST.read_text())
    assert "processor_version" in data
    assert "inputs" in data
    assert len(data["inputs"]) == 5


def test_corpus_indexes_cleanly(corpus_store: Path) -> None:
    idx = build_index(corpus_store)
    assert len(idx.docs) == 5, f"Expected 5 corpus docs, got {len(idx.docs)}"


def test_corpus_no_import_zkm_eml() -> None:
    """Core corpus test must not import the plugin."""
    import sys
    assert "zkm_eml" not in sys.modules, "core corpus test imported zkm_eml"


def test_corpus_searchable_by_body_token(corpus_store: Path) -> None:
    idx = build_index(corpus_store)
    save_index(corpus_store, idx)

    hits = search(corpus_store, "invoice")
    paths = [h.path for h in hits]
    assert any("invoice-for-march-services" in p for p in paths), (
        f"Expected invoice doc in hits, got: {paths}"
    )


def test_corpus_searchable_by_participant(corpus_store: Path) -> None:
    idx = build_index(corpus_store)
    save_index(corpus_store, idx)

    hits = search(corpus_store, "alice@example.com")
    assert len(hits) >= 1, "alice@example.com should match at least one doc"


def test_corpus_subject_not_in_bm25_title_slot(corpus_store: Path) -> None:
    """'subject' is not indexed via the title slot — searching for the subject
    token only hits because it appears in the body or is a tokenized word.

    This test documents the title/subject drift trap: if the converter ever
    starts writing 'title' instead of 'subject', the BM25 title-slot search
    below would suddenly get a stronger signal for the subject token.
    The trap is primarily caught by the zkm-eml roundtrip test asserting
    'title' is absent from frontmatter; this test documents the indexer side.
    """
    idx = build_index(corpus_store)
    # No doc has frontmatter 'title:' — all have 'subject:'. The indexer
    # reads 'title' at index.py:65; subject is NOT indexed via that slot.
    for doc in idx.docs:
        assert "title" not in doc.metadata, (
            f"{doc.rel_path} has unexpected 'title' in metadata — converter drift?"
        )
