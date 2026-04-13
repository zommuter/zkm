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
