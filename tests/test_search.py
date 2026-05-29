"""Tests for search() and snippet logic."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import pytest

from zkm.index import build_index, save_index
from zkm.query import _temporal_filter, search


@pytest.fixture()
def indexed_store(store: Path, make_note: Callable[..., Path]) -> Path:
    make_note("notes/apples.md", "apples and oranges", "date: 2026-01-01\nsource: notes")
    make_note(
        "notes/oranges.md", "oranges only, no apples here", "date: 2026-01-02\nsource: notes"
    )
    make_note("notes/bananas.md", "bananas are yellow", "date: 2026-01-03\nsource: notes")
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


def test_search_stem_match_across_inflections(indexed_store: Path) -> None:
    """Querying the stem form 'orange' should match docs containing 'oranges'."""
    hits = search(indexed_store, "orange")
    paths = [h.path for h in hits]
    assert "notes/oranges.md" in paths or "notes/apples.md" in paths


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


def test_snippet_fallback_to_body_head(
    indexed_store: Path, make_note: Callable[..., Path]
) -> None:
    """When query term only in frontmatter (not body), snippet falls back to body head."""
    make_note("notes/meta_only.md", "Some unrelated body text here.",
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


# Natural German phrases — these should all activate the last-month filter.
# The earlier implementation only had "vorigen monat"; "letzten Monat" is far
# more common and was silently falling through, causing temporal search to
# ignore the date window and return docs from any year.
def test_temporal_filter_german_letzten_monat() -> None:
    today = date.today()
    first_this = today.replace(day=1)
    end = first_this - timedelta(days=1)
    start = end.replace(day=1)
    assert _temporal_filter("Rechnungen von letzten Monat") == (start, end)


def test_temporal_filter_german_letztem_monat() -> None:
    today = date.today()
    first_this = today.replace(day=1)
    end = first_this - timedelta(days=1)
    start = end.replace(day=1)
    assert _temporal_filter("was ist im letztem Monat passiert?") == (start, end)


def test_temporal_filter_german_vergangenen_monat() -> None:
    today = date.today()
    first_this = today.replace(day=1)
    end = first_this - timedelta(days=1)
    start = end.replace(day=1)
    assert _temporal_filter("Ausgaben vom vergangenen Monat") == (start, end)


def test_temporal_filter_german_letzte_woche() -> None:
    today = date.today()
    start = today - timedelta(days=today.weekday() + 7)
    expected = (start, start + timedelta(days=6))
    assert _temporal_filter("was ist letzte Woche passiert?") == expected


def test_temporal_filter_german_kueerzlich() -> None:
    today = date.today()
    result = _temporal_filter("kürzlich empfangene Mails")
    assert result is not None
    assert result[1] == today


def test_temporal_filter_german_neulich() -> None:
    result = _temporal_filter("neulich gesendete Nachrichten")
    assert result is not None


def test_temporal_filter_german_letztes_jahr() -> None:
    today = date.today()
    y = today.year - 1
    assert _temporal_filter("Berichte vom letzten Jahr") == (date(y, 1, 1), date(y, 12, 31))


def test_temporal_search_respects_date_window_for_german_query(
    store: Path, make_note: Callable[..., Path]
) -> None:
    """German 'letzten Monat' must activate the temporal filter so old docs are excluded.

    Regression test: before the fix, unrecognised German phrases fell through to plain
    BM25 with no date window, surfacing documents from any year.
    """
    today = date.today()
    first_this = today.replace(day=1)
    last_month_end = first_this - timedelta(days=1)
    last_month_mid = last_month_end.replace(day=min(15, last_month_end.day))

    make_note(
        "notes/recent_bill.md", "Rechnung Stadtwerke Mai",
        f"date: {last_month_mid.isoformat()}\nsource: notes"
    )
    make_note(
        "notes/old_bill.md", "Rechnung Stadtwerke 2012",
        "date: 2012-03-01\nsource: notes"
    )
    idx = build_index(store)
    save_index(store, idx)

    hits = search(store, "Rechnungen von letzten Monat")
    paths = [h.path for h in hits]
    assert "notes/recent_bill.md" in paths
    assert "notes/old_bill.md" not in paths


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


def test_temporal_search_returns_date_filtered_docs(
    store: Path, make_note: Callable[..., Path]
) -> None:
    today = date.today()
    first_this = today.replace(day=1)
    last_month_end = first_this - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    last_month_mid = last_month_start.replace(day=min(15, last_month_end.day))
    old_date = "2018-03-01"

    make_note("notes/recent.md", "meeting with Frank",
              f"date: {last_month_mid.isoformat()}\nsource: notes")
    make_note("notes/old.md", "meeting with Frank",
              f"date: {old_date}\nsource: notes")
    idx = build_index(store)
    save_index(store, idx)

    hits = search(store, "what happened last month?")
    paths = [h.path for h in hits]
    assert "notes/recent.md" in paths
    assert "notes/old.md" not in paths


def test_temporal_search_most_recent_first(
    store: Path, make_note: Callable[..., Path]
) -> None:
    today = date.today()
    first_this = today.replace(day=1)
    last_month_end = first_this - timedelta(days=1)
    day1 = last_month_end.replace(day=1)
    day15 = last_month_end.replace(day=min(15, last_month_end.day))

    make_note("notes/early.md", "early note", f"date: {day1.isoformat()}\nsource: notes")
    make_note("notes/later.md", "later note", f"date: {day15.isoformat()}\nsource: notes")
    idx = build_index(store)
    save_index(store, idx)

    hits = search(store, "last month highlights")
    assert hits[0].path == "notes/later.md"  # more recent first


def test_temporal_search_falls_back_on_empty_window(
    store: Path, make_note: Callable[..., Path]
) -> None:
    """If no docs fall in the date window, all docs are returned (fallback)."""
    make_note("notes/old.md", "some content", "date: 2018-01-01\nsource: notes")
    idx = build_index(store)
    save_index(store, idx)

    hits = search(store, "last month recap")
    # Falls back to full corpus — old doc still returned
    assert len(hits) == 1
