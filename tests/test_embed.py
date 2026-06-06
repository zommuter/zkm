"""Tests for the embedding client, EmbedStore, and build_embed_store."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import numpy as np
import pytest

from zkm.embed import (
    EmbedStore,
    EmbedUnavailable,
    _chunk_texts,
    _embeddings_url,
    build_embed_store,
    embed_texts,
    load_embed_store,
    resolve_embed_config,
    save_embed_store,
)
from zkm.index import Doc
from zkm.store import init_store

# ---------------------------------------------------------------------------
# URL helper
# ---------------------------------------------------------------------------


def test_embeddings_url_bare_host() -> None:
    assert _embeddings_url("http://localhost:8080") == "http://localhost:8080/v1/embeddings"


def test_embeddings_url_with_v1() -> None:
    assert _embeddings_url("http://localhost:8080/v1") == "http://localhost:8080/v1/embeddings"


def test_embeddings_url_already_full() -> None:
    url = "http://localhost:8080/v1/embeddings"
    assert _embeddings_url(url) == url


def test_embeddings_url_trailing_slash() -> None:
    assert _embeddings_url("http://localhost:8080/") == "http://localhost:8080/v1/embeddings"


# ---------------------------------------------------------------------------
# resolve_embed_config
# ---------------------------------------------------------------------------


def test_resolve_embed_config_yaml(tmp_path: Path) -> None:
    import yaml
    store = tmp_path / "store"
    init_store(store, backend="none")
    cfg_path = store / "zkm-config.yaml"
    data = yaml.safe_load(cfg_path.read_text()) or {}
    data.setdefault("core", {})["embed"] = {"endpoint": "http://myhost:9090", "model": "my-model"}
    cfg_path.write_text(yaml.dump(data, default_flow_style=False))
    ep, mdl, key, _ = resolve_embed_config(store)
    assert ep == "http://myhost:9090"
    assert mdl == "my-model"
    assert key == ""


def test_resolve_embed_config_override(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    ep, mdl, _key, _ = resolve_embed_config(store, endpoint="http://override:1234", model="m")
    assert ep == "http://override:1234"
    assert mdl == "m"


def test_resolve_embed_config_unset_gives_default_endpoint(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    ep, mdl, _, _ = resolve_embed_config(store)
    assert ep == "http://localhost:8080"
    assert mdl == "bge-m3"


# ---------------------------------------------------------------------------
# embed_texts
# ---------------------------------------------------------------------------


def _fake_embed_response(n: int, dim: int = 4) -> dict:
    return {
        "data": [
            {"index": i, "embedding": [float(i + 1)] * dim, "object": "embedding"}
            for i in range(n)
        ]
    }


def test_embed_texts_returns_normalized_float32(monkeypatch: pytest.MonkeyPatch) -> None:
    dim = 4
    mock_resp = MagicMock()
    mock_resp.json.return_value = _fake_embed_response(2, dim)
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        result = embed_texts(["hello", "world"], "http://localhost:8080", "bge-m3")

    assert mock_post.called
    assert result.dtype == np.float32
    assert result.shape == (2, dim)
    # Rows should be L2-normalized
    norms = np.linalg.norm(result, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-6)


def test_embed_texts_raises_when_no_endpoint() -> None:
    with pytest.raises(EmbedUnavailable, match="ZKM_EMBED_ENDPOINT not set"):
        embed_texts(["x"], "", "bge-m3")


def test_embed_texts_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("HTTP 500")

    with patch("httpx.post", return_value=mock_resp):
        with pytest.raises(EmbedUnavailable):
            embed_texts(["x"], "http://localhost:8080", "bge-m3")


def test_embed_texts_batches_large_input(monkeypatch: pytest.MonkeyPatch) -> None:
    dim = 2
    call_count = 0

    def fake_post(url, headers, json, timeout):  # noqa: A002
        nonlocal call_count
        n = len(json["input"])
        call_count += 1
        resp = MagicMock()
        resp.json.return_value = _fake_embed_response(n, dim)
        resp.raise_for_status = MagicMock()
        return resp

    with patch("httpx.post", side_effect=fake_post):
        result = embed_texts(["t"] * 70, "http://localhost:8080", "bge-m3")

    assert result.shape == (70, dim)
    assert call_count == 3  # 32 + 32 + 6


# ---------------------------------------------------------------------------
# EmbedStore.topk
# ---------------------------------------------------------------------------


def _make_store(n: int = 5, dim: int = 4) -> EmbedStore:
    vecs = np.eye(n, dim, dtype=np.float32)  # orthonormal; i-th row points at dimension i
    return EmbedStore(
        paths=[f"doc{i}.md" for i in range(n)],
        mtimes_ns=[i * 1000 for i in range(n)],
        vectors=vecs,
        model="bge-m3",
    )


def test_topk_returns_correct_order() -> None:
    es = _make_store(5, 4)
    # Query vector pointing at dimension 2 (doc2 should score highest)
    q = np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32)
    results = es.topk(q, 3)
    paths = [es.paths[i] for i, _ in results]
    assert paths[0] == "doc2.md"
    assert len(results) == 3


def test_topk_clamps_to_store_size() -> None:
    es = _make_store(3, 4)
    q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    results = es.topk(q, 100)
    assert len(results) == 3


def test_topk_empty_store() -> None:
    es = EmbedStore(paths=[], mtimes_ns=[], vectors=np.zeros((0, 4), dtype=np.float32))
    q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    assert es.topk(q, 5) == []


# ---------------------------------------------------------------------------
# save_embed_store / load_embed_store
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    es = _make_store(4, 8)
    save_embed_store(store, es)
    loaded = load_embed_store(store)
    assert loaded is not None
    assert loaded.paths == es.paths
    assert loaded.mtimes_ns == es.mtimes_ns
    np.testing.assert_allclose(loaded.vectors, es.vectors, atol=1e-6)
    assert loaded.model == "bge-m3"


def test_load_returns_none_when_missing(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    assert load_embed_store(store) is None


def test_meta_file_written(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    es = _make_store(2, 4)
    save_embed_store(store, es)
    meta = json.loads((store / ".zkm-index/embeddings-meta.json").read_text())
    assert meta["model"] == "bge-m3"
    assert meta["n_docs"] == 2
    assert meta["dim"] == 4


def test_save_embed_store_atomic_under_interrupt(tmp_path: Path, monkeypatch) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    es = _make_store(3, 8)
    save_embed_store(store, es)

    npz_path = store / ".zkm-index/embeddings.npz"
    meta_path = store / ".zkm-index/embeddings-meta.json"
    good_npz = npz_path.read_bytes()
    good_meta = meta_path.read_bytes()

    def boom(f, **_kwargs):
        f.write(b"corrupt")
        raise RuntimeError("simulated mid-write crash")

    monkeypatch.setattr(np, "savez_compressed", boom)

    es2 = _make_store(5, 8)
    with pytest.raises(RuntimeError):
        save_embed_store(store, es2)

    assert npz_path.read_bytes() == good_npz, "NPZ was overwritten despite crash"
    assert meta_path.read_bytes() == good_meta, "meta was overwritten despite crash"
    assert load_embed_store(store) is not None, "store corrupted — load returns None"


# ---------------------------------------------------------------------------
# build_embed_store
# ---------------------------------------------------------------------------


def _make_doc(store: Path, rel: str, body: str = "hello world", mtime_ns: int = 1000) -> Doc:
    path = store / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return Doc(rel_path=rel, mtime_ns=mtime_ns, metadata={}, tokens=body.split())


def test_build_embed_store_embeds_all_docs(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    docs = [_make_doc(store, f"notes/d{i}.md", f"text {i}", mtime_ns=i * 100) for i in range(3)]

    def fake_post(url, headers, json, timeout):  # noqa: A002
        n = len(json["input"])
        resp = MagicMock()
        resp.json.return_value = _fake_embed_response(n, 4)
        resp.raise_for_status = MagicMock()
        return resp

    with patch("httpx.post", side_effect=fake_post):
        es = build_embed_store(
            store, docs, prev_es=None, endpoint="http://localhost:8080",
            model="bge-m3", api_key="",
        )

    assert len(es.paths) == 3
    assert es.vectors.shape == (3, 4)


def test_build_embed_store_splits_oversized_chunk(tmp_path: Path) -> None:
    """A chunk the server rejects as 'too large to process' is split + mean-pooled
    instead of aborting the whole build (deterministic 500, not retried with backoff)."""
    store = tmp_path / "store"
    init_store(store, backend="none")
    # One doc whose single chunk exceeds the server's per-input limit (simulated at 8 chars).
    docs = [_make_doc(store, "notes/big.md", "X" * 20, mtime_ns=100)]
    threshold = 8
    too_large_body = (
        '{"error":{"code":500,"message":"input (999 tokens) is too large to process.'
        ' increase the physical batch size (current batch size: 2048)","type":"server_error"}}'
    )

    def fake_post(url, headers, json, timeout):  # noqa: A002
        texts = json["input"]
        resp = MagicMock()
        if any(len(t) > threshold for t in texts):
            req = httpx.Request("POST", url)
            http_resp = httpx.Response(500, text=too_large_body, request=req)
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=req, response=http_resp
            )
            return resp
        resp.json.return_value = _fake_embed_response(len(texts), 4)
        resp.raise_for_status = MagicMock()
        return resp

    with patch("httpx.post", side_effect=fake_post):
        es = build_embed_store(
            store, docs, prev_es=None, endpoint="http://localhost:8080",
            model="bge-m3", api_key="",
        )

    # The oversized chunk still produces exactly one normalized row — no abort, no data loss.
    assert es.vectors.shape == (1, 4)
    np.testing.assert_allclose(np.linalg.norm(es.vectors, axis=1), 1.0, atol=1e-6)


def test_build_embed_store_reuses_cached_vectors(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    docs = [_make_doc(store, f"notes/d{i}.md", mtime_ns=i * 100) for i in range(3)]

    call_count = 0

    def fake_post(url, headers, json, timeout):  # noqa: A002
        nonlocal call_count
        n = len(json["input"])
        call_count += 1
        resp = MagicMock()
        resp.json.return_value = _fake_embed_response(n, 4)
        resp.raise_for_status = MagicMock()
        return resp

    # First build
    with patch("httpx.post", side_effect=fake_post):
        es1 = build_embed_store(
            store, docs, prev_es=None, endpoint="http://localhost:8080",
            model="bge-m3", api_key="",
        )

    call_count = 0  # reset

    # Second build: same docs, same mtimes → no new HTTP calls
    with patch("httpx.post", side_effect=fake_post):
        es2 = build_embed_store(
            store, docs, prev_es=es1, endpoint="http://localhost:8080",
            model="bge-m3", api_key="",
        )

    assert call_count == 0
    np.testing.assert_allclose(es1.vectors, es2.vectors)


def test_build_embed_store_reembeds_on_model_change(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    docs = [_make_doc(store, "notes/d0.md", mtime_ns=100)]

    call_count = 0

    def fake_post(url, headers, json, timeout):  # noqa: A002
        nonlocal call_count
        n = len(json["input"])
        call_count += 1
        resp = MagicMock()
        resp.json.return_value = _fake_embed_response(n, 4)
        resp.raise_for_status = MagicMock()
        return resp

    with patch("httpx.post", side_effect=fake_post):
        es1 = build_embed_store(
            store, docs, prev_es=None, endpoint="http://localhost:8080",
            model="bge-m3", api_key="",
        )

    call_count = 0

    # Different model → must re-embed
    with patch("httpx.post", side_effect=fake_post):
        build_embed_store(
            store, docs, prev_es=es1, endpoint="http://localhost:8080",
            model="e5-large", api_key="",
        )

    assert call_count > 0


# ---------------------------------------------------------------------------
# _chunk_texts
# ---------------------------------------------------------------------------


def test_chunk_texts_short_doc_yields_single_chunk(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    doc = _make_doc(store, "notes/short.md", body="hello world", mtime_ns=1000)
    chunks = _chunk_texts(store, doc)
    assert len(chunks) == 1
    assert "hello world" in chunks[0]


def test_chunk_texts_long_doc_yields_multiple_with_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZKM_EMBED_CHUNK_CHARS", "2000")
    monkeypatch.setenv("ZKM_EMBED_CHUNK_OVERLAP", "200")
    store = tmp_path / "store"
    init_store(store, backend="none")
    body = "A" * 6000
    doc = _make_doc(store, "notes/long.md", body=body, mtime_ns=1000)
    chunks = _chunk_texts(store, doc)
    # stride = 2000 - 200 = 1800; starts at 0, 1800, 3600, 5400 → 4 chunks
    assert len(chunks) == 4
    # Consecutive chunks share a 200-char suffix/prefix from the raw body
    for i in range(len(chunks) - 1):
        # The last 200 chars of chunk i's body window == first 200 chars of chunk i+1's body window
        # Strip the header (no title/tags in this fixture) — chunks[i] == window text only
        assert chunks[i][-200:] == chunks[i + 1][: len(chunks[i + 1]) - len(chunks[i + 1].lstrip("A"))][:200]


def test_chunk_texts_long_doc_overlap_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify overlap by checking that the overlapping characters match between chunks."""
    monkeypatch.setenv("ZKM_EMBED_CHUNK_CHARS", "100")
    monkeypatch.setenv("ZKM_EMBED_CHUNK_OVERLAP", "20")
    store = tmp_path / "store"
    init_store(store, backend="none")
    body = "X" * 300
    doc = _make_doc(store, "notes/ol.md", body=body, mtime_ns=1000)
    chunks = _chunk_texts(store, doc)
    # stride = 80; starts at 0, 80, 160, 240 → 4 chunks
    assert len(chunks) == 4
    # Each chunk is entirely X's (no title/tags) — the last 20 of chunk[i] == first 20 of chunk[i+1]
    for i in range(len(chunks) - 1):
        assert chunks[i][-20:] == chunks[i + 1][:20]


