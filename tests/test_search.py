"""Tests for search() and snippet logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from zkm.index import build_index, save_index
from zkm.query import search
from zkm.store import init_store


@pytest.fixture()
def store(tmp_path: Path) -> Path:
    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    return sdir


def _write_note(store: Path, rel: str, body: str, frontmatter: str = "") -> Path:
    path = store / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = f"---\n{frontmatter}\n---\n" if frontmatter else ""
    path.write_text(fm + body)
    return path


@pytest.fixture()
def indexed_store(store: Path) -> Path:
    _write_note(store, "notes/apples.md", "apples and oranges", "date: 2026-01-01\nsource: notes")
    _write_note(
        store, "notes/oranges.md", "oranges only, no apples here", "date: 2026-01-02\nsource: notes"
    )
    _write_note(store, "notes/bananas.md", "bananas are yellow", "date: 2026-01-03\nsource: notes")
    idx = build_index(store)
    save_index(store, idx)
    return store


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def test_search_oranges_returns_relevant_docs(indexed_store: Path) -> None:
    hits = search(indexed_store, "oranges")
    assert len(hits) >= 2
    paths = [h.path for h in hits]
    assert "notes/oranges.md" in paths
    assert "notes/apples.md" in paths
    bananas_pos = next((i for i, h in enumerate(hits) if "bananas" in h.path), None)
    assert bananas_pos is None or bananas_pos > 1


def test_search_returns_positive_scores(indexed_store: Path) -> None:
    hits = search(indexed_store, "oranges")
    assert all(h.score > 0 for h in hits)


def test_search_no_match_returns_empty(indexed_store: Path) -> None:
    hits = search(indexed_store, "zzznomatchzzz")
    assert hits == []


def test_search_top_k_limits_results(indexed_store: Path) -> None:
    hits = search(indexed_store, "oranges apples bananas", top_k=1)
    assert len(hits) == 1


def test_search_includes_date(indexed_store: Path) -> None:
    hits = search(indexed_store, "oranges", top_k=1)
    assert hits[0].date != ""


# ---------------------------------------------------------------------------
# Snippet
# ---------------------------------------------------------------------------


def test_snippet_contains_query_term(indexed_store: Path) -> None:
    hits = search(indexed_store, "oranges", top_k=1)
    assert hits[0].snippet != ""
    assert "orange" in hits[0].snippet.lower()


def test_snippet_fallback_to_body_head(indexed_store: Path) -> None:
    """When query term only in frontmatter (not body), snippet falls back to body head."""
    _write_note(indexed_store, "notes/meta_only.md", "Some unrelated body text here.",
                "tags: [quux]\nsource: notes")
    idx = build_index(indexed_store)
    save_index(indexed_store, idx)

    hits = search(indexed_store, "quux", top_k=1)
    assert len(hits) == 1
    # Snippet is not empty — falls back to body head
    assert hits[0].snippet != ""


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_search_raises_when_no_index(store: Path) -> None:
    with pytest.raises(FileNotFoundError, match="zkm index"):
        search(store, "anything")
