"""Tests for LLM query expansion: parsing, RRF merge, caching, fallback."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from zkm.expand import (
    _EXPAND_COLD_TIMEOUT_DEFAULT,
    _EXPAND_TIMEOUT_DEFAULT,
    _PARSER_VERSION,
    _parse_hypothetical,
    _parse_hypothetical_text,
    _parse_keywords,
    _probe_model_loaded,
    expand_query,
    expand_query_with_hyp,
)
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


def test_parse_keywords_fallback_blank_line_when_no_section2_marker() -> None:
    # Without a "Section 2" marker the parser falls back to blank-line split.
    # The prose sentence is 7 words and would be filtered anyway, but the
    # blank-line split is the primary guard here.
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


def test_parse_keywords_caps_at_twelve() -> None:
    lines = "\n".join(f"term{i}" for i in range(20))
    kws = _parse_keywords(lines)
    assert len(kws) == 12


def test_parse_keywords_empty_input() -> None:
    assert _parse_keywords("") == []


def test_parse_keywords_inline_comma_separated() -> None:
    """Model puts all keywords on one line after the section header — comma-separated."""
    text = (
        "Section 1 — Search terms: Rechnung, invoice, Faktura, bill\n"
        "\nSection 2 — Hypothetical answer: The invoice was 142 EUR."
    )
    kws = _parse_keywords(text)
    assert "Rechnung" in kws
    assert "invoice" in kws
    assert "Faktura" in kws
    assert "bill" in kws
    assert not any("Section" in k for k in kws)


def test_parse_keywords_inline_quoted_space_separated() -> None:
    """Model puts quoted terms space-separated on the section header line."""
    text = (
        'Section 1 — Search terms: "invoice" "payment" "Rechnung" "Betrag"\n'
        "\nSection 2 — Hypothetical answer: The electricity bill was 80 EUR."
    )
    kws = _parse_keywords(text)
    assert "invoice" in kws
    assert "payment" in kws
    assert "Rechnung" in kws
    assert not any("Section" in k for k in kws)


def test_parse_keywords_aya_markdown_blocked_format() -> None:
    """aya-expanse-8b emits **English:**/**German:** blocks with blank lines between them.
    Parser must cross blank lines (using Section 2 marker as boundary) and skip the
    markdown sub-headers, yielding at least one EN and one DE keyword.
    """
    text = (
        "## Section 1 — Search terms\n\n"
        "**English:**\n"
        "- Last electricity bill\n"
        "- electricity invoice\n\n"
        "**German:**\n"
        "- Letzte Stromrechnung\n"
        "- Stromkosten\n\n"
        "## Section 2 — Hypothetical Answer\n\n"
        "Die letzte Stromrechnung betrug 120 Euro."
    )
    kws = _parse_keywords(text)
    assert "Last electricity bill" in kws or "electricity invoice" in kws
    assert "Letzte Stromrechnung" in kws or "Stromkosten" in kws
    assert not any(k.startswith("**") or k.startswith("#") or "Section" in k for k in kws)


def test_parse_keywords_section_header_not_a_keyword() -> None:
    """The 'Section 1 — Search terms:' label itself must not appear in the result."""
    text = (
        "Section 1 — Search terms:\n- Rechnung\n- invoice\n\n"
        "Section 2 — Hypothetical answer: ..."
    )
    kws = _parse_keywords(text)
    assert not any("Section" in k or "Search" in k for k in kws)
    assert "Rechnung" in kws
    assert "invoice" in kws


def test_parse_keywords_section_header_no_colon() -> None:
    """Section label without trailing colon must not leak as a keyword."""
    text = "Section 1 — Search terms\n- Rechnung\n- invoice\n\nSection 2 — Hypothetical answer: ..."
    kws = _parse_keywords(text)
    assert not any("Section" in k or "Search" in k for k in kws)
    assert "Rechnung" in kws
    assert "invoice" in kws


def test_parse_keywords_aya_bilingual_six_plus_six() -> None:
    """aya-expanse-8b emits 6 EN + 6 DE phrases; all must survive the cap."""
    lines = (
        "electricity bill\n"
        "utility invoice\n"
        "energy costs\n"
        "power consumption bill\n"
        "monthly electricity charge\n"
        "energy invoice amount\n"
        "Stromrechnung\n"
        "Energiekosten\n"
        "Stadtwerke Rechnung\n"
        "monatliche Stromkosten\n"
        "Energieverbrauch Kosten\n"
        "letzte Stromrechnung\n"
        "\n"
        "The electricity bill from Stadtwerke was 120 EUR."
    )
    kws = _parse_keywords(lines)
    assert "electricity bill" in kws or "utility invoice" in kws
    assert "Stromrechnung" in kws or "letzte Stromrechnung" in kws
    assert len(kws) >= 10


# ---------------------------------------------------------------------------
# _parse_hypothetical / _parse_hypothetical_text
# ---------------------------------------------------------------------------


def test_parse_hypothetical_returns_tokens_after_blank_line() -> None:
    text = "keyword one\nkeyword two\n\nThe electricity bill from Stadtwerke was 142 CHF."
    tokens = _parse_hypothetical(text)
    assert len(tokens) > 0
    all_text = " ".join(tokens)
    assert any(t in all_text for t in ["elektr", "electricity", "stadtwerk", "stadtwerke"])


def test_parse_hypothetical_no_blank_line_returns_empty() -> None:
    assert _parse_hypothetical("just keywords\nno blank line") == []


def test_parse_hypothetical_text_strips_section2_label() -> None:
    """'Section 2 — Hypothetical answer:' prefix must be stripped from result."""
    text = "keywords\n\nSection 2 — Hypothetical answer: The bill was 80 EUR."
    hyp = _parse_hypothetical_text(text)
    assert hyp == "The bill was 80 EUR."
    assert "Section" not in hyp


def test_parse_hypothetical_text_section2_marker_no_blank_line() -> None:
    """When sections are separated by newline only (no blank line), still extracts hyp."""
    text = (
        "Section 1 — Search terms:\n- term one\n"
        "Section 2 — Hypothetical answer: It costs 80 EUR."
    )
    hyp = _parse_hypothetical_text(text)
    assert "80 EUR" in hyp
    assert "Section" not in hyp


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
    """Second call with same question+model uses cache; LLM is called exactly once."""
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

    expand_query("what was my electricity bill?", store, "http://localhost", "model-a", "")
    expand_query("what was my electricity bill?", store, "http://localhost", "model-a", "")

    assert call_count[0] == 1  # second call served from cache


def test_expand_query_cache_misses_on_different_model(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Switching models must not serve a cached result from a different model."""
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

    expand_query("what was my electricity bill?", store, "http://localhost", "model-a", "")
    expand_query("what was my electricity bill?", store, "http://localhost", "model-b", "")

    assert call_count[0] == 2  # different model → cache miss → two LLM calls


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


def test_expand_query_cache_misses_on_parser_version_bump(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache file from an old parser version is ignored and overwritten with the new version."""
    import json

    cache_file = store / ".zkm-index/expansion-cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps({"_parser_version": "v1", "entries": {"deadbeef": {"keywords": ["stale"]}}}),
        encoding="utf-8",
    )

    call_count = [0]

    class MockResp:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            call_count[0] += 1
            return {"choices": [{"message": {"content": "electricity\n\nA bill."}}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: MockResp())

    expand_query("what was my electricity bill?", store, "http://localhost", "model-a", "")
    assert call_count[0] == 1  # old entry ignored → LLM called

    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert data.get("_parser_version") == _PARSER_VERSION


def test_expand_query_legacy_cache_format_ignored(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Old flat-dict cache (no _parser_version key) is treated as empty."""
    import json

    cache_file = store / ".zkm-index/expansion-cache.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        json.dumps({"deadbeef": {"keywords": ["stale"]}}),
        encoding="utf-8",
    )

    call_count = [0]

    class MockResp:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            call_count[0] += 1
            return {"choices": [{"message": {"content": "electricity\n\nA bill."}}]}

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: MockResp())

    expand_query("what was my electricity bill?", store, "http://localhost", "model-a", "")
    assert call_count[0] == 1  # flat format → cache miss → LLM called

    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert "_parser_version" in data  # file now uses new envelope format


# ---------------------------------------------------------------------------
# _probe_model_loaded
# ---------------------------------------------------------------------------


def test_probe_model_loaded_returns_true_when_in_running_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockGetResp:
        status_code = 200
        def raise_for_status(self) -> None: pass
        def json(self) -> dict: return {"model": "aya-expanse-8b", "status": "running"}

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: MockGetResp())
    assert _probe_model_loaded("http://localhost:8080", "aya-expanse-8b") is True


def test_probe_model_loaded_returns_false_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockGetResp:
        status_code = 200
        def raise_for_status(self) -> None: pass
        def json(self) -> dict: return {"model": "qwen3.5-0.8b", "status": "running"}

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: MockGetResp())
    assert _probe_model_loaded("http://localhost:8080", "aya-expanse-8b") is False


def test_probe_model_loaded_returns_none_on_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MockGetResp:
        status_code = 404
        def raise_for_status(self) -> None: pass
        def json(self) -> dict: return {}

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: MockGetResp())
    assert _probe_model_loaded("http://localhost:8080", "aya-expanse-8b") is None


def test_probe_model_loaded_returns_none_on_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: (_ for _ in ()).throw(
        httpx.ConnectError("refused")
    ))
    assert _probe_model_loaded("http://localhost:8080", "aya-expanse-8b") is None


# ---------------------------------------------------------------------------
# Cold-aware timeout selection
# ---------------------------------------------------------------------------


class _FakePostResp:
    status_code = 200
    def raise_for_status(self) -> None: pass
    def json(self) -> dict:
        return {"choices": [{"message": {"content": "electricity\nStromrechnung\n\nA bill."}}]}


def test_expand_query_uses_cold_timeout_when_probe_returns_false(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When llama-swap reports the model is not loaded, use the cold timeout."""
    class MockGetResp:
        status_code = 200
        def raise_for_status(self) -> None: pass
        def json(self) -> dict: return {"model": "other-model"}  # aya not in response

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: MockGetResp())

    observed: list[float] = []

    def mock_post(*a, **kw: object) -> _FakePostResp:
        observed.append(float(kw.get("timeout", 0.0)))  # type: ignore[arg-type]
        return _FakePostResp()

    monkeypatch.setattr(httpx, "post", mock_post)
    expand_query_with_hyp("test question", store, "http://localhost:8080", "aya-expanse-8b", "")
    assert observed == [_EXPAND_COLD_TIMEOUT_DEFAULT]


def test_expand_query_uses_warm_timeout_when_probe_returns_true(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the model is already loaded, use the normal warm timeout."""
    class MockGetResp:
        status_code = 200
        def raise_for_status(self) -> None: pass
        def json(self) -> dict: return {"model": "aya-expanse-8b"}  # model IS loaded

    monkeypatch.setattr(httpx, "get", lambda *a, **kw: MockGetResp())

    observed: list[float] = []

    def mock_post(*a, **kw: object) -> _FakePostResp:
        observed.append(float(kw.get("timeout", 0.0)))  # type: ignore[arg-type]
        return _FakePostResp()

    monkeypatch.setattr(httpx, "post", mock_post)
    expand_query_with_hyp("test question", store, "http://localhost:8080", "aya-expanse-8b", "")
    assert observed == [_EXPAND_TIMEOUT_DEFAULT]


def test_expand_query_uses_warm_timeout_when_probe_returns_none(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the endpoint is not llama-swap (probe returns None), use the warm timeout."""
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: (_ for _ in ()).throw(
        Exception("not llama-swap")
    ))

    observed: list[float] = []

    def mock_post(*a, **kw: object) -> _FakePostResp:
        observed.append(float(kw.get("timeout", 0.0)))  # type: ignore[arg-type]
        return _FakePostResp()

    monkeypatch.setattr(httpx, "post", mock_post)
    expand_query_with_hyp("test question", store, "http://localhost:8080", "aya-expanse-8b", "")
    assert observed == [_EXPAND_TIMEOUT_DEFAULT]


# ---------------------------------------------------------------------------
# Typed failure reasons
# ---------------------------------------------------------------------------


def test_expand_query_with_hyp_returns_reason_timeout(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda *a, **kw: (_ for _ in ()).throw(Exception("no server"))
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: (_ for _ in ()).throw(
        httpx.TimeoutException("timed out")
    ))
    _, _, _, reason = expand_query_with_hyp("test", store, "http://localhost", "m", "")
    assert reason == "timeout"


def test_expand_query_with_hyp_returns_reason_endpoint_error(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda *a, **kw: (_ for _ in ()).throw(Exception("no server"))
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: (_ for _ in ()).throw(
        httpx.ConnectError("connection refused")
    ))
    _, _, _, reason = expand_query_with_hyp("test", store, "http://localhost:9999", "m", "")
    assert reason == "endpoint_error"


def test_expand_query_with_hyp_returns_none_reason_on_success(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda *a, **kw: (_ for _ in ()).throw(Exception("no server"))
    )
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _FakePostResp())
    _, _, _, reason = expand_query_with_hyp("test", store, "http://localhost", "m", "")
    assert reason is None


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