def test_chunk_texts_respects_env_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZKM_EMBED_CHUNK_CHARS", "500")
    monkeypatch.setenv("ZKM_EMBED_CHUNK_OVERLAP", "50")
    store = tmp_path / "store"
    init_store(store, backend="none")
    body = "B" * 1200  # stride=450; starts at 0, 450, 900 → 3 chunks
    doc = _make_doc(store, "notes/env.md", body=body, mtime_ns=1000)
    chunks = _chunk_texts(store, doc)
    assert len(chunks) == 3


def test_chunk_texts_legacy_max_chars_deprecation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("ZKM_EMBED_MAX_CHARS", "300")
    monkeypatch.delenv("ZKM_EMBED_CHUNK_CHARS", raising=False)
    store = tmp_path / "store"
    init_store(store, backend="none")
    body = "C" * 800  # stride = 300-200=100? No — legacy sets chunk_chars=300, overlap still default 200
    # With chunk_chars=300, overlap=200, stride=100; body=800 → starts 0,100,200,...,700 → 8 chunks
    # But we just care about the deprecation warning appearing
    doc = _make_doc(store, "notes/legacy.md", body=body, mtime_ns=1000)
    _chunk_texts(store, doc)
    captured = capsys.readouterr()
    assert "ZKM_EMBED_MAX_CHARS is deprecated" in captured.err


