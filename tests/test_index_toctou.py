"""TOCTOU hardening for build_index file enumeration (id:f1d7).

The full-rebuild path was hotfixed (commit 6dc0132) to skip a file that
vanishes between rglob enumeration and stat() — a real race against the chat
by-id rename / Syncthing churn. The *incremental* fast path still does an
`exists()`-then-`stat()` two-step, which has the same TOCTOU window: a file
present at `exists()` can be gone by the explicit `stat()`. This suite specs
unifying both paths on the try/except guard.

# roadmap:f1d7
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from zkm.index import build_index, save_index, write_watermark


def _commit_all(store: Path, msg: str = "test commit") -> str:
    subprocess.run(["git", "-C", str(store), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(store), "commit", "-m", msg, "--allow-empty"],
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "-C", str(store), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_full_rebuild_skips_vanished_file(
    store: Path, make_note: Callable[..., Path], monkeypatch
) -> None:
    """Regression guard for the shipped hotfix: full rebuild skips a file whose
    stat() raises FileNotFoundError instead of crashing the whole run."""
    make_note("notes/keep.md", "keeper")
    make_note("notes/gone.md", "going away")

    real_stat = Path.stat

    def flaky_stat(self: Path, *a, **k):
        if str(self).endswith("notes/gone.md"):
            raise FileNotFoundError(self)
        return real_stat(self, *a, **k)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    idx = build_index(store, full=True)  # must not raise
    rels = {d.rel_path for d in idx.docs}
    assert "notes/keep.md" in rels
    assert "notes/gone.md" not in rels


def test_incremental_path_survives_stat_toctou(
    store: Path, make_note: Callable[..., Path], monkeypatch
) -> None:
    """Incremental fast path: a changed file that exists() at check time but is
    gone by the explicit stat() (the TOCTOU window) must be skipped, not crash.

    Currently RED — the incremental loop does `exists()` then a bare `stat()`.
    """
    make_note("notes/a.md", "apple")
    sha1 = _commit_all(store, "add a")
    idx1 = build_index(store)
    save_index(store, idx1)
    write_watermark(store, sha1)  # mark sha1 as last indexed

    make_note("notes/b.md", "banana content")
    _commit_all(store, "add b")  # b.md is the only changed candidate

    real_stat = Path.stat
    calls = {"n": 0}

    def flaky_stat(self: Path, *a, **k):
        # Let exists() (call 1) succeed, then make the explicit stat() (call 2)
        # raise — simulating the file vanishing inside the TOCTOU window.
        if str(self).endswith("notes/b.md"):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise FileNotFoundError(self)
        return real_stat(self, *a, **k)

    monkeypatch.setattr(Path, "stat", flaky_stat)

    idx2 = build_index(store)  # must not raise; b.md simply skipped this round
    rels = {d.rel_path for d in idx2.docs}
    assert "notes/a.md" in rels
    assert "notes/b.md" not in rels
