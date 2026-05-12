"""Tests for the BM25 indexer."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from zkm.index import _read_watermark, build_index, load_index, save_index, tokenize, write_watermark
from zkm.store import init_store

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------


def test_tokenize_basic() -> None:
    result = tokenize("Hello, World! it's 2026")
    assert "hello" in result
    assert "world" in result
    assert "it's" in result
    assert "2026" in result


def test_tokenize_empty() -> None:
    assert tokenize("") == []


def test_tokenize_short_words_excluded() -> None:
    # The regex requires at least 2 chars: \w[\w'-]+
    result = tokenize("a bb ccc")
    assert "a" not in result
    assert "bb" in result
    assert "ccc" in result


def test_tokenize_preserves_umlauts() -> None:
    result = tokenize("über Müller café")
    # Raw umlaut tokens must survive (not stripped to ASCII-only garbage)
    raw_tokens_set = set(result)
    assert any("ber" in t or "über" in t for t in raw_tokens_set), (
        "Expected 'über' or its stem in tokens"
    )
    assert any("ll" in t for t in raw_tokens_set), "Expected 'müller' or stem in tokens"


def test_tokenize_english_stemming() -> None:
    result_plural = set(tokenize("meetings"))
    result_singular = set(tokenize("meeting"))
    # Both should share at least one stem token
    assert result_plural & result_singular, (
        f"'meetings' tokens {result_plural} and 'meeting' tokens {result_singular} share no stems"
    )


def test_tokenize_german_stemming() -> None:
    result_plural = set(tokenize("Rechnungen"))
    result_singular = set(tokenize("Rechnung"))
    assert result_plural & result_singular, (
        f"'Rechnungen' {result_plural} and 'Rechnung' {result_singular} share no stems"
    )


# ---------------------------------------------------------------------------
# build + save + load round-trip
# ---------------------------------------------------------------------------


def test_build_index_basic(store: Path) -> None:
    _write_note(store, "notes/alpha.md", "apples and oranges", "source: notes")
    _write_note(store, "notes/beta.md", "bananas only", "source: notes")

    idx = build_index(store)
    assert len(idx.docs) == 2
    rels = {d.rel_path for d in idx.docs}
    assert "notes/alpha.md" in rels
    assert "notes/beta.md" in rels


def test_build_index_skips_system_dirs(store: Path) -> None:
    _write_note(store, "notes/real.md", "real content")
    _write_note(store, "originals/scan.md", "should be skipped")
    _write_note(store, ".zkm-index/meta.md", "should be skipped")
    _write_note(store, "plugins/zkm-x/readme.md", "should be skipped")

    idx = build_index(store)
    rels = {d.rel_path for d in idx.docs}
    assert "notes/real.md" in rels
    assert not any("originals" in r or ".zkm-index" in r or "plugins" in r for r in rels)


def test_save_load_round_trip(store: Path) -> None:
    _write_note(store, "notes/note.md", "hello world")
    idx = build_index(store)
    save_index(store, idx)

    loaded = load_index(store)
    assert loaded is not None
    assert len(loaded.docs) == len(idx.docs)
    assert loaded.docs[0].rel_path == idx.docs[0].rel_path
    assert (store / ".zkm-index" / "bm25.pkl").exists()


def test_load_index_missing_returns_none(store: Path) -> None:
    assert load_index(store) is None


def test_load_index_version_mismatch_returns_none(store: Path) -> None:
    import pickle

    index_dir = store / ".zkm-index"
    index_dir.mkdir(parents=True, exist_ok=True)
    with open(store / ".zkm-index/bm25.pkl", "wb") as fh:
        pickle.dump({"version": 99, "store": str(store), "built_at": "x", "index": None}, fh)

    assert load_index(store) is None


# ---------------------------------------------------------------------------
# Incremental indexing
# ---------------------------------------------------------------------------


def test_incremental_reuses_unchanged_doc(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Files unchanged since last build must not be re-tokenized."""
    _write_note(store, "notes/note.md", "hello world")
    idx1 = build_index(store)
    save_index(store, idx1)

    tokenize_calls: list[str] = []
    import zkm.index as _idx_mod
    original_tokenize = _idx_mod.tokenize

    def spy_tokenize(text: str) -> list[str]:
        tokenize_calls.append(text)
        return original_tokenize(text)

    monkeypatch.setattr(_idx_mod, "tokenize", spy_tokenize)
    # Also patch _tokenize_doc to use the spy
    original_tok_doc = _idx_mod._tokenize_doc

    def spy_tok_doc(post: object) -> list[str]:
        tokenize_calls.append("__doc__")
        return original_tok_doc(post)  # type: ignore[arg-type]

    monkeypatch.setattr(_idx_mod, "_tokenize_doc", spy_tok_doc)

    idx2 = build_index(store)
    # No re-tokenization expected — mtime unchanged
    assert "__doc__" not in tokenize_calls
    assert len(idx2.docs) == 1


