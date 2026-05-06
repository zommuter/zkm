"""Tests for llm_query / llm_stream config resolution and streaming."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from zkm.index import build_index, save_index
from zkm.query import _chat_url, llm_query, llm_stream, search, search_with_expansion
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
    _write_note(store, "notes/doc1.md", "electricity bill from Stadtwerke",
                "source: notes\ndate: 2026-01-01")
    _write_note(store, "notes/doc2.md", "apple pie recipe", "source: notes\ndate: 2026-01-02")
    idx = build_index(store)
    save_index(store, idx)
    return store


# ---------------------------------------------------------------------------
# _chat_url helper
# ---------------------------------------------------------------------------


def test_chat_url_bare_host() -> None:
    assert _chat_url("http://localhost:11434") == "http://localhost:11434/v1/chat/completions"


def test_chat_url_with_v1() -> None:
    assert _chat_url("http://localhost:11434/v1") == "http://localhost:11434/v1/chat/completions"


def test_chat_url_already_full() -> None:
    url = "http://localhost:11434/v1/chat/completions"
    assert _chat_url(url) == url


def test_chat_url_trailing_slash() -> None:
    assert _chat_url("http://localhost:11434/") == "http://localhost:11434/v1/chat/completions"


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------


def test_defaults_used_when_no_config(indexed_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No env vars set → falls back to localhost:8080 + qwen3.5-0.8b, no error."""
    monkeypatch.delenv("ZKM_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("ZKM_LLM_MODEL", raising=False)
    monkeypatch.delenv("ZKM_LLM_KEY", raising=False)

    requests_made: list[dict] = []

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def iter_lines(self):
            import json
            yield f"data: {json.dumps({'choices': [{'delta': {'content': 'ok'}}]})}"
            yield "data: [DONE]"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def mock_stream(method, url, *, headers, json, timeout):
        requests_made.append({"url": url, "model": json["model"]})
        return MockResponse()

    monkeypatch.setattr(httpx, "stream", mock_stream)
    list(llm_query(indexed_store, "electricity", expand=False))

    assert requests_made[0]["url"] == "http://localhost:8080/v1/chat/completions"
    assert requests_made[0]["model"] == "qwen3.5-0.8b"


def test_config_from_dot_env(indexed_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZKM_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("ZKM_LLM_MODEL", raising=False)
    monkeypatch.delenv("ZKM_LLM_KEY", raising=False)

    (indexed_store / ".env").write_text(
        "ZKM_LLM_ENDPOINT=http://localhost:11434\n"
        "ZKM_LLM_MODEL=llama3\n"
        "ZKM_LLM_KEY=testkey\n"
    )

    chunks = ["Hello ", "world"]
    done_line = "data: [DONE]"

    def _sse_lines() -> list[str]:
        return [
            f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}"
            for c in chunks
        ] + [done_line]

    class MockResponse:
        def __init__(self) -> None:
            self.status_code = 200

        def raise_for_status(self) -> None:
            pass

        def iter_lines(self):
            yield from _sse_lines()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(httpx, "stream", lambda *a, **kw: MockResponse())

    result = list(llm_query(indexed_store, "what is the bill?", expand=False))
    assert result == chunks


# ---------------------------------------------------------------------------
# Streaming + prompt
# ---------------------------------------------------------------------------


def test_llm_query_streams_content(indexed_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZKM_LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("ZKM_LLM_MODEL", "llama3")
    monkeypatch.setenv("ZKM_LLM_KEY", "testkey")

    chunks = ["The bill ", "is for electricity."]

    def _sse_lines() -> list[str]:
        return [
            f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}"
            for c in chunks
        ] + ["data: [DONE]"]

    class MockResponse:
        def __init__(self) -> None:
            self.status_code = 200

        def raise_for_status(self) -> None:
            pass

        def iter_lines(self):
            yield from _sse_lines()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    requests_made: list[dict] = []

    def mock_stream(method, url, *, headers, json, timeout):
        requests_made.append({"method": method, "url": url, "json": json})
        return MockResponse()

    monkeypatch.setattr(httpx, "stream", mock_stream)

    result = list(llm_query(indexed_store, "electricity bill", expand=False))
    assert result == chunks

    # Verify prompt contains doc relative paths as citation handles
    assert len(requests_made) == 1
    messages = requests_made[0]["json"]["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    assert "notes/doc1.md" in user_msg["content"]


def test_llm_query_empty_store_no_crash(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """llm_query with no indexed docs should still call the LLM (no context)."""
    idx = build_index(store)
    save_index(store, idx)

    monkeypatch.setenv("ZKM_LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("ZKM_LLM_MODEL", "llama3")
    monkeypatch.setenv("ZKM_LLM_KEY", "testkey")

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def iter_lines(self):
            yield f"data: {json.dumps({'choices': [{'delta': {'content': 'no context'}}]})}"
            yield "data: [DONE]"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(httpx, "stream", lambda *a, **kw: MockResponse())
    result = list(llm_query(store, "any question", expand=False))
    assert result == ["no context"]


# ---------------------------------------------------------------------------
# Bilingual expansion end-to-end
# ---------------------------------------------------------------------------


def test_search_with_expansion_finds_german_doc(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """search_with_expansion surfaces a German doc for an English question.

    With raw BM25 there would be zero token overlap (English question vs German doc).
    The mocked expansion call returns German keyword variants that match the doc.
    """
    _write_note(
        store,
        "notes/stromrechnung.md",
        "Stromrechnung von Stadtwerke: 142 CHF",
        "source: notes\ndate: 2026-03-01",
    )
    _write_note(
        store,
        "notes/groceries.md",
        "Migros Einkauf: 87 CHF",
        "source: notes\ndate: 2026-03-15",
    )
    idx = build_index(store)
    save_index(store, idx)

    # Mock the expansion LLM call (httpx.post) to return known keyword variants.
    expansion_response = {
        "choices": [{
            "message": {
                "content": (
                    "Stromrechnung\nStadtwerke\nelectricity bill\nutility invoice\n\n"
                    "The electricity bill from Stadtwerke was 142 CHF."
                )
            }
        }]
    }

    class MockPostResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return expansion_response

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: MockPostResponse())
    monkeypatch.setenv("ZKM_LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("ZKM_LLM_MODEL", "test-model")
    monkeypatch.setenv("ZKM_LLM_KEY", "")

    hits = search_with_expansion(store, "what was my last electricity bill?", top_k=5)
    paths = [h.path for h in hits]
    assert "notes/stromrechnung.md" in paths
    assert paths[0] == "notes/stromrechnung.md"  # electricity doc ranked first


def test_llm_stream_system_prompt_contains_current_date(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """System prompt must include today's ISO date so the model knows temporal context.

    Regression test: without this, a model answering 'last month' has no idea what
    year or month 'now' is and hallucinates dates from its training data (e.g. 2024).
    """
    idx = build_index(store)
    save_index(store, idx)
    monkeypatch.setenv("ZKM_LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("ZKM_LLM_MODEL", "test-model")
    monkeypatch.setenv("ZKM_LLM_KEY", "")

    captured: list[dict] = []

    class MockResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def iter_lines(self):
            yield f"data: {json.dumps({'choices': [{'delta': {'content': 'ok'}}]})}"
            yield "data: [DONE]"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    def mock_stream(method, url, *, headers, json, timeout):
        captured.append(json)
        return MockResponse()

    monkeypatch.setattr(httpx, "stream", mock_stream)
    list(llm_stream(store, [], "what happened last month?"))

    assert len(captured) == 1
    messages = captured[0]["messages"]
    system_msg = next(m for m in messages if m["role"] == "system")
    today_iso = date.today().isoformat()
    assert today_iso in system_msg["content"], (
        f"System prompt missing today's date ({today_iso}): {system_msg['content']!r}"
    )


def test_no_expand_misses_german_doc(store: Path) -> None:
    """With --no-expand, raw BM25 on an English question returns nothing for a German-only doc."""
    _write_note(
        store,
        "notes/stromrechnung.md",
        "Stromrechnung von Stadtwerke: 142 CHF",
        "source: notes\ndate: 2026-03-01",
    )
    idx = build_index(store)
    save_index(store, idx)

    # English question vs German doc: with only raw BM25, zero token overlap → no results
    hits = search(store, "what was my last electricity bill?")
    paths = [h.path for h in hits]
    assert "notes/stromrechnung.md" not in paths
