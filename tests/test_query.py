"""Tests for llm_query config resolution and streaming."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from zkm.index import build_index, save_index
from zkm.query import _chat_url, llm_query
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


def test_missing_endpoint_raises(indexed_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZKM_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("ZKM_LLM_MODEL", raising=False)
    monkeypatch.delenv("ZKM_LLM_KEY", raising=False)
    with pytest.raises(ValueError, match="ZKM_LLM_ENDPOINT"):
        list(llm_query(indexed_store, "anything"))


def test_missing_model_raises(indexed_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZKM_LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.delenv("ZKM_LLM_MODEL", raising=False)
    monkeypatch.delenv("ZKM_LLM_KEY", raising=False)
    with pytest.raises(ValueError, match="ZKM_LLM_MODEL"):
        list(llm_query(indexed_store, "anything"))


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

    result = list(llm_query(indexed_store, "what is the bill?"))
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

    result = list(llm_query(indexed_store, "electricity bill"))
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
    result = list(llm_query(store, "any question"))
    assert result == ["no context"]
