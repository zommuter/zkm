"""Tests for the dirty-tree guard (zkm.devcheck)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import click
import pytest

from zkm import devcheck
from zkm.devcheck import assert_clean, find_repo_root, is_dirty


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_git_repo(path: Path) -> Path:
    """Initialise a bare-minimum git repo with one committed file."""
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "tracked.txt").write_text("hello\n")
    _git(path, "add", "tracked.txt")
    _git(path, "commit", "-m", "init")
    return path


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def make_plugin_dir(plugins_root: Path, name: str, *, with_git: bool = True) -> Path:
    """Create a fake plugin dir under plugins_root with plugin.yaml."""
    plugin_dir = plugins_root / f"zkm-{name}"
    if with_git:
        make_git_repo(plugin_dir)
    else:
        plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.yaml").write_text(
        f"name: zkm-{name}\nversion: 0.1.0\ndescription: test\n"
    )
    return plugin_dir


# ---------------------------------------------------------------------------
# find_repo_root
# ---------------------------------------------------------------------------


def test_find_repo_root_finds_ancestor(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    assert find_repo_root(nested) == repo


def test_find_repo_root_no_git(tmp_path: Path) -> None:
    assert find_repo_root(tmp_path) is None


# ---------------------------------------------------------------------------
# is_dirty
# ---------------------------------------------------------------------------


def test_is_dirty_clean_repo(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    dirty, summary = is_dirty(repo)
    assert not dirty
    assert summary == ""


def test_is_dirty_modified_tracked_file(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    (repo / "tracked.txt").write_text("modified\n")
    dirty, summary = is_dirty(repo)
    assert dirty
    assert summary != ""


def test_is_dirty_untracked_file_does_not_count(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    (repo / "untracked.txt").write_text("new file\n")
    dirty, _ = is_dirty(repo)
    assert not dirty


# ---------------------------------------------------------------------------
# assert_clean
# ---------------------------------------------------------------------------


def _patch_core(monkeypatch: pytest.MonkeyPatch, core_path: Path) -> None:
    """Make assert_clean think zkm.__file__ lives at core_path/zkm/__init__.py."""
    monkeypatch.setattr(devcheck, "_zkm_module_path", lambda: core_path / "src" / "zkm" / "__init__.py")


def test_assert_clean_passes_on_clean_core(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    core_repo = make_git_repo(tmp_path / "core")
    _patch_core(monkeypatch, core_repo)
    (core_repo / "src" / "zkm").mkdir(parents=True)
    assert_clean()  # must not raise


def test_assert_clean_raises_on_dirty_core(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZKM_BYPASS_DIRTY_CHECK", raising=False)
    core_repo = make_git_repo(tmp_path / "core")
    _patch_core(monkeypatch, core_repo)
    (core_repo / "src" / "zkm").mkdir(parents=True)
    (core_repo / "tracked.txt").write_text("wip\n")  # dirty tracked file
    with pytest.raises(click.ClickException, match="uncommitted changes"):
        assert_clean()


def test_assert_clean_raises_on_dirty_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ZKM_BYPASS_DIRTY_CHECK", raising=False)
    core_repo = make_git_repo(tmp_path / "core")
    _patch_core(monkeypatch, core_repo)
    (core_repo / "src" / "zkm").mkdir(parents=True)

    plugins_root = tmp_path / "plugins"
    plugin_dir = make_plugin_dir(plugins_root, "eml")
    (plugin_dir / "tracked.txt").write_text("wip\n")  # dirty plugin

    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(plugins_root))
    with pytest.raises(click.ClickException, match="uncommitted changes"):
        assert_clean(plugin_name="zkm-eml")


def test_assert_clean_scope_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dirty plugin X does not block 'convert plugin Y'."""
    core_repo = make_git_repo(tmp_path / "core")
    _patch_core(monkeypatch, core_repo)
    (core_repo / "src" / "zkm").mkdir(parents=True)

    plugins_root = tmp_path / "plugins"
    make_plugin_dir(plugins_root, "eml")   # clean
    pdf_dir = make_plugin_dir(plugins_root, "pdf")
    (pdf_dir / "tracked.txt").write_text("wip\n")  # dirty — but different plugin

    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(plugins_root))
    # Converting zkm-eml should pass even though zkm-pdf is dirty
    assert_clean(plugin_name="zkm-eml")


def test_assert_clean_bypass_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core_repo = make_git_repo(tmp_path / "core")
    _patch_core(monkeypatch, core_repo)
    (core_repo / "src" / "zkm").mkdir(parents=True)
    (core_repo / "tracked.txt").write_text("wip\n")  # dirty

    monkeypatch.setenv("ZKM_BYPASS_DIRTY_CHECK", "1")
    assert_clean()  # must not raise despite dirty tree


def test_assert_clean_non_editable_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If zkm.__file__ has no .git/ ancestor, the check is a no-op."""
    no_git_dir = tmp_path / "usr" / "lib" / "python3" / "zkm"
    no_git_dir.mkdir(parents=True)
    monkeypatch.setattr(devcheck, "_zkm_module_path", lambda: no_git_dir / "__init__.py")
    assert_clean()  # must not raise


def test_assert_clean_unknown_plugin_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unknown plugin name does not crash; convert will error clearly later."""
    core_repo = make_git_repo(tmp_path / "core")
    _patch_core(monkeypatch, core_repo)
    (core_repo / "src" / "zkm").mkdir(parents=True)
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(tmp_path / "empty-plugins"))
    assert_clean(plugin_name="zkm-nonexistent")  # must not raise


def test_assert_clean_plugin_without_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plugin installed without its own .git/ (plain dir/symlink) — no-op for plugin check."""
    core_repo = make_git_repo(tmp_path / "core")
    _patch_core(monkeypatch, core_repo)
    (core_repo / "src" / "zkm").mkdir(parents=True)

    plugins_root = tmp_path / "plugins"
    make_plugin_dir(plugins_root, "notes", with_git=False)

    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(plugins_root))
    assert_clean(plugin_name="zkm-notes")  # must not raise
