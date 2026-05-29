"""Tests using pathological fixtures that document known edge cases.

These tests assert invariants about the indexing/embedding pipeline's
behaviour under stress or known-bad input — not regressions to fix,
but documented limitations and safeguards.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import frontmatter
import pytest

from zkm.embed import _MAX_PREFIX_CHARS, _chunk_texts
from zkm.index import _tokenize_doc, build_index
from zkm.store import init_store

PATHOLOGICAL_DIR = Path(__file__).parent / "fixtures" / "pathological"


@pytest.fixture()
def store(tmp_path: Path) -> Path:
    s = tmp_path / "store"
    init_store(s, backend="none")
    return s


def _copy_fixture(fixture_name: str, store: Path, subdir: str = "notes") -> Path:
    src = PATHOLOGICAL_DIR / fixture_name
    dst = store / subdir / fixture_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


# ---------------------------------------------------------------------------
# oversized_entities.md — prefix cap
# ---------------------------------------------------------------------------


def test_chunk_prefix_capped_for_oversized_entities(store: Path) -> None:
    """_chunk_texts caps the metadata prefix at _MAX_PREFIX_CHARS even when
    entities[] total value length exceeds that limit.

    Regression: before the cap was added, a doc with ~75 entities (22k chars)
    produced chunks >8192 tokens that bge-m3 rejected with HTTP 500.
    """
    _copy_fixture("oversized_entities.md", store)

    idx = build_index(store)
    assert idx.docs, "fixture must be indexed"
    doc = next(d for d in idx.docs if "oversized_entities" in d.rel_path)

    chunks = _chunk_texts(store, doc)
    assert chunks, "should produce at least one chunk"

    # Each chunk = capped_prefix + "\n" + body_window
    # Body window default is 2000 chars; prefix must be ≤ _MAX_PREFIX_CHARS.
    default_chunk_chars = 2000
    for chunk in chunks:
        assert len(chunk) <= _MAX_PREFIX_CHARS + default_chunk_chars + 1, (
            f"chunk length {len(chunk)} exceeds prefix cap ({_MAX_PREFIX_CHARS}) "
            f"+ body window ({default_chunk_chars})"
        )


def test_oversized_entities_raw_prefix_exceeds_cap() -> None:
    """Verify the fixture actually has enough entity data to trigger the cap
    (otherwise the test above is vacuous)."""
    fixture = PATHOLOGICAL_DIR / "oversized_entities.md"
    post = frontmatter.load(str(fixture))

    entity_parts = [
        str(e.get("value", ""))
        for e in post.metadata.get("entities", [])
        if isinstance(e, dict) and e.get("valid", True) is not False
    ]
    raw_entity_str = " ".join(entity_parts)
    assert len(raw_entity_str) > _MAX_PREFIX_CHARS, (
        f"fixture entity string is only {len(raw_entity_str)} chars; "
        f"must exceed _MAX_PREFIX_CHARS={_MAX_PREFIX_CHARS} to test the cap"
    )


# ---------------------------------------------------------------------------
# html_entity_ner.md — valid:false skip
# ---------------------------------------------------------------------------


def test_tokenize_doc_skips_invalid_entities() -> None:
    """_tokenize_doc excludes entities with valid:false from BM25 tokens.

    HTML-entity artifact strings (e.g. '&gt;&nbsp;') are marked valid:false
    by the NER scrub pipeline. They must not pollute the BM25 index.
    """
    fixture = PATHOLOGICAL_DIR / "html_entity_ner.md"
    post = frontmatter.load(str(fixture))
    tokens = _tokenize_doc(post)
    token_text = " ".join(tokens)

    # Artifact strings must be absent from tokens
    for artifact in ("&gt;", "&nbsp;", "&gt;&nbsp;"):
        assert artifact not in token_text, (
            f"HTML-entity artifact {artifact!r} should be skipped (valid:false)"
        )

    # The legitimate entity must be present
    assert "actual" in token_text, (
        "Actual Company GmbH (valid:true) should be tokenised"
    )


def test_chunk_texts_skips_invalid_entities(store: Path) -> None:
    """_chunk_texts excludes valid:false entities from the embed prefix."""
    _copy_fixture("html_entity_ner.md", store)

    idx = build_index(store)
    doc = next(d for d in idx.docs if "html_entity" in d.rel_path)
    chunks = _chunk_texts(store, doc)

    chunk_text = "\n".join(chunks)
    for artifact in ("&gt;", "&nbsp;"):
        assert artifact not in chunk_text, (
            f"HTML-entity artifact {artifact!r} must not appear in embed chunks"
        )


# ---------------------------------------------------------------------------
# subject_only.md — subject field not indexed by BM25
# ---------------------------------------------------------------------------


def test_subject_field_not_indexed_by_bm25(store: Path) -> None:
    """BM25 does not index the 'subject' frontmatter field — only 'title'.

    This is a known limitation: zkm-eml writes subject:, not title:, so
    email subject lines are invisible to the search index unless the converter
    is fixed to copy subject → title.

    See index.py:65 (reads title) and embed.py:479 (reads title).
    """
    _copy_fixture("subject_only.md", store)

    idx = build_index(store)
    assert idx.docs, "fixture must be indexed"

    doc = next(d for d in idx.docs if "subject_only" in d.rel_path)
    token_text = " ".join(doc.tokens)

    # The unique subject term must NOT appear in the token list
    assert "xyloquintet" not in token_text, (
        "subject: field should not be tokenised; only title: is indexed"
    )
    assert "uniquesubjectterm" not in token_text, (
        "subject: field should not be tokenised; only title: is indexed"
    )
