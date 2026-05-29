"""Session-wide test configuration for zkm."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from zkm.store import init_store


@pytest.fixture(autouse=True)
def _bypass_dirty_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the dirty-tree guard for all tests by default.

    CLI-touching tests should not fail because the source tree is dirty during
    development. The guard's own correctness is covered in test_devcheck.py,
    where individual tests explicitly clear this env var.
    """
    monkeypatch.setenv("ZKM_BYPASS_DIRTY_CHECK", "1")


@pytest.fixture()
def store(tmp_path: Path) -> Path:
    sdir = tmp_path / "store"
    init_store(sdir, backend="none")
    return sdir


@pytest.fixture()
def make_note(store: Path) -> Callable[..., Path]:
    """Return a helper that writes a markdown note into the test store."""

    def _make(rel: str, body: str, frontmatter: str = "") -> Path:
        path = store / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        fm = f"---\n{frontmatter}\n---\n" if frontmatter else ""
        path.write_text(fm + body)
        return path

    return _make
