"""Tests for LLM query expansion: parsing, RRF merge, caching, fallback."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from zkm.expand import _parse_hypothetical, _parse_keywords, expand_query
from zkm.index import tokenize
from zkm.query import Hit, rrf_merge
from zkm.store import init_store


@pytest.fixture()
def store(tmp_path: Path) -> Path:
    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    return sdir


# ---------------------------------------------------------------------------
# _parse_keywords
# ---------------------------------------------------------------------------


def test_parse_keywords_numbered_list() -> None:
    text = "1. electricity bill\n2. Stromrechnung\n3. utility invoice\n\nSome sentence."
    kws = _parse_keywords(text)
    assert "electricity bill" in kws
    assert "Stromrechnung" in kws
    assert "utility invoice" in kws
    assert len(kws) <= 5


def test_parse_keywords_bullet_list() -> None:
    text = "- power costs\n- Stadtwerke\n- energy bill\n\nHypothetical."
    kws = _parse_keywords(text)
    assert "power costs" in kws
    assert "Stadtwerke" in kws


def test_parse_keywords_stops_at_blank_line() -> None:
    text = "term one\nterm two\n\nThis is the hypothetical answer sentence."
    kws = _parse_keywords(text)
    assert "term one" in kws
    assert "term two" in kws
    assert not any("hypothetical" in k.lower() for k in kws)


def test_parse_keywords_drops_prose_lines() -> None:
    # Lines with more than 5 words are treated as prose and skipped
    text = "good term\nThis is a very long line that should be skipped entirely\nother term"
    kws = _parse_keywords(text)
    assert "good term" in kws
    assert "other term" in kws
    assert not any("long line" in k for k in kws)


def test_parse_keywords_caps_at_five() -> None:
    lines = "\n".join(f"term{i}" for i in range(10))
    kws = _parse_keywords(lines)
    assert len(kws) <= 5


def test_parse_keywords_empty_input() -> None:
    assert _parse_keywords("") == []


# ---------------------------------------------------------------------------
# _parse_hypothetical
# ---------------------------------------------------------------------------


def test_parse_hypothetical_returns_tokens_after_blank_line() -> None:
    text = "keyword one\nkeyword two\n\nThe electricity bill from Stadtwerke was 142 CHF."
    tokens = _parse_hypothetical(text)
    assert len(tokens) > 0
    # Should contain tokens from the hypothetical sentence
    all_text = " ".join(tokens)
    assert any(t in all_text for t in ["elektr", "electricity", "stadtwerk", "stadtwerke"])


def test_parse_hypothetical_no_blank_line_returns_empty() -> None:
    assert _parse_hypothetical("just keywords\nno blank line") == []


# ---------------------------------------------------------------------------
# rrf_merge
# ---------------------------------------------------------------------------


def _make_hit(path: str, score: float = 1.0) -> Hit:
    return Hit(path=path, score=score, date="", snippet="")


def test_rrf_merge_basic_ordering() -> None:
    """Doc ranked first in both lists should win; doc only in one list ranks lower."""
    list1 = [_make_hit("a.md"), _make_hit("b.md"), _make_hit("c.md")]
    list2 = [_make_hit("a.md"), _make_hit("c.md"), _make_hit("d.md")]

    merged = rrf_merge([list1, list2])
    paths = [h.path for h in merged]

    assert paths[0] == "a.md"  # ranked 1st in both → highest RRF score
    assert "b.md" in paths
    assert "c.md" in paths
    assert "d.md" in paths


def test_rrf_merge_deduplicates() -> None:
    """Same path appearing in multiple lists must appear only once in output."""
    list1 = [_make_hit("x.md"), _make_hit("y.md")]
    list2 = [_make_hit("x.md"), _make_hit("z.md")]

    merged = rrf_merge([list1, list2])
    paths = [h.path for h in merged]
    assert paths.count("x.md") == 1


def test_rrf_merge_empty_lists() -> None:
    assert rrf_merge([]) == []
    assert rrf_merge([[], []]) == []


def test_rrf_merge_single_list_preserves_order() -> None:
    hits = [_make_hit("a.md", 3.0), _make_hit("b.md", 2.0), _make_hit("c.md", 1.0)]
    merged = rrf_merge([hits])
    assert [h.path for h in merged] == ["a.md", "b.md", "c.md"]


# ---------------------------------------------------------------------------
# expand_query — cache
# ---------------------------------------------------------------------------


def test_expand_query_caches_result(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Second call with same question uses cache; LLM is called exactly once."""
    call_count = [0]

    class MockResp:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            call_count[0] += 1
            return {
                "choices": [{"message": {"content": "electricity\nStromrechnung\n\nA bill."}}]
            }

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: MockResp())

    expand_query("what was my electricity bill?", store, "http://localhost", "m", "")
    expand_query("what was my electricity bill?", store, "http://localhost", "m", "")

    assert call_count[0] == 1  # second call served from cache


def test_expand_query_fallback_on_llm_error(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When LLM is unreachable, expansion returns [tokenize(question)] without raising."""
    def mock_post(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", mock_post)

    result = expand_query("electricity bill", store, "http://localhost:9999", "m", "")
    assert len(result) == 1
    assert result[0] == tokenize("electricity bill")


def test_expand_query_returns_multiple_variants_on_success(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful LLM call yields raw-question tokens + keyword variants + hypothetical."""
    llm_output = (
        "Stromrechnung\n"
        "electricity bill\n"
        "Stadtwerke Rechnung\n"
        "\n"
        "The electricity bill from Stadtwerke was 142 CHF in March."
    )

    class MockResp:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"choices": [{"message": {"content": llm_output}}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: MockResp())

    result = expand_query("what was my last electricity bill?", store, "http://x", "m", "")
    # Should have raw query + at least 2 keyword variants + hypothetical
    assert len(result) >= 3
    # First entry is always the raw question tokens
    assert result[0] == tokenize("what was my last electricity bill?")
