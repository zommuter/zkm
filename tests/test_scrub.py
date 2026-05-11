"""Tests for zkm.scrub (run_scrub dispatch) and CLI cmd_scrub."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import frontmatter
import pytest
from click.testing import CliRunner

from zkm.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_store(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for cmd in [
        ["git", "init", "-q", str(path)],
        ["git", "-C", str(path), "config", "user.email", "t@test"],
        ["git", "-C", str(path), "config", "user.name", "T"],
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init", "-q"],
    ]:
        subprocess.run(cmd, check=True, capture_output=True)


def _make_md(directory: Path, filename: str, **meta) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(frontmatter.dumps(frontmatter.Post("body", **meta)), encoding="utf-8")
    return path


def _make_plugin(plugins_dir: Path, name: str, has_scrub: bool = True) -> Path:
    plugin_dir = plugins_dir / f"zkm-{name}"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.yaml").write_text(
        f"name: {name}\nversion: 0.1.0\ndescription: test\n"
    )
    if has_scrub:
        (plugin_dir / "convert.py").write_text(
            "def convert(store_path, config, **kw): return []\n"
            "def scrub(store_path, config, *, dry_run=True, verbose=False, progress=None):\n"
            "    return {'files_scanned': 1, 'files_changed': 0, 'entities_removed': 0}\n"
        )
    else:
        (plugin_dir / "convert.py").write_text(
            "def convert(store_path, config, **kw): return []\n"
        )
    return plugin_dir


# ---------------------------------------------------------------------------
# run_scrub unit tests
# ---------------------------------------------------------------------------


def test_run_scrub_raises_on_missing_plugin(tmp_path, monkeypatch):
    """LookupError when plugin is not installed."""
    from zkm.scrub import run_scrub

    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(tmp_path / "plugins"))
    (tmp_path / "plugins").mkdir()

    with pytest.raises(LookupError, match="not installed"):
        run_scrub("no-such-plugin", tmp_path)


def test_run_scrub_raises_on_missing_scrub_fn(tmp_path, monkeypatch):
    """AttributeError when plugin exists but has no scrub()."""
    plugins_dir = tmp_path / "plugins"
    _make_plugin(plugins_dir, "tester", has_scrub=False)
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(plugins_dir))

    from zkm.scrub import run_scrub

    with pytest.raises(AttributeError, match="does not implement scrub"):
        run_scrub("zkm-tester", tmp_path)


def test_run_scrub_dispatches_to_plugin(tmp_path, monkeypatch):
    """run_scrub calls the plugin's scrub() and returns its stats."""
    plugins_dir = tmp_path / "plugins"
    _make_plugin(plugins_dir, "tester", has_scrub=True)
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(plugins_dir))

    from zkm.scrub import run_scrub

    stats = run_scrub("zkm-tester", tmp_path, dry_run=True)
    assert "files_scanned" in stats
    assert "files_changed" in stats
    assert "entities_removed" in stats


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def test_cmd_scrub_dry_run_output(tmp_path, monkeypatch):
    """CLI dry-run prints summary without --apply."""
    store = tmp_path / "store"
    _init_store(store)
    plugins_dir = store.parent / "plugins"
    _make_plugin(plugins_dir, "tester")
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(plugins_dir))
    monkeypatch.setenv("ZKM_STORE", str(store))

    runner = CliRunner()
    result = runner.invoke(main, ["scrub", "zkm-tester"])
    assert result.exit_code == 0
    assert "dry run" in result.output


def test_cmd_scrub_missing_plugin_exits_1(tmp_path, monkeypatch):
    """CLI exits 1 when plugin not found."""
    store = tmp_path / "store"
    _init_store(store)
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(tmp_path / "empty_plugins"))
    (tmp_path / "empty_plugins").mkdir()
    monkeypatch.setenv("ZKM_STORE", str(store))

    runner = CliRunner()
    result = runner.invoke(main, ["scrub", "no-such-plugin"])
    assert result.exit_code == 1


def test_cmd_scrub_no_scrub_fn_exits_2(tmp_path, monkeypatch):
    """CLI exits 2 when plugin has no scrub() function."""
    store = tmp_path / "store"
    _init_store(store)
    plugins_dir = tmp_path / "plugins"
    _make_plugin(plugins_dir, "tester", has_scrub=False)
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(plugins_dir))
    monkeypatch.setenv("ZKM_STORE", str(store))

    runner = CliRunner()
    result = runner.invoke(main, ["scrub", "zkm-tester"])
    assert result.exit_code == 2
