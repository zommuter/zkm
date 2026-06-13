# roadmap:9878
"""Executable tests for the 5 T1 @manual BDD scenarios in features/cli-journeys.feature.

Contract: each of the 5 scenarios converted from @manual to automated has a
subprocess-style test (CliRunner or RunSession) that asserts exit code /
stdout / files against a scratch store. No new harness is needed — these are
pure CLI / file assertions.

Converted scenarios (from features/cli-journeys.feature):
  - Hybrid search degrades gracefully: Search with the embedding endpoint down
  - Concurrent and gamemode guards: Second convert while one is running (exit 75)
  - Concurrent and gamemode guards: Index refuses while gamemode lock exists
  - Amenders: No-op convert skips the amender pass
  - Store health at a glance: Doctor on a healthy configured store
"""

from __future__ import annotations

import json
import os
import textwrap
import time
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _all_output(result) -> str:
    """stdout + stderr combined, regardless of click version."""
    try:
        return result.output + result.stderr
    except (AttributeError, ValueError):
        return result.output


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make httpx refuse all connections (hermetic doctor runs)."""
    def _refuse(*args, **kwargs):
        raise httpx.ConnectError("test: no network")

    monkeypatch.setattr(httpx, "post", _refuse)
    monkeypatch.setattr(httpx, "get", _refuse, raising=False)


def _build_bm25_index(store: Path) -> None:
    """Build and save a BM25 index for the test store."""
    from zkm.index import build_index, save_index

    idx = build_index(store)
    save_index(store, idx)


def _write_plugin(pdir: Path, name: str, kind: str, convert_body: str) -> None:
    d = pdir / f"zkm-{name}"
    d.mkdir(parents=True)
    kind_line = f"kind: {kind}\n" if kind else ""
    (d / "plugin.yaml").write_text(
        f"name: {name}\nversion: 0.1.0\ndescription: test fixture\n"
        f"{kind_line}creates_dirs: [notes]\n"
    )
    (d / "convert.py").write_text(convert_body)


def _make_pid_file(
    running_dir: Path,
    pid: int,
    *,
    command: str = "convert",
    args: list[str] | None = None,
) -> Path:
    """Write a fake PID JSON file to simulate a running command.

    The file is named <pid>.json so _scan_running_dir can parse the stem as int.
    """
    running_dir.mkdir(parents=True, exist_ok=True)
    args = args or ["eml"]
    pid_file = running_dir / f"{pid}.json"
    pid_file.write_text(
        json.dumps(
            {
                "command": command,
                "args": args,
                "pid": pid,
                "started_at": "2026-01-01T00:00:00+00:00",
                "phase": "convert",
                "current": 0,
                "total": None,
                "message": "",
                "last_updated": time.time(),
            }
        )
    )
    return pid_file


# ---------------------------------------------------------------------------
# BDD scenario 1: Hybrid search degrades gracefully
# Feature: Hybrid search degrades gracefully
# Scenario: Search with the embedding endpoint down
# ---------------------------------------------------------------------------


def test_search_bm25_fallback_when_embed_endpoint_down(
    store: Path, make_note, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BDD: Given an indexed store with ZKM_EMBED_ENDPOINT pointing at a stopped server,
    When I run "zkm search invoice",
    Then I still get BM25 results, a stderr notice mentions dense index unavailable,
    and the exit code is 0.
    """
    # Arrange: add a note with 'invoice' and build the BM25 index
    make_note("notes/bill.md", "invoice for electricity 2026", "date: 2026-01-01\nsource: notes")
    _build_bm25_index(store)

    # Patch httpx so the embed client fails fast (no real network call needed)
    def _refuse(*args, **kwargs):
        raise httpx.ConnectError("test: embed endpoint refused")

    monkeypatch.setattr(httpx, "post", _refuse)

    from zkm.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["search", "invoice", "--store", str(store)])

    # Exit code must be 0 (degraded, not failed)
    assert result.exit_code == 0, f"expected exit 0, got {result.exit_code}:\n{_all_output(result)}"

    # BM25 results must still appear
    out = _all_output(result)
    assert "invoice" in out.lower() or "bill" in out.lower(), (
        f"expected BM25 result in output:\n{out}"
    )

    # Notice about dense leg being skipped must appear
    assert "dense" in out.lower() or "skip" in out.lower() or "bm25" in out.lower(), (
        f"expected notice about dense/skip in output:\n{out}"
    )


