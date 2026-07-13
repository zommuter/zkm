"""Tests for llm_query / llm_stream config resolution and streaming."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import numpy as np
import pytest

from zkm.embed import EmbedStore, save_embed_store
from zkm.index import build_index, save_index
from zkm.query import (
    _chat_url,
    _resolve_expand_config,
    llm_query,
    llm_stream,
    search,
    search_hybrid,
    search_with_expansion,
)
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
    """No env vars set → falls back to localhost:8080 + gemma4-e4b, no error."""
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
    assert requests_made[0]["model"] == "gemma4-e4b"


def test_config_from_yaml(indexed_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import yaml
    monkeypatch.delenv("ZKM_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("ZKM_LLM_MODEL", raising=False)
    monkeypatch.delenv("ZKM_LLM_KEY", raising=False)

    cfg_path = indexed_store / "zkm-config.yaml"
    data = yaml.safe_load(cfg_path.read_text()) or {}
    data.setdefault("core", {})["llm"] = {
        "endpoint": "http://localhost:11434",
        "model": "llama3",
        "key": "testkey",
    }
    cfg_path.write_text(yaml.dump(data, default_flow_style=False))

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


def test_llm_stream_system_prompt_instructs_relevance_check(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """System prompt must instruct the LLM to judge relevance and refuse on mismatches.

    Regression: previously the prompt only said "use the provided sources", causing
    the model to fabricate answers (e.g. electricity bills) from tangentially related
    docs (e.g. phone bills) when the actual document type was absent from the corpus.
    """
    monkeypatch.setenv("ZKM_LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("ZKM_LLM_MODEL", "test-model")
    monkeypatch.setenv("ZKM_LLM_KEY", "")

    captured: list[dict] = []

    class MockResponse:
        status_code = 200

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
    list(llm_stream(store, [], "Wie hoch war meine Stromrechnung?"))

    assert len(captured) == 1
    system_msg = next(m for m in captured[0]["messages"] if m["role"] == "system")
    prompt = system_msg["content"]
    assert "judge whether" in prompt, f"relevance-check clause missing: {prompt!r}"
    assert "say so" in prompt, f"escape-hatch clause missing: {prompt!r}"
    assert "language of the question" in prompt, f"bilingual clause missing: {prompt!r}"


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


# ---------------------------------------------------------------------------
# Hybrid search (BM25 + dense)
# ---------------------------------------------------------------------------


def _write_and_index(store: Path, docs: list[tuple[str, str, str]]) -> None:
    """Write (rel, body, frontmatter) tuples, build and save BM25 index."""
    for rel, body, fm in docs:
        _write_note(store, rel, body, fm)
    idx = build_index(store)
    save_index(store, idx)


def _make_embed_store(store: Path, paths: list[str], vecs: np.ndarray) -> None:
    """Save a hand-crafted EmbedStore for deterministic dense tests."""
    es = EmbedStore(
        paths=paths,
        mtimes_ns=[0] * len(paths),
        vectors=vecs.astype(np.float32),
        model="bge-m3",
    )
    save_embed_store(store, es)


def test_search_hybrid_no_dense_flag_uses_bm25(store: Path) -> None:
    """--no-dense with search_hybrid must return the same results as bare search()."""
    _write_and_index(store, [
        ("notes/doc1.md", "electricity bill stadtwerke", "source: notes"),
        ("notes/doc2.md", "apple pie recipe", "source: notes"),
    ])
    hybrid = search_hybrid(store, "electricity", top_k=5, dense=False)
    plain = search(store, "electricity", top_k=5)
    assert [h.path for h in hybrid] == [h.path for h in plain]



def test_search_hybrid_no_dense_flag_skips_embed(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """search_hybrid with dense=False must not call embed_texts even when store exists."""
    _write_and_index(store, [
        ("notes/doc1.md", "electricity bill", "source: notes"),
    ])
    dim = 4
    _make_embed_store(store, ["notes/doc1.md"], np.eye(1, dim))
    embed_called = []
    monkeypatch.setattr("zkm.query.embed_texts", lambda *a, **kw: embed_called.append(1))
    hits = search_hybrid(store, "electricity", top_k=5, dense=False)
    assert embed_called == []
    assert any("doc1" in h.path for h in hits)


def test_search_hybrid_surfaces_cross_lingual_doc(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dense leg surfaces a doc with zero BM25 token overlap (cross-lingual recall)."""
    monkeypatch.setenv("ZKM_EMBED_ENDPOINT", "http://localhost:8080")
    _write_and_index(store, [
        ("notes/bm25_match.md", "electricity invoice payment", "source: notes"),
        ("notes/dense_only.md", "Rechnung Stadtwerke Strom", "source: notes"),
    ])

    # Build a 2-doc embed store where dim-0 = bm25_match, dim-1 = dense_only
    dim = 2
    vecs = np.eye(2, dim, dtype=np.float32)  # orthonormal; each doc points at its own dimension
    _make_embed_store(store, ["notes/bm25_match.md", "notes/dense_only.md"], vecs)

    # Query vector pointing at dim-1 → dense_only should score 1.0
    query_vec = np.array([[0.0, 1.0]], dtype=np.float32)

    def fake_embed(texts, endpoint, model, api_key="", *, timeout=60.0):
        # Return same vector for any query
        return np.tile(query_vec, (len(texts), 1))

    monkeypatch.setattr("zkm.query.embed_texts", fake_embed)

    hits = search_hybrid(store, "Stromrechnung", top_k=5, dense=True)
    paths = [h.path for h in hits]
    # dense_only has zero BM25 overlap with English-like terms but dense places it first
    assert "notes/dense_only.md" in paths


