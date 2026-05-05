"""Tests for search() and snippet logic."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from zkm.index import build_index, save_index
from zkm.query import _temporal_filter, search
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


# ---------------------------------------------------------------------------
# Temporal filtering
# ---------------------------------------------------------------------------


def test_temporal_filter_last_month() -> None:
    today = date.today()
    first_this = today.replace(day=1)
    end = first_this - timedelta(days=1)
    start = end.replace(day=1)
    assert _temporal_filter("what are last month's highlights") == (start, end)


def test_temporal_filter_this_month() -> None:
    today = date.today()
    result = _temporal_filter("this month's expenses")
    assert result is not None
    assert result[0] == today.replace(day=1)
    assert result[1] == today


def test_temporal_filter_this_year() -> None:
    today = date.today()
    result = _temporal_filter("what happened this year?")
    assert result == (date(today.year, 1, 1), today)


def test_temporal_filter_none_for_plain_query() -> None:
    assert _temporal_filter("electricity bill stadtwerke") is None


def test_temporal_search_returns_date_filtered_docs(store: Path) -> None:
    today = date.today()
    first_this = today.replace(day=1)
    last_month_end = first_this - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    last_month_mid = last_month_start.replace(day=min(15, last_month_end.day))
    old_date = "2018-03-01"

    _write_note(store, "notes/recent.md", "meeting with Frank",
                f"date: {last_month_mid.isoformat()}\nsource: notes")
    _write_note(store, "notes/old.md", "meeting with Frank",
                f"date: {old_date}\nsource: notes")
    idx = build_index(store)
    save_index(store, idx)

    hits = search(store, "what happened last month?")
    paths = [h.path for h in hits]
    assert "notes/recent.md" in paths
    assert "notes/old.md" not in paths


def test_temporal_search_most_recent_first(store: Path) -> None:
    today = date.today()
    first_this = today.replace(day=1)
    last_month_end = first_this - timedelta(days=1)
    day1 = last_month_end.replace(day=1)
    day15 = last_month_end.replace(day=min(15, last_month_end.day))

    _write_note(store, "notes/early.md", "early note", f"date: {day1.isoformat()}\nsource: notes")
    _write_note(store, "notes/later.md", "later note", f"date: {day15.isoformat()}\nsource: notes")
    idx = build_index(store)
    save_index(store, idx)

    hits = search(store, "last month highlights")
    assert hits[0].path == "notes/later.md"  # more recent first


def test_temporal_search_falls_back_on_empty_window(store: Path) -> None:
    """If no docs fall in the date window, all docs are returned (fallback)."""
    _write_note(store, "notes/old.md", "some content", "date: 2018-01-01\nsource: notes")
    idx = build_index(store)
    save_index(store, idx)

    hits = search(store, "last month recap")
    # Falls back to full corpus — old doc still returned
    assert len(hits) == 1
