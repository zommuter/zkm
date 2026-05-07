"""Tests for hybrid search recall, SearchTrace, and CLI dense-skip warnings."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from zkm.embed import EmbedStore, EmbedUnavailable, save_embed_store
from zkm.index import build_index, save_index
from zkm.query import SearchTrace, search_hybrid_traced
from zkm.store import init_store


@pytest.fixture()
def store(tmp_path: Path) -> Path:
    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    return sdir


def _write_and_index(store: Path, docs: list[tuple[str, str]]) -> None:
    for rel, body in docs:
        p = store / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    idx = build_index(store)
    save_index(store, idx)


def _make_embed_store(store: Path, paths: list[str], vecs: np.ndarray) -> None:
    es = EmbedStore(
        paths=paths,
        mtimes_ns=[0] * len(paths),
        vectors=vecs.astype(np.float32),
        model="bge-m3",
    )
    save_embed_store(store, es)


# ---------------------------------------------------------------------------
# Pool width drives cross-lingual recall
# ---------------------------------------------------------------------------


def test_dense_pool_width_determines_cross_lingual_recall(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pool widening is what enables cross-lingual recall on literal-heavy corpora.

    With 50 literal docs (cosine ~0.98 with query) and 1 cross-lingual doc
    (cosine ~0.72), the cross-lingual sits at rank 51 in dense. The old
    pool (top_k * 3 = 15 for top_k=5) excludes it; the new floor (200) includes it.
    """
    monkeypatch.setenv("ZKM_EMBED_ENDPOINT", "http://localhost:8080")
    monkeypatch.delenv("ZKM_EMBED_MODEL", raising=False)

    dim = 4
    n_literal = 50  # > old pool (top_k*3=15), < new floor (200)

    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.05, (n_literal, dim)).astype(np.float32)
    literal_vecs = np.tile([1.0, 0.0, 0.0, 0.0], (n_literal, 1)).astype(np.float32) + noise
    norms = np.linalg.norm(literal_vecs, axis=1, keepdims=True)
    literal_vecs = literal_vecs / norms

    # cross-lingual doc at cosine ~0.72 with query direction [1,0,0,0]
    cross_vec = np.array([[0.72, 0.694, 0.0, 0.0]], dtype=np.float32)
    cross_vec /= np.linalg.norm(cross_vec)

    all_vecs = np.concatenate([literal_vecs, cross_vec], axis=0)

    docs = [(f"notes/literal_{i:03d}.md", f"Rechnung Stadtwerke {i}") for i in range(n_literal)]
    docs.append(("notes/cross_lingual.md", "invoice electricity payment"))
    _write_and_index(store, docs)

    paths = [f"notes/literal_{i:03d}.md" for i in range(n_literal)] + ["notes/cross_lingual.md"]
    _make_embed_store(store, paths, all_vecs)

    query_vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    cross_idx = n_literal  # index of cross_lingual.md in paths

    # Direct pool test: old pool (top_k*3=15) excludes; new floor (200) includes
    es = EmbedStore(paths=paths, mtimes_ns=[0] * (n_literal + 1), vectors=all_vecs, model="bge-m3")
    narrow_indices = {i for i, _ in es.topk(query_vec, 15)}
    wide_indices = {i for i, _ in es.topk(query_vec, 200)}
    assert cross_idx not in narrow_indices, "cross-lingual should be absent from narrow pool"
    assert cross_idx in wide_indices, "cross-lingual should be in wide pool (new floor=200)"

    # Full search_hybrid with large top_k (wide pool) surfaces the cross-lingual
    monkeypatch.setattr("zkm.query.embed_texts", lambda *a, **kw: query_vec.reshape(1, -1))
    hits, trace = search_hybrid_traced(store, "Rechnung", top_k=55, dense=True)
    assert trace.dense_skipped_reason is None
    assert trace.dense_hits > 0
    assert "notes/cross_lingual.md" in [h.path for h in hits]


# ---------------------------------------------------------------------------
# SearchTrace — dense-skip reasons
# ---------------------------------------------------------------------------