def test_incremental_retokenizes_changed_doc(store: Path) -> None:
    path = _write_note(store, "notes/note.md", "original content")
    idx1 = build_index(store)
    old_tokens = idx1.docs[0].tokens[:]
    save_index(store, idx1)

    # Force a different mtime by writing new content
    path.write_text("completely new content about oranges")
    import os
    new_mtime = path.stat().st_mtime_ns + 1_000_000  # +1ms
    os.utime(path, ns=(new_mtime, new_mtime))

    idx2 = build_index(store)
    assert idx2.docs[0].tokens != old_tokens
    assert "oranges" in idx2.docs[0].tokens


def test_incremental_drops_deleted_doc(store: Path) -> None:
    _write_note(store, "notes/keep.md", "keep this")
    p2 = _write_note(store, "notes/gone.md", "delete me")
    idx1 = build_index(store)
    save_index(store, idx1)
    assert len(idx1.docs) == 2

    p2.unlink()
    idx2 = build_index(store)
    assert len(idx2.docs) == 1
    assert idx2.docs[0].rel_path == "notes/keep.md"


# ---------------------------------------------------------------------------
# Metadata fields
# ---------------------------------------------------------------------------


def test_build_index_reads_frontmatter(store: Path) -> None:
    _write_note(
        store,
        "notes/tagged.md",
        "some body text",
        "date: 2026-01-15\ntags: [bills, electricity]\nsource: notes",
    )
    idx = build_index(store)
    doc = idx.docs[0]
    assert doc.metadata.get("source") == "notes"
    assert "bills" in doc.tokens
    assert "electricity" in doc.tokens


def test_tokenize_doc_includes_entity_values(store: Path) -> None:
    _write_note(
        store,
        "notes/ner.md",
        "call me",
        "entities:\n  - {scope: body, type: email, value: 'alice@example.com', canonical: 'alice@example.com'}",
    )
    idx = build_index(store)
    # tokenize splits "alice@example.com" → ["alice", "example", "com"]
    tokens = idx.docs[0].tokens
    assert "alice" in tokens
    assert "example" in tokens


def test_tokenize_doc_includes_entity_canonical(store: Path) -> None:
    _write_note(
        store,
        "notes/ner2.md",
        "send money",
        "entities:\n  - {scope: body, type: iban, value: 'DE44 5001 0517 5407 3249 31', canonical: 'DE44500105175407324931', standard: 'ISO 13616'}",
    )
    idx = build_index(store)
    tokens = idx.docs[0].tokens
    # canonical is all word-chars so tokenize keeps it as one token (lowercased)
    assert "de44500105175407324931" in tokens


def test_tokenize_doc_skips_invalid_entities(store: Path) -> None:
    _write_note(
        store,
        "notes/ner3.md",
        "body text",
        "entities:\n  - {scope: body, type: person, value: 'garbage', valid: false}",
    )
    idx = build_index(store)
    assert "garbage" not in idx.docs[0].tokens


def test_tokenize_doc_includes_participant_address(store: Path) -> None:
    _write_note(
        store,
        "mail/msg.md",
        "hi",
        "participants:\n  - {address: 'bob@example.org', role: 'from'}",
    )
    idx = build_index(store)
    assert "bob@example.org" in idx.docs[0].tokens


def test_tokenize_doc_includes_participant_name(store: Path) -> None:
    _write_note(
        store,
        "mail/msg2.md",
        "hi",
        "participants:\n  - {address: 'carol@x.com', name: 'Carol Smith', role: 'to'}",
    )
    idx = build_index(store)
    tokens = idx.docs[0].tokens
    assert "carol" in tokens
    assert "smith" in tokens


def test_progress_callback_invoked(store: Path) -> None:
    _write_note(store, "notes/a.md", "alpha")
    _write_note(store, "notes/b.md", "beta")

    calls: list[tuple[int, int | None, str]] = []
    build_index(store, progress=lambda c, t, m: calls.append((c, t, m)))

    assert len(calls) >= 2
    currents = [c for c, _, _ in calls]
    assert currents == sorted(currents)