def test_chunk_texts_includes_entity_value_and_canonical(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    path = store / "mail/msg.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nentities:\n"
        "  - {scope: body, type: email, value: 'alice@example.com', canonical: 'alice@example.com'}\n"
        "---\nhello world\n"
    )
    doc = Doc(rel_path="mail/msg.md", mtime_ns=1000, metadata={}, tokens=[])
    chunks = _chunk_texts(store, doc)
    assert any("alice@example.com" in c for c in chunks)


def test_chunk_texts_skips_invalid_entities(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    path = store / "mail/msg.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nentities:\n"
        "  - {scope: body, type: person, value: 'garbage', valid: false}\n"
        "---\nhello\n"
    )
    doc = Doc(rel_path="mail/msg.md", mtime_ns=1000, metadata={}, tokens=[])
    chunks = _chunk_texts(store, doc)
    assert all("garbage" not in c for c in chunks)


def test_chunk_texts_includes_participant_address_and_name(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    path = store / "mail/msg.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nparticipants:\n"
        "  - {address: 'bob@example.org', name: 'Bob Builder', role: 'from'}\n"
        "---\nsome email body\n"
    )
    doc = Doc(rel_path="mail/msg.md", mtime_ns=1000, metadata={}, tokens=[])
    chunks = _chunk_texts(store, doc)
    assert any("bob@example.org" in c for c in chunks)
    assert any("Bob Builder" in c for c in chunks)


