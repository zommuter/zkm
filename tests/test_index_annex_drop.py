"""Tests for embeddings.npz annex tier and superseded-key drop hook.

# roadmap:7e21

Hermetic tests: no real embedding model is loaded.  git-annex must be on PATH
(it is on zomni and cartmanjaro).  The conftest `store` fixture uses backend="none";
here we use a dedicated `annex_store` fixture that initialises a real annex repo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _annex(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", "annex", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _annex_key_count(store: Path, suffix: str = ".npz") -> int:
    """Count distinct annex keys locally present matching *suffix*.

    git-annex stores each key as ``.git/annex/objects/<aa>/<bb>/<keyname>/<keyname>``.
    The depth-3 directories (``<keyname>`` dirs — one per key) are counted via
    ``find -mindepth 3 -maxdepth 3 -type d``.  After ``git annex drop``, the dir
    is removed.
    """
    annex_obj_dir = store / ".git" / "annex" / "objects"
    if not annex_obj_dir.exists():
        return 0
    # depth-3 dirs relative to annex_obj_dir: <aa>/<bb>/<keyname>
    result = subprocess.run(
        ["find", str(annex_obj_dir), "-mindepth", "3", "-maxdepth", "3",
         "-type", "d", "-name", f"*{suffix}"],
        capture_output=True,
        text=True,
    )
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    return len(lines)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def annex_store(tmp_path: Path) -> Path:
    """A git-annex initialised store with the zkm gitattributes template."""
    from zkm.store import _GITATTRIBUTES_ANNEX, _GITIGNORE

    sdir = tmp_path / "store"
    sdir.mkdir()

    # Bootstrap minimal git repo + annex
    _git(["init", "-q"], sdir)
    _git(["config", "user.email", "test@example.com"], sdir)
    _git(["config", "user.name", "Test"], sdir)
    _annex(["init", "test-store", "-q"], sdir)
    # Allow git-annex to track dotfile paths (.zkm-index/embeddings.npz).
    # Without this, git-annex ignores annex.largefiles=anything for dotfiles.
    _annex(["config", "--set", "annex.dotfiles", "true"], sdir)

    # Write the zkm gitattributes and gitignore templates
    (sdir / ".gitattributes").write_text(_GITATTRIBUTES_ANNEX)
    (sdir / ".gitignore").write_text(_GITIGNORE)
    (sdir / "notes").mkdir()
    (sdir / "notes" / ".gitkeep").touch()

    _git(["add", ".gitattributes", ".gitignore", "notes/.gitkeep"], sdir)
    _git(["commit", "-m", "init store", "-q"], sdir)

    return sdir


def _make_fake_npz(store: Path) -> None:
    """Write a small fake embeddings.npz so the test has a real file to annex."""
    index_dir = store / ".zkm-index"
    index_dir.mkdir(parents=True, exist_ok=True)
    npz_path = store / ".zkm-index" / "embeddings.npz"
    npz_tmp = npz_path.with_name(npz_path.name + ".tmp")
    with open(npz_tmp, "wb") as f:
        np.savez_compressed(
            f,
            paths=np.array(["notes/a.md"], dtype=object),
            mtimes_ns=np.array([12345], dtype=np.int64),
            chunk_indices=np.array([0], dtype=np.int32),
            vectors=np.random.rand(1, 4).astype(np.float32),
        )
    import os
    os.replace(npz_tmp, npz_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_gitattributes_embeddings_npz_is_annexed(annex_store: Path) -> None:
    """check-attr for .zkm-index/embeddings.npz must resolve to annex.largefiles=anything.

    The gitattributes template in store.py must carry an explicit rule so the
    embeddings artifact is annexed rather than forced to git.
    """
    result = subprocess.run(
        ["git", "check-attr", "annex.largefiles", ".zkm-index/embeddings.npz"],
        cwd=annex_store,
        capture_output=True,
        text=True,
        check=True,
    )
    # Expected: ".zkm-index/embeddings.npz: annex.largefiles: anything"
    assert "anything" in result.stdout, (
        f"Expected annex.largefiles=anything for .zkm-index/embeddings.npz, got: {result.stdout!r}"
    )


def test_gitattributes_bm25_pkl_is_not_annexed(annex_store: Path) -> None:
    """bm25.pkl is T4 (regenerate); it must NOT carry annex.largefiles=anything.

    It is gitignored and no explicit annex rule should pin stale copies.
    """
    result = subprocess.run(
        ["git", "check-attr", "annex.largefiles", ".zkm-index/bm25.pkl"],
        cwd=annex_store,
        capture_output=True,
        text=True,
        check=True,
    )
    # Must NOT have anything — either "unspecified" or "nothing"
    assert "anything" not in result.stdout, (
        f"bm25.pkl should not be annexed (T4), but got: {result.stdout!r}"
    )


def test_annex_drop_superseded_key_leaves_one_key(annex_store: Path) -> None:
    """After two save_embed_store + annex_add_and_commit + drop cycles,
    exactly one embeddings.npz annex key must remain in the local annex.

    This is the core of id:7e21's acceptance: no annex pileup.
    """
    from zkm.embed import (
        annex_add_and_commit,
        annex_drop_superseded_key,
        get_annex_key,
    )

    # --- Cycle 1: write first embeddings.npz ---
    _make_fake_npz(annex_store)
    old_key_1 = get_annex_key(annex_store, ".zkm-index/embeddings.npz")
    # First time: no old key yet (file is new)
    assert old_key_1 == "", f"Expected no key before first add, got: {old_key_1!r}"

    ok = annex_add_and_commit(annex_store, ".zkm-index/embeddings.npz")
    assert ok, "First annex_add_and_commit should succeed"

    key_after_first = get_annex_key(annex_store, ".zkm-index/embeddings.npz")
    assert key_after_first, "Expected a key after first add"

    # Key count should be 1
    count_after_first = _annex_key_count(annex_store)
    assert count_after_first == 1, f"Expected 1 annex key after first add, got {count_after_first}"

    # --- Cycle 2: write new embeddings.npz (different content → new key) ---
    # Capture old key before overwriting (mirrors get_annex_key call in cmd_index).
    old_key_before_second = get_annex_key(annex_store, ".zkm-index/embeddings.npz")

    # Simulate save_embed_store: write to .tmp then os.replace over the symlink.
    # os.replace replaces the symlink itself (not the target), making it a plain file.
    _make_fake_npz(annex_store)  # new random vectors; os.replace inside replaces symlink

    ok2 = annex_add_and_commit(annex_store, ".zkm-index/embeddings.npz")
    assert ok2, "Second annex_add_and_commit should succeed"

    _key_after_second = get_annex_key(annex_store, ".zkm-index/embeddings.npz")
    # Keys may be identical if random content collides — but with random 4-float vecs
    # that's astronomically unlikely; if they ARE identical, drop is a no-op (still 1 key).

    # Drop the old key
    annex_drop_superseded_key(annex_store, old_key_before_second)

    # Exactly one key should remain
    count_after_drop = _annex_key_count(annex_store)
    assert count_after_drop == 1, (
        f"Expected exactly 1 annex key after drop, got {count_after_drop}"
    )


def test_get_annex_key_returns_empty_for_non_annexed_store(tmp_path: Path) -> None:
    """get_annex_key returns '' when git-annex is not initialised (graceful)."""
    from zkm.embed import get_annex_key

    sdir = tmp_path / "plain"
    sdir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=sdir, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=sdir, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=sdir, check=True)
    # No annex init
    key = get_annex_key(sdir, ".zkm-index/embeddings.npz")
    assert key == "", f"Expected '' for non-annex store, got: {key!r}"


def test_annex_drop_superseded_key_noop_on_empty_key(annex_store: Path) -> None:
    """annex_drop_superseded_key('') must silently no-op (first-run safety)."""
    from zkm.embed import annex_drop_superseded_key

    # Should not raise
    annex_drop_superseded_key(annex_store, "")