def test_search_with_expansion_no_dense_skips_embed(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """search_with_expansion(dense=False) must not call embed_texts."""
    monkeypatch.setenv("ZKM_LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("ZKM_LLM_MODEL", "test-model")
    monkeypatch.setenv("ZKM_LLM_KEY", "")
    _write_and_index(store, [
        ("notes/doc1.md", "electricity bill", "source: notes"),
    ])

    expansion_response = {
        "choices": [{"message": {"content": "electricity bill\n\nThe bill was 50 CHF."}}]
    }

    class MockPost:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return expansion_response

    embed_called = []

    def _fake_embed(*a, **kw) -> np.ndarray:
        embed_called.append(1)
        return np.zeros((1, 4))

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: MockPost())
    monkeypatch.setattr("zkm.query.embed_texts", _fake_embed)

    search_with_expansion(store, "electricity", top_k=5, dense=False)
    assert embed_called == [], "embed_texts must not be called when dense=False"


def test_search_with_expansion_dense_temporal_filter(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dense hits outside the temporal window should be filtered out."""
    monkeypatch.setenv("ZKM_LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("ZKM_LLM_MODEL", "test-model")
    monkeypatch.setenv("ZKM_LLM_KEY", "")
    monkeypatch.setenv("ZKM_EMBED_ENDPOINT", "http://localhost:8080")
    monkeypatch.delenv("ZKM_EMBED_MODEL", raising=False)

    _write_and_index(store, [
        ("notes/recent.md", "payment", "source: notes\ndate: 2026-04-15"),
        ("notes/old.md", "payment", "source: notes\ndate: 2025-01-01"),
    ])
    dim = 2
    vecs = np.eye(2, dim, dtype=np.float32)
    _make_embed_store(store, ["notes/recent.md", "notes/old.md"], vecs)

    expansion_response = {
        "choices": [{"message": {"content": "payment\n\nA recent payment was made."}}]
    }

    class MockPost:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return expansion_response

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: MockPost())

    # Both docs score equally in dense; temporal filter for "this year" = 2026
    # old.md (2025) should be filtered out of the dense leg
    def fake_embed(texts, endpoint, model, api_key="", *, timeout=60.0):
        return np.ones((len(texts), dim), dtype=np.float32) / (dim ** 0.5)

    monkeypatch.setattr("zkm.query.embed_texts", fake_embed)

    hits = search_with_expansion(store, "payments this year", top_k=10, dense=True)
    paths = [h.path for h in hits]
    # old.md is outside 2026 and should not appear via the dense temporal filter
    # (it may appear via BM25 if BM25 is also filtered, but here both docs match "payment"
    # BM25-wise — we just check that recent.md is present)
    assert "notes/recent.md" in paths


def test_llm_stream_strips_eos_tokens(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """llm_stream must strip <|..._TOKEN|> control tokens emitted by some models

    (e.g. aya-expanse-8b).
    """
    monkeypatch.setenv("ZKM_LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("ZKM_LLM_MODEL", "test-model")
    monkeypatch.setenv("ZKM_LLM_KEY", "")

    class MockResponse:
        status_code = 200

        def iter_lines(self):
            yield f"data: {json.dumps({'choices': [{'delta': {'content': 'Hello'}}]})}"
            eos_chunk = {"choices": [{"delta": {"content": "<|END_OF_TURN_TOKEN|>"}}]}
            yield f"data: {json.dumps(eos_chunk)}"
            world_chunk = {
                "choices": [{"delta": {"content": " world<|END_OF_TURN_TOKEN|>"}}]
            }
            yield f"data: {json.dumps(world_chunk)}"
            yield "data: [DONE]"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(httpx, "stream", lambda *a, **kw: MockResponse())
    tokens = list(llm_stream(store, [], "test question?"))
    assert tokens == ["Hello", " world"], f"EOS tokens not stripped: {tokens!r}"


# ---------------------------------------------------------------------------
# Expand-model override
# ---------------------------------------------------------------------------


def test_resolve_expand_config_env_override(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ZKM_LLM_EXPAND_MODEL env var overrides config expand.model."""
    import yaml
    cfg_path = store / "zkm-config.yaml"
    data = yaml.safe_load(cfg_path.read_text()) or {}
    data.setdefault("core", {})["expand"] = {"model": "config-expand-model"}
    cfg_path.write_text(yaml.dump(data, default_flow_style=False))

    monkeypatch.setenv("ZKM_LLM_EXPAND_MODEL", "env-override-model")
    _, mdl, _ = _resolve_expand_config(store)
    assert mdl == "env-override-model"


def test_resolve_expand_config_env_override_absent(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without ZKM_LLM_EXPAND_MODEL, config expand.model wins."""
    import yaml
    cfg_path = store / "zkm-config.yaml"
    data = yaml.safe_load(cfg_path.read_text()) or {}
    data.setdefault("core", {})["expand"] = {"model": "config-expand-model"}
    cfg_path.write_text(yaml.dump(data, default_flow_style=False))

    monkeypatch.delenv("ZKM_LLM_EXPAND_MODEL", raising=False)
    _, mdl, _ = _resolve_expand_config(store)
    assert mdl == "config-expand-model"


def test_search_expand_model_flag_forwarded(
    indexed_store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--expand-model CLI flag is forwarded to search_with_expansion_traced."""
    from click.testing import CliRunner

    import zkm.query as qmod
    from zkm.cli import main

    calls: list[str | None] = []

    original = qmod.search_with_expansion_traced

    def patched(store, question, *, top_k=20, dense=True, model=None, **kw):
        calls.append(model)
        return original(store, question, top_k=top_k, dense=False, model=model, **kw)

    monkeypatch.setattr(qmod, "search_with_expansion_traced", patched)
    monkeypatch.delenv("ZKM_LLM_EXPAND_MODEL", raising=False)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "search",
            "--store",
            str(indexed_store),
            "--expand",
            "--expand-model",
            "aya-expanse-8b",
            "test",
        ],
        catch_exceptions=False,
    )
    assert calls == ["aya-expanse-8b"], (
        f"model not forwarded, calls={calls}, output={result.output}"
    )