def test_chunk_texts_prefix_capped_on_large_entities(tmp_path: Path) -> None:
    """Synthetic 30k-char entities prefix must be capped to _MAX_PREFIX_CHARS."""
    from zkm.embed import _MAX_PREFIX_CHARS

    store = tmp_path / "store"
    init_store(store, backend="none")
    path = store / "mail/msg.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Build 150 entity entries of 200 chars each → ~30k-char entity_str
    entities_yaml = "".join(
        f"  - {{scope: body, type: org, value: 'entity_{i:04d}_{'x' * 190}'}}\n"
        for i in range(150)
    )
    path.write_text(f"---\nentities:\n{entities_yaml}---\nshort body\n")
    doc = Doc(rel_path="mail/msg.md", mtime_ns=1000, metadata={}, tokens=[])
    chunks = _chunk_texts(store, doc)
    for chunk in chunks:
        assert len(chunk) <= _MAX_PREFIX_CHARS + 2000 + 10  # prefix cap + body window + newline


# ---------------------------------------------------------------------------
# EmbedStore schema versioning
# ---------------------------------------------------------------------------


def test_embed_store_round_trip_with_chunks(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    es = EmbedStore(
        paths=["a.md", "a.md", "b.md"],
        mtimes_ns=[1000, 1000, 2000],
        vectors=np.eye(3, 4, dtype=np.float32),
        model="bge-m3",
        chunk_indices=[0, 1, 0],
    )
    save_embed_store(store, es)
    loaded = load_embed_store(store)
    assert loaded is not None
    assert loaded.paths == es.paths
    assert loaded.chunk_indices == [0, 1, 0]
    assert loaded.mtimes_ns == es.mtimes_ns
    np.testing.assert_allclose(loaded.vectors, es.vectors, atol=1e-6)


def test_load_embed_store_rejects_old_schema_version(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    es = _make_store(2, 4)
    save_embed_store(store, es)
    # Overwrite meta with old schema version
    meta_path = store / ".zkm-index/embeddings-meta.json"
    meta = json.loads(meta_path.read_text())
    meta["schema_version"] = 1
    meta_path.write_text(json.dumps(meta))
    assert load_embed_store(store) is None


def test_load_embed_store_rejects_missing_schema_version(tmp_path: Path) -> None:
    store = tmp_path / "store"
    init_store(store, backend="none")
    es = _make_store(2, 4)
    save_embed_store(store, es)
    meta_path = store / ".zkm-index/embeddings-meta.json"
    meta = json.loads(meta_path.read_text())
    del meta["schema_version"]
    meta_path.write_text(json.dumps(meta))
    assert load_embed_store(store) is None


# ---------------------------------------------------------------------------
# build_embed_store — chunk cache reuse and invalidation
# ---------------------------------------------------------------------------


def test_build_embed_store_reuses_chunks_on_unchanged_mtime(tmp_path: Path) -> None:
    """All chunks for an unchanged doc are reused without a POST call."""
    store = tmp_path / "store"
    init_store(store, backend="none")
    body = "W" * 5000  # produces 3 chunks with defaults
    doc = _make_doc(store, "notes/long.md", body=body, mtime_ns=999)

    call_count = 0

    def fake_post(url, headers, json, timeout):  # noqa: A002
        nonlocal call_count
        n = len(json["input"])
        call_count += 1
        resp = MagicMock()
        resp.json.return_value = _fake_embed_response(n, 4)
        resp.raise_for_status = MagicMock()
        return resp

    with patch("httpx.post", side_effect=fake_post):
        es1 = build_embed_store(
            store, [doc], prev_es=None, endpoint="http://localhost:8080",
            model="bge-m3", api_key="",
        )

    # 3 chunks produced
    assert es1.paths.count("notes/long.md") == 3

    call_count = 0
    with patch("httpx.post", side_effect=fake_post):
        es2 = build_embed_store(
            store, [doc], prev_es=es1, endpoint="http://localhost:8080",
            model="bge-m3", api_key="",
        )

    assert call_count == 0
    assert es2.paths.count("notes/long.md") == 3
    np.testing.assert_allclose(es1.vectors, es2.vectors)


def test_build_embed_store_rechunks_on_mtime_change(tmp_path: Path) -> None:
    """Changing mtime causes all chunks for the doc to be re-embedded."""
    store = tmp_path / "store"
    init_store(store, backend="none")
    doc = _make_doc(store, "notes/doc.md", body="hello world", mtime_ns=100)

    call_count = 0

    def fake_post(url, headers, json, timeout):  # noqa: A002
        nonlocal call_count
        n = len(json["input"])
        call_count += 1
        resp = MagicMock()
        resp.json.return_value = _fake_embed_response(n, 4)
        resp.raise_for_status = MagicMock()
        return resp

    with patch("httpx.post", side_effect=fake_post):
        es1 = build_embed_store(
            store, [doc], prev_es=None, endpoint="http://localhost:8080",
            model="bge-m3", api_key="",
        )

    call_count = 0
    doc_changed = Doc(
        rel_path="notes/doc.md", mtime_ns=999, metadata={}, tokens=["hello", "world"]
    )
    with patch("httpx.post", side_effect=fake_post):
        build_embed_store(
            store, [doc_changed], prev_es=es1, endpoint="http://localhost:8080",
            model="bge-m3", api_key="",
        )

    assert call_count > 0


def test_build_embed_store_skips_doc_on_persistent_failure(tmp_path: Path) -> None:
    """A doc whose batches always fail is skipped; the run does not abort."""
    store = tmp_path / "store"
    init_store(store, backend="none")
    doc_ok = _make_doc(store, "notes/ok.md", body="hello world okay", mtime_ns=1)
    doc_bad = _make_doc(store, "notes/bad.md", body="FAILME", mtime_ns=2)

    def fake_post(url, headers, json, timeout):  # noqa: A002
        inputs: list[str] = json["input"]
        if any("FAILME" in t for t in inputs):
            raise Exception("simulated transient failure")
        resp = MagicMock()
        resp.json.return_value = _fake_embed_response(len(inputs), 4)
        resp.raise_for_status = MagicMock()
        return resp

    # batch size = 1 so each doc is isolated; single-attempt retry so failure skips
    with patch("zkm.embed._EMBED_RETRY_SLEEPS", (0,)), \
         patch("zkm.embed._EMBED_BATCH", 1), \
         patch("httpx.post", side_effect=fake_post):
        es = build_embed_store(
            store, [doc_ok, doc_bad], prev_es=None, endpoint="http://localhost:8080",
            model="bge-m3", api_key="",
        )

    assert "notes/ok.md" in es.paths


def test_build_embed_store_stall_timeout_raises_on_persistent_failure(tmp_path: Path) -> None:
    """When every batch fails and stall_timeout fires, EmbedUnavailable is raised."""
    store = tmp_path / "store"
    init_store(store, backend="none")
    doc = _make_doc(store, "notes/a.md", body="text to embed", mtime_ns=1)

    def always_fail(url, headers, json, timeout):  # noqa: A002
        raise Exception("simulated transient server error")

    # Patch time.monotonic to simulate stall detection after the first failed batch:
    # - call 1 (last_success init): 0.0
    # - call 2 (top-of-loop check): 0.001 (< stall_timeout, don't abort yet)
    # - call 3 (after-failure check): 9999.0 (> stall_timeout, abort)
    mono_seq = [0.0, 0.001, 9999.0]

    with patch("zkm.embed._EMBED_RETRY_SLEEPS", (0,)), \
         patch("zkm.embed._EMBED_BATCH", 1), \
         patch("httpx.post", side_effect=always_fail), \
         patch("zkm.embed.time.monotonic", side_effect=mono_seq):
        with pytest.raises(EmbedUnavailable, match="stalled"):
            build_embed_store(
                store, [doc], prev_es=None, endpoint="http://localhost:8080",
                model="bge-m3", api_key="", stall_timeout=1800.0,
            )


def test_build_embed_store_stall_timeout_not_tripped_on_success(tmp_path: Path) -> None:
    """A run where every batch succeeds never trips the stall timeout, even if tiny."""
    store = tmp_path / "store"
    init_store(store, backend="none")
    docs = [_make_doc(store, f"notes/{i}.md", body=f"text {i}", mtime_ns=i) for i in range(3)]

    def always_succeed(url, headers, json, timeout):  # noqa: A002
        resp = MagicMock()
        resp.json.return_value = _fake_embed_response(len(json["input"]), 4)
        resp.raise_for_status = MagicMock()
        return resp

    with patch("zkm.embed._EMBED_BATCH", 1), \
         patch("httpx.post", side_effect=always_succeed):
        es = build_embed_store(
            store, docs, prev_es=None, endpoint="http://localhost:8080",
            model="bge-m3", api_key="", stall_timeout=1800.0,
        )

    assert len(set(es.paths)) == 3


def test_embed_stall_timeout_default_from_config(tmp_path: Path) -> None:
    """embed.stall_timeout defaults to 1800.0 and is returned by resolve_embed_config."""
    store = tmp_path / "store"
    init_store(store, backend="none")
    _, _, _, stall = resolve_embed_config(store)
    assert stall == 1800.0