# ---------------------------------------------------------------------------
# BDD scenario 2: Concurrent lock — second convert exits 75
# Feature: Concurrent and gamemode guards
# Scenario: Second convert of the same plugin while one is running
# ---------------------------------------------------------------------------


def test_concurrent_convert_exits_75_and_names_pid(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BDD: Given "zkm convert eml" is running in terminal A,
    When I run "zkm convert eml" in terminal B,
    Then terminal B exits immediately with code 75 and the message names the running PID.

    Test strategy: install a minimal "eml" plugin so the CLI reaches RunSession;
    write a PID file for an alive "convert eml" to trigger the concurrent guard.
    """
    # Install a minimal "eml" plugin
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(pdir))
    _write_plugin(
        pdir,
        "eml",
        "",
        "def convert(store_path, config):\n    return []\n",
    )

    # Fake a running "convert eml" by writing a PID file (alive PID = current process)
    running_dir = store / ".zkm-state" / "running"
    fake_pid = os.getpid()
    _make_pid_file(running_dir, fake_pid, command="convert", args=["eml"])

    from zkm.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["convert", "eml", "--store", str(store), "--no-commit"])

    assert result.exit_code == 75, (
        f"expected exit 75, got {result.exit_code}:\n{_all_output(result)}"
    )
    # The message must name the running PID
    assert str(fake_pid) in _all_output(result), (
        f"expected PID {fake_pid} in output:\n{_all_output(result)}"
    )


# ---------------------------------------------------------------------------
# BDD scenario 3: Gamemode lock — index refuses (exit 75), names lock path
# Feature: Concurrent and gamemode guards
# Scenario: Index refuses while the gamemode lock exists
# (@roadmap-1098 — guard already implemented; @manual removed here)
# ---------------------------------------------------------------------------


def test_index_exits_75_and_names_lock_path_when_gamemode_lock_exists(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BDD: Given the file /tmp/zomni-gamemode.lock exists,
    When I run "zkm index",
    Then it exits immediately with code 75 and the message names the lock path.
    """
    # Arrange: create the gamemode lockfile in a hermetic tmp location
    lock = tmp_path / "zomni-gamemode.lock"
    lock.touch()
    monkeypatch.setenv("ZKM_GAMEMODE_LOCK", str(lock))

    from zkm.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["index", "--store", str(store), "--no-embed"])

    assert result.exit_code == 75, (
        f"expected exit 75, got {result.exit_code}:\n{_all_output(result)}"
    )
    # The message must name the lock path
    assert str(lock) in _all_output(result), (
        f"expected lock path {lock} in output:\n{_all_output(result)}"
    )