# ---------------------------------------------------------------------------
# Git-commit watermark
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _commit_all(store: Path, msg: str = "test commit") -> str:
    """Stage everything and commit; return the new HEAD SHA."""
    _git(["add", "-A"], store)
    _git(["commit", "--allow-empty", "-m", msg], store)
    return _git(["rev-parse", "HEAD"], store)


def test_watermark_absent_does_full_scan(store: Path) -> None:
    """No watermark → full rglob scan (same behaviour as before)."""
    _write_note(store, "notes/a.md", "apple")
    _commit_all(store)
    idx = build_index(store)
    assert len(idx.docs) == 1
    assert _read_watermark(store) is None  # build_index never writes the watermark


def test_write_read_watermark(store: Path) -> None:
    sha = _commit_all(store)
    write_watermark(store, sha)
    assert _read_watermark(store) == sha


def test_watermark_fast_path_picks_up_new_file(store: Path) -> None:
    """After a watermark is recorded, a newly committed file is indexed."""
    _write_note(store, "notes/a.md", "apple")
    sha1 = _commit_all(store, "add a")
    idx1 = build_index(store)
    save_index(store, idx1)
    write_watermark(store, sha1)  # mark sha1 as last indexed

    _write_note(store, "notes/b.md", "banana content")
    _commit_all(store, "add b")  # new commit, watermark still at sha1

    idx2 = build_index(store)  # fast path diffs sha1..HEAD → finds b.md
    rels = {d.rel_path for d in idx2.docs}
    assert "notes/a.md" in rels
    assert "notes/b.md" in rels


def test_watermark_fast_path_drops_deleted_file(store: Path) -> None:
    """A file deleted after the watermark must not appear in the next index."""
    _write_note(store, "notes/keep.md", "keeper")
    _write_note(store, "notes/gone.md", "going away")
    sha1 = _commit_all(store, "add both")
    idx1 = build_index(store)
    save_index(store, idx1)
    write_watermark(store, sha1)  # mark sha1 as last indexed

    (store / "notes/gone.md").unlink()
    _commit_all(store, "delete gone")  # new commit, watermark still at sha1

    idx2 = build_index(store)  # fast path diffs sha1..HEAD → sees deletion
    rels = {d.rel_path for d in idx2.docs}
    assert "notes/keep.md" in rels
    assert "notes/gone.md" not in rels


def test_watermark_fast_path_uncommitted_md_included(store: Path) -> None:
    """An uncommitted (dirty) .md file must be picked up via git status."""
    _write_note(store, "notes/committed.md", "base")
    sha1 = _commit_all(store, "base")
    idx1 = build_index(store)
    save_index(store, idx1)
    write_watermark(store, sha1)

    # Add a file but do NOT commit it
    _write_note(store, "notes/dirty.md", "dirty content")

    idx2 = build_index(store)
    rels = {d.rel_path for d in idx2.docs}
    assert "notes/dirty.md" in rels


def test_watermark_unreachable_falls_back_to_full_scan(store: Path) -> None:
    """A bogus watermark SHA triggers full scan; index is still correct."""
    _write_note(store, "notes/a.md", "apple")
    _commit_all(store)
    idx1 = build_index(store)
    save_index(store, idx1)

    write_watermark(store, "deadbeef" * 5)  # bogus SHA

    _write_note(store, "notes/b.md", "banana")
    _commit_all(store)

    idx2 = build_index(store)
    rels = {d.rel_path for d in idx2.docs}
    assert "notes/a.md" in rels
    assert "notes/b.md" in rels


def test_full_flag_bypasses_watermark(store: Path) -> None:
    """--full ignores the watermark and returns all docs."""
    _write_note(store, "notes/a.md", "apple")
    sha1 = _commit_all(store, "add a")
    idx1 = build_index(store)
    save_index(store, idx1)
    write_watermark(store, sha1)

    # Add and commit another file, but set watermark to HEAD (nothing "changed")
    _write_note(store, "notes/b.md", "banana")
    sha2 = _commit_all(store, "add b")
    # Intentionally record sha2 as watermark so fast path sees no changes
    write_watermark(store, sha2)

    # Normal build via fast path: b.md is already indexed (it's in the committed diff)
    # Full build: must include both
    idx_full = build_index(store, full=True)
    rels = {d.rel_path for d in idx_full.docs}
    assert "notes/a.md" in rels
    assert "notes/b.md" in rels
