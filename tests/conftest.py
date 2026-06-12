"""Session-wide test configuration for zkm."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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


@pytest.fixture(autouse=True)
def _no_gamemode_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point the gamemode-lock guard (roadmap:1098) at a path that never exists.

    Hermeticity: tests must not change behaviour because a real
    /tmp/zomni-gamemode.lock happens to exist on the dev machine. The guard's
    own tests in test_gamemode_guard.py override this env var explicitly.
    """
    monkeypatch.setenv("ZKM_GAMEMODE_LOCK", str(tmp_path / "no-such-gamemode.lock"))


@pytest.fixture(autouse=True)
def _no_self_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable systemd-run self-scoping (roadmap:62f3) for all tests.

    An os.execvpe re-exec inside pytest/CliRunner would replace the test
    process. test_selfscope.py opts back in explicitly and monkeypatches the
    exec/systemctl layer instead.
    """
    monkeypatch.setenv("ZKM_NO_SELF_SCOPE", "1")


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