def test_search_hybrid_trace_no_embed_store(store: Path) -> None:
    """Trace reports 'no_embed_store' when dense=True but no EmbedStore exists."""
    _write_and_index(store, [("notes/doc.md", "electricity bill")])
    hits, trace = search_hybrid_traced(store, "electricity", top_k=5, dense=True)
    assert any("doc" in h.path for h in hits)
    assert trace.dense_skipped_reason == "no_embed_store"
    assert trace.dense_hits == 0


def test_search_hybrid_trace_no_endpoint(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trace reports 'no_endpoint' when embed endpoint is explicitly disabled."""
    _write_and_index(store, [("notes/doc.md", "electricity bill")])
    _make_embed_store(store, ["notes/doc.md"], np.eye(1, 4))
    monkeypatch.setenv("ZKM_EMBED_ENDPOINT", "")  # explicit empty → disabled
    hits, trace = search_hybrid_traced(store, "electricity", top_k=5, dense=True)
    assert any("doc" in h.path for h in hits)
    assert trace.dense_skipped_reason == "no_endpoint"
    assert trace.dense_hits == 0


def test_search_hybrid_trace_embed_failed(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trace reports 'embed_failed' when the embed request raises EmbedUnavailable."""
    _write_and_index(store, [("notes/doc.md", "electricity bill")])
    _make_embed_store(store, ["notes/doc.md"], np.eye(1, 4))
    monkeypatch.setenv("ZKM_EMBED_ENDPOINT", "http://localhost:8080")

    def _raise(*a, **kw):
        raise EmbedUnavailable("connection refused")

    monkeypatch.setattr("zkm.query.embed_texts", _raise)
    hits, trace = search_hybrid_traced(store, "electricity", top_k=5, dense=True)
    assert any("doc" in h.path for h in hits)
    assert trace.dense_skipped_reason == "embed_failed"
    assert trace.dense_hits == 0


# ---------------------------------------------------------------------------
# CLI: stderr warning when dense is skipped
# ---------------------------------------------------------------------------


def test_cmd_search_warns_on_dense_skip(tmp_path: Path) -> None:
    """zkm search emits a stderr warning when dense leg is skipped."""
    from click.testing import CliRunner

    from zkm.cli import main

    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    (sdir / "notes").mkdir(exist_ok=True)
    (sdir / "notes" / "doc.md").write_text("electricity bill")
    idx = build_index(sdir)
    save_index(sdir, idx)
    # No EmbedStore → dense will be skipped with "no_embed_store"

    runner = CliRunner()
    result = runner.invoke(main, ["search", "--store", str(sdir), "electricity"])
    assert result.exit_code == 0
    assert "dense leg skipped" in (result.stderr or "")
    assert "no_embed_store" in (result.stderr or "")


# ---------------------------------------------------------------------------
# CLI: --expand routes through search_with_expansion_traced
# ---------------------------------------------------------------------------


def test_cmd_search_expand_calls_search_with_expansion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--expand flag routes through search_with_expansion_traced; default uses search_hybrid_traced."""
    from click.testing import CliRunner

    from zkm.cli import main

    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    (sdir / "notes").mkdir(exist_ok=True)
    (sdir / "notes" / "doc.md").write_text("electricity bill")
    idx = build_index(sdir)
    save_index(sdir, idx)

    expansion_called: list[int] = []
    hybrid_called: list[int] = []

    def fake_expansion(*a, **kw):
        expansion_called.append(1)
        return [], SearchTrace(0, 0, None, True)

    def fake_hybrid(*a, **kw):
        hybrid_called.append(1)
        return [], SearchTrace(0, 0, None, False)

    runner = CliRunner()

    # Without --expand: search_hybrid_traced should be called
    with monkeypatch.context() as m:
        m.setattr("zkm.query.search_hybrid_traced", fake_hybrid)
        m.setattr("zkm.query.search_with_expansion_traced", fake_expansion)
        runner.invoke(main, ["search", "--store", str(sdir), "test"])
    assert hybrid_called, "search_hybrid_traced should be called without --expand"
    assert not expansion_called, "search_with_expansion_traced should not be called without --expand"

    expansion_called.clear()
    hybrid_called.clear()

    # With --expand: search_with_expansion_traced should be called
    with monkeypatch.context() as m:
        m.setattr("zkm.query.search_hybrid_traced", fake_hybrid)
        m.setattr("zkm.query.search_with_expansion_traced", fake_expansion)
        runner.invoke(main, ["search", "--store", str(sdir), "--expand", "test"])
    assert expansion_called, "search_with_expansion_traced should be called with --expand"
    assert not hybrid_called, "search_hybrid_traced should not be called with --expand"


def test_search_show_expansion_prints_keywords(tmp_path: Path, monkeypatch) -> None:
    """--show-expansion prints keywords and hyp_text to stderr when trace contains them."""
    from click.testing import CliRunner

    from zkm.cli import main
    from zkm.query import SearchTrace

    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    (sdir / "notes").mkdir(exist_ok=True)
    (sdir / "notes" / "doc.md").write_text("electricity bill")
    idx = build_index(sdir)
    save_index(sdir, idx)

    stub_trace = SearchTrace(1, 0, None, True, ["Stromrechnung", "utility invoice"], "Here is a sample electricity bill.")

    def fake_expansion(*a, **kw):
        return [], stub_trace

    runner = CliRunner()
    with monkeypatch.context() as m:
        m.setattr("zkm.query.search_with_expansion_traced", fake_expansion)
        result = runner.invoke(main, ["search", "--store", str(sdir), "--expand", "--show-expansion", "test"])

    assert "zkm: query expansion" in result.output
    assert "Stromrechnung" in result.output
    assert "utility invoice" in result.output
    assert "Here is a sample electricity bill." in result.output
    assert result.exit_code == 0


def test_search_show_expansion_silent_without_expand(tmp_path: Path, monkeypatch) -> None:
    """--show-expansion without --expand is a silent no-op (trace has no keywords)."""
    from click.testing import CliRunner

    from zkm.cli import main
    from zkm.query import SearchTrace

    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    (sdir / "notes").mkdir(exist_ok=True)
    (sdir / "notes" / "doc.md").write_text("electricity bill")
    idx = build_index(sdir)
    save_index(sdir, idx)

    def fake_hybrid(*a, **kw):
        return [], SearchTrace(0, 0, None, False)

    runner = CliRunner()
    with monkeypatch.context() as m:
        m.setattr("zkm.query.search_hybrid_traced", fake_hybrid)
        result = runner.invoke(main, ["search", "--store", str(sdir), "--show-expansion", "test"])

    assert "query expansion" not in result.output
    assert result.exit_code == 0


def test_query_show_expansion_prints_keywords(tmp_path: Path, monkeypatch) -> None:
    """zkm query --show-expansion prints expansion block to stderr without polluting stdout."""
    from click.testing import CliRunner

    from zkm.cli import main
    from zkm.query import SearchTrace

    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    (sdir / "notes").mkdir(exist_ok=True)
    (sdir / "notes" / "doc.md").write_text("electricity bill")
    idx = build_index(sdir)
    save_index(sdir, idx)

    stub_trace = SearchTrace(1, 0, None, True, ["Stromrechnung"], "A hypothetical answer.")

    def fake_expansion(*a, **kw):
        return [], stub_trace

    def fake_llm_stream(*a, **kw):
        yield "answer text"

    runner = CliRunner()
    with monkeypatch.context() as m:
        m.setattr("zkm.query.search_with_expansion_traced", fake_expansion)
        m.setattr("zkm.query.llm_stream", fake_llm_stream)
        result = runner.invoke(main, ["query", "--store", str(sdir), "--show-expansion", "test question"])

    assert "zkm: query expansion" in result.output
    assert "Stromrechnung" in result.output
    assert "A hypothetical answer." in result.output
    assert "answer text" in result.output
    assert result.exit_code == 0