def test_doctor_reports_gamemode_lock_row_when_lock_exists(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BDD (additional assertion from the same scenario):
    "zkm doctor" shows a "gamemode lock" row with exit code unchanged.
    """
    _block_network(monkeypatch)

    from zkm.cli import main

    runner = CliRunner()

    # Baseline without lock
    baseline = runner.invoke(main, ["doctor", "--store", str(store)])
    assert "gamemode lock" not in baseline.output.lower()

    # With lock present
    lock = tmp_path / "zomni-gamemode.lock"
    lock.touch()
    monkeypatch.setenv("ZKM_GAMEMODE_LOCK", str(lock))
    result = runner.invoke(main, ["doctor", "--store", str(store)])

    assert "gamemode lock" in result.output.lower(), (
        f"expected 'gamemode lock' row in doctor output:\n{result.output}"
    )
    # Informational only — exit code must not change
    assert result.exit_code == baseline.exit_code


# ---------------------------------------------------------------------------
# BDD scenario 4: No-op amender skip
# Feature: Amenders enrich only what was just ingested
# Scenario: No-op convert skips the amender pass
# (@roadmap-dd89 — already implemented; @manual removed here)
# ---------------------------------------------------------------------------


def test_noop_convert_skips_amenders_and_prints_notice(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BDD: Given an mbsync run that delivered no new mail,
    When the post-sync hook runs "zkm convert eml",
    Then the command prints "Skipping amenders (0 files created)" and returns.
    """
    # Arrange: one primary plugin that creates zero files + one amender
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    monkeypatch.setenv("ZKM_PLUGINS_DIR", str(pdir))

    # Primary: zero-creating plugin
    _write_plugin(
        pdir,
        "noop",
        "",
        "def convert(store_path, config):\n    return []\n",
    )
    # Amender: would write a marker if called
    amender_marker = tmp_path / "amender-ran"
    _write_plugin(
        pdir,
        "amarker",
        "amender",
        textwrap.dedent(
            f"""\
            from pathlib import Path

            def convert(store_path, config, *, created=None):
                Path({str(amender_marker)!r}).write_text("ran")
                return []
            """
        ),
    )

    from zkm.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["convert", "noop", "--store", str(store), "--no-commit"])

    assert result.exit_code == 0, f"expected exit 0:\n{_all_output(result)}"
    out = _all_output(result)
    assert "Skipping amenders (0 files created)" in out, (
        f"expected skip notice in output:\n{out}"
    )
    # The amender must NOT have run
    assert not amender_marker.exists(), "amender must not run when zero files were created"


# ---------------------------------------------------------------------------
# BDD scenario 5: Doctor on a healthy configured store
# Feature: Store health at a glance
# Scenario: Doctor on a healthy configured store
# ---------------------------------------------------------------------------


def test_doctor_on_healthy_store_shows_counts_and_exits_0(
    store: Path, make_note, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BDD: Given an indexed store with endpoints responding OK,
    When I run "zkm doctor",
    Then I see md/bm25 document counts and the exit code is 0.

    Hermetic strategy: mock httpx.post to return a successful embed/chat
    response so the endpoint probes succeed without a real server.
    """
    def _mock_post(url: str, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.raise_for_status = lambda: None
        if "embeddings" in url:
            resp.json.return_value = {
                "data": [{"embedding": [0.1, 0.2, 0.3]}],
                "model": "bge-m3",
            }
        else:
            # chat completions
            resp.json.return_value = {"model": "gemma4-e4b"}
        return resp

    monkeypatch.setattr(httpx, "post", _mock_post)

    # Arrange: a store with some notes + BM25 index
    make_note("notes/alpha.md", "content about alpha", "date: 2026-01-01\nsource: notes")
    make_note("notes/beta.md", "content about beta", "date: 2026-01-02\nsource: notes")
    _build_bm25_index(store)

    from zkm.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--store", str(store)])

    assert result.exit_code == 0, (
        f"expected exit 0 for healthy store, got {result.exit_code}:\n{result.output}"
    )
    # md count row must be present (proves the store sweep ran)
    assert "md files" in result.output.lower() or "md" in result.output.lower(), (
        f"expected md count row in doctor output:\n{result.output}"
    )
    # bm25 docs row must be present
    assert "bm25" in result.output.lower(), (
        f"expected bm25 docs row in doctor output:\n{result.output}"
    )
    # The md and bm25 counts should agree (both 2 notes)
    lines = result.output.splitlines()
    md_line = next((ln for ln in lines if "md files" in ln.lower()), "")
    bm25_line = next((ln for ln in lines if "bm25" in ln.lower()), "")
    assert "2" in md_line, f"expected 2 md files:\n{md_line}"
    assert "2" in bm25_line, f"expected 2 bm25 docs:\n{bm25_line}"
