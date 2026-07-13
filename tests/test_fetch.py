"""Tests for zkm fetch command."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from zkm.cli import main
from zkm.store import init_store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> Path:
    init_store(tmp_path, backend="none")
    return tmp_path


def _write_fetch_config(store: Path, sources: dict) -> None:
    cfg_path = store / "zkm-config.yaml"
    existing = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    existing.setdefault("core", {})["fetch"] = {"sources": sources}
    cfg_path.write_text(yaml.dump(existing, default_flow_style=False))


# ---------------------------------------------------------------------------
# --list
# ---------------------------------------------------------------------------


def test_fetch_list_no_sources(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--store", str(store), "--list"])
    assert result.exit_code == 0
    assert "No fetch sources" in result.output


def test_fetch_list_with_sources(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _write_fetch_config(store, {"myproton": {"command": "echo hi", "plugin": "vcard"}})
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--store", str(store), "--list"])
    assert result.exit_code == 0
    assert "myproton" in result.output
    assert "echo hi" in result.output
    assert "vcard" in result.output


def test_fetch_list_no_plugin_shown(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _write_fetch_config(store, {"raw": {"command": "echo raw"}})
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--store", str(store), "--list"])
    assert result.exit_code == 0
    assert "convert" not in result.output


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_fetch_no_sources_configured(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--store", str(store)])
    assert result.exit_code == 1
    assert "No fetch sources" in result.output


def test_fetch_unknown_source(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _write_fetch_config(store, {"known": {"command": "echo hi"}})
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--store", str(store), "unknown"])
    assert result.exit_code == 1
    assert "unknown source" in result.output
    assert "known" in result.output


def test_fetch_source_missing_command(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _write_fetch_config(store, {"empty": {}})
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--store", str(store)])
    assert result.exit_code == 0  # WARN but not error
    assert "WARN" in result.output
    assert "no command" in result.output


def test_fetch_command_failure(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _write_fetch_config(store, {"bad": {"command": "false"}})
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--store", str(store)])
    assert result.exit_code == 1
    assert "Error" in result.output


# ---------------------------------------------------------------------------
# Successful fetch — no plugin
# ---------------------------------------------------------------------------


def test_fetch_single_source_no_plugin(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    sentinel = tmp_path / "sentinel.txt"
    _write_fetch_config(store, {"myproton": {"command": f"touch {sentinel}"}})
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--store", str(store), "myproton"])
    assert result.exit_code == 0, result.output
    assert sentinel.exists()
    assert "Fetched 'myproton'" in result.output


def test_fetch_all_sources(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    s1 = tmp_path / "s1.txt"
    s2 = tmp_path / "s2.txt"
    _write_fetch_config(store, {
        "src1": {"command": f"touch {s1}"},
        "src2": {"command": f"touch {s2}"},
    })
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--store", str(store)])
    assert result.exit_code == 0, result.output
    assert s1.exists()
    assert s2.exists()


# ---------------------------------------------------------------------------
# Fetch with plugin auto-convert
# ---------------------------------------------------------------------------


def test_fetch_with_plugin_invokes_convert(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _write_fetch_config(store, {"src": {"command": "true", "plugin": "myplugin"}})
    runner = CliRunner()
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CompletedProcess([], returncode=0),  # fetch command
            subprocess.CompletedProcess([], returncode=0),  # convert
        ]
        result = runner.invoke(main, ["fetch", "--store", str(store), "src"])

    assert result.exit_code == 0, result.output
    assert mock_run.call_count == 2
    convert_call_args = mock_run.call_args_list[1]
    cmd_list = convert_call_args[0][0]  # positional first arg
    assert "convert" in cmd_list
    assert "myplugin" in cmd_list


def test_fetch_no_convert_flag_skips_plugin(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    sentinel = tmp_path / "fetched.txt"
    _write_fetch_config(store, {"src": {"command": f"touch {sentinel}", "plugin": "myplugin"}})
    runner = CliRunner()
    result = runner.invoke(main, ["fetch", "--store", str(store), "--no-convert", "src"])
    assert result.exit_code == 0, result.output
    assert sentinel.exists()
    assert "Skipped auto-convert" in result.output
    assert "myplugin" in result.output


def test_fetch_convert_failure_exits_nonzero(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _write_fetch_config(store, {"src": {"command": "true", "plugin": "myplugin"}})
    runner = CliRunner()
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CompletedProcess([], returncode=0),
            subprocess.CompletedProcess([], returncode=1),
        ]
        result = runner.invoke(main, ["fetch", "--store", str(store), "src"])
    assert result.exit_code == 1
    assert "WARN" in result.output
