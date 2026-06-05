"""Smoke tests for zkm.store.init_store."""

import subprocess
from pathlib import Path

import pytest

from zkm.store import init_store


def test_init_creates_structure(tmp_path: Path) -> None:
    init_store(tmp_path, backend="none")

    assert (tmp_path / ".git").is_dir()
    assert (tmp_path / ".zkm-config").read_text().strip() == "binary_backend=none"
    assert (tmp_path / ".gitignore").exists()
    assert (tmp_path / ".env").exists()
    for d in ("inbox", "notes", "originals"):
        assert (tmp_path / d).is_dir()
        assert (tmp_path / d / ".gitkeep").exists()


def test_init_makes_initial_commit(tmp_path: Path) -> None:
    init_store(tmp_path, backend="none")

    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "initialize zkm knowledge store" in result.stdout


def test_init_idempotent(tmp_path: Path) -> None:
    init_store(tmp_path, backend="none")
    # Second call must not raise and must not create a second commit
    init_store(tmp_path, backend="none")

    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(result.stdout.strip().splitlines()) == 1


def test_init_auto_backend_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force auto-detect to find nothing → should fall back to 'none'
    monkeypatch.setattr("shutil.which", lambda _: None)
    init_store(tmp_path, backend="auto")
    assert "binary_backend=none" in (tmp_path / ".zkm-config").read_text()


class TestEnsureGitignorePatterns:
    def test_appends_missing(self, tmp_path: Path) -> None:
        from zkm.cli import _ensure_gitignore_patterns

        gi = tmp_path / ".gitignore"
        gi.write_text("*.swp\n")
        _ensure_gitignore_patterns(tmp_path, ["inbox/foo.db", "inbox/foo.db.crypt15"])
        lines = gi.read_text().splitlines()
        assert "inbox/foo.db" in lines
        assert "inbox/foo.db.crypt15" in lines

    def test_skips_already_present(self, tmp_path: Path) -> None:
        from zkm.cli import _ensure_gitignore_patterns

        gi = tmp_path / ".gitignore"
        gi.write_text("*.swp\ninbox/foo.db\n")
        _ensure_gitignore_patterns(tmp_path, ["inbox/foo.db"])
        assert gi.read_text().count("inbox/foo.db") == 1

    def test_creates_gitignore_if_absent(self, tmp_path: Path) -> None:
        from zkm.cli import _ensure_gitignore_patterns

        _ensure_gitignore_patterns(tmp_path, ["inbox/foo.db"])
        assert "inbox/foo.db" in (tmp_path / ".gitignore").read_text()
