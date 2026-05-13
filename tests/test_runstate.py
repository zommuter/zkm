"""Tests for zkm.runstate — PID-file progress tracking."""

from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

import pytest
from click.testing import CliRunner

from zkm.cli import main
from zkm.runstate import RunSession, _should_write


# ---------------------------------------------------------------------------
# _should_write helpers
# ---------------------------------------------------------------------------


def test_should_write_at_fibonacci_counts() -> None:
    assert _should_write(1)
    assert _should_write(2)
    assert _should_write(3)
    assert _should_write(5)
    assert _should_write(8)
    assert _should_write(13)


def test_should_write_not_at_non_fibonacci() -> None:
    assert not _should_write(4)
    assert not _should_write(6)
    assert not _should_write(7)
    assert not _should_write(9)
    assert not _should_write(10)
    assert not _should_write(100)


# ---------------------------------------------------------------------------
# PID file lifecycle
# ---------------------------------------------------------------------------


def test_pid_file_created_on_enter(tmp_path: Path) -> None:
    with RunSession(tmp_path, "convert", args=["eml"]) as session:
        assert session._pid_file is not None
        assert session._pid_file.exists()
        data = json.loads(session._pid_file.read_text())
        assert data["command"] == "convert"
        assert data["args"] == ["eml"]
        assert data["pid"] == os.getpid()


def test_pid_file_unlinked_on_normal_exit(tmp_path: Path) -> None:
    pid_file_path: Path | None = None
    with RunSession(tmp_path, "index") as session:
        pid_file_path = session._pid_file
        assert pid_file_path is not None
        assert pid_file_path.exists()
    assert not pid_file_path.exists()


def test_pid_file_unlinked_on_exception_exit(tmp_path: Path) -> None:
    pid_file_path: Path | None = None
    with pytest.raises(ValueError):
        with RunSession(tmp_path, "convert") as session:
            pid_file_path = session._pid_file
            assert pid_file_path is not None
            assert pid_file_path.exists()
            raise ValueError("test error")
    assert pid_file_path is not None
    assert not pid_file_path.exists()


def test_running_dir_created_automatically(tmp_path: Path) -> None:
    running_dir = tmp_path / ".zkm-state" / "running"
    assert not running_dir.exists()
    with RunSession(tmp_path, "convert"):
        assert running_dir.exists()


# ---------------------------------------------------------------------------
# Schema correctness
# ---------------------------------------------------------------------------


def test_pid_file_schema_fields(tmp_path: Path) -> None:
    with RunSession(tmp_path, "index", args=[]) as session:
        data = json.loads(session._pid_file.read_text())  # type: ignore[union-attr]
    required = {"command", "pid", "started_at", "args", "phase", "current", "total", "message", "last_updated"}
    assert required.issubset(data.keys())


# ---------------------------------------------------------------------------
# tick() — fibonacci write spacing
# ---------------------------------------------------------------------------


def test_tick_writes_at_fibonacci_counts(tmp_path: Path) -> None:
    with RunSession(tmp_path, "convert") as session:
        pid_file = session._pid_file
        assert pid_file is not None

        written_at: list[int] = []
        original_write = session._write_file

        def tracking_write() -> None:
            written_at.append(session._tick_count)
            original_write()

        session._write_file = tracking_write  # type: ignore[method-assign]

        for i in range(1, 10):
            session.tick(i, 20, phase="convert")

        # File must have been written at 1, 2, 3, 5, 8 (fibonacci counts in 1..9)
        assert 1 in written_at
        assert 2 in written_at
        assert 3 in written_at
        assert 5 in written_at
        assert 8 in written_at
        # Not at 4, 6, 7, 9
        assert 4 not in written_at
        assert 6 not in written_at
        assert 7 not in written_at
        assert 9 not in written_at


def test_tick_writes_after_60s_elapsed(tmp_path: Path) -> None:
    """A write occurs if 60s has passed since last write, even at non-fibonacci count."""
    with RunSession(tmp_path, "convert") as session:
        # Force last_write_time to 61 seconds ago.
        session._last_write_time = time.monotonic() - 61.0
        session._tick_count = 10  # non-fibonacci count

        written: list[bool] = []
        original_write = session._write_file

        def tracking_write() -> None:
            written.append(True)
            original_write()

        session._write_file = tracking_write  # type: ignore[method-assign]
        session.tick(10, 20)
        assert written  # should have written due to 60s elapsed


def test_tick_does_not_write_at_non_fibonacci_within_60s(tmp_path: Path) -> None:
    with RunSession(tmp_path, "convert") as session:
        session._last_write_time = time.monotonic()  # just wrote

        written: list[bool] = []
        original_write = session._write_file

        def tracking_write() -> None:
            written.append(True)
            original_write()

        session._write_file = tracking_write  # type: ignore[method-assign]
        session._tick_count = 3  # set to 3 so next tick will be count=4 (non-fibonacci)
        session.tick(4, 20)  # count becomes 4 — not fibonacci
        assert not written


def test_tick_updates_progress_fields(tmp_path: Path) -> None:
    with RunSession(tmp_path, "convert") as session:
        session.tick(7, 100, phase="convert", message="processing foo.md")
        assert session._current == 7
        assert session._total == 100
        assert session._phase == "convert"
        assert session._message == "processing foo.md"


def test_tick_caller_eta_overrides_fallback(tmp_path: Path) -> None:
    with RunSession(tmp_path, "convert") as session:
        session.tick(5, 100, eta_seconds=42.0)
        assert session._eta_seconds == 42.0
        data = json.loads(session._pid_file.read_text())  # type: ignore[union-attr]
        assert data["eta_seconds"] == 42.0


def test_tick_computes_fallback_eta(tmp_path: Path) -> None:
    with RunSession(tmp_path, "convert") as session:
        time.sleep(0.05)
        session.tick(1, 10)
        assert session._eta_seconds is not None
        assert session._eta_seconds > 0


def test_tick_eta_none_when_current_zero(tmp_path: Path) -> None:
    with RunSession(tmp_path, "convert") as session:
        session.tick(0, 10)
        assert session._eta_seconds is None


def test_payload_includes_eta_seconds(tmp_path: Path) -> None:
    with RunSession(tmp_path, "convert") as session:
        session.tick(3, 10, eta_seconds=15.5)
        data = json.loads(session._pid_file.read_text())  # type: ignore[union-attr]
        assert "eta_seconds" in data
        assert data["eta_seconds"] == 15.5


def test_set_phase_clears_eta(tmp_path: Path) -> None:
    with RunSession(tmp_path, "index") as session:
        session.tick(50, 100, eta_seconds=30.0)
        assert session._eta_seconds == 30.0
        session.set_phase("embed")
        assert session._eta_seconds is None


# ---------------------------------------------------------------------------
# set_phase()
# ---------------------------------------------------------------------------


def test_set_phase_resets_counters_and_writes(tmp_path: Path) -> None:
    with RunSession(tmp_path, "index") as session:
        session.tick(50, 100, phase="bm25")
        session.set_phase("embed")
        assert session._phase == "embed"
        assert session._current == 0
        assert session._total is None
        assert session._tick_count == 0
        data = json.loads(session._pid_file.read_text())  # type: ignore[union-attr]
        assert data["phase"] == "embed"


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


def test_atomic_write_uses_tmp_then_replace(tmp_path: Path) -> None:
    """Write goes via .tmp file then atomic replace — no partial JSON visible."""
    with RunSession(tmp_path, "convert") as session:
        pid_file = session._pid_file
        assert pid_file is not None
        tmp_file = pid_file.with_suffix(".tmp")
        # After enter, PID file exists and no stray .tmp
        assert pid_file.exists()
        assert not tmp_file.exists()
        # JSON must be valid
        data = json.loads(pid_file.read_text())
        assert data["pid"] == os.getpid()


# ---------------------------------------------------------------------------
# SIGUSR1 handler
# ---------------------------------------------------------------------------


def test_sigusr1_forces_write_and_stderr(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    with RunSession(tmp_path, "convert", args=["zkm-eml"]) as session:
        session.tick(5, 50, phase="convert", message="test")
        # Artificially age the last_write_time so the next tick wouldn't auto-write
        session._last_write_time = time.monotonic()
        session._tick_count = 10  # non-fibonacci

        # Send SIGUSR1 to ourselves
        os.kill(os.getpid(), signal.SIGUSR1)
        # Give the handler a moment (it runs synchronously in CPython)
        time.sleep(0.01)

        # PID file should be freshly written
        data = json.loads(session._pid_file.read_text())  # type: ignore[union-attr]
        assert data["current"] == 5
        assert data["phase"] == "convert"

    captured = capsys.readouterr()
    assert "convert" in captured.err
    assert "phase=convert" in captured.err


def test_sigusr1_includes_eta_in_stderr(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    with RunSession(tmp_path, "convert", args=["eml"]) as session:
        session.tick(5, 50, phase="convert", eta_seconds=90.0)
        session._last_write_time = time.monotonic()
        session._tick_count = 10
        os.kill(os.getpid(), signal.SIGUSR1)
        time.sleep(0.01)

    captured = capsys.readouterr()
    assert "ETA" in captured.err
    assert "1m" in captured.err  # 90s = 1m30s


def test_sigusr1_no_eta_when_unknown(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    with RunSession(tmp_path, "convert") as session:
        session.tick(0, None, phase="convert")
        session._last_write_time = time.monotonic()
        session._tick_count = 10
        os.kill(os.getpid(), signal.SIGUSR1)
        time.sleep(0.01)

    captured = capsys.readouterr()
    assert "ETA" not in captured.err


def test_sigusr1_handler_restored_on_exit(tmp_path: Path) -> None:
    old_handler = signal.getsignal(signal.SIGUSR1)
    with RunSession(tmp_path, "convert"):
        pass
    restored = signal.getsignal(signal.SIGUSR1)
    assert restored == old_handler


# ---------------------------------------------------------------------------
# zkm status --follow / --leave-if-done
# ---------------------------------------------------------------------------


def _make_pid_file(running_dir: Path, pid: int, command: str = "convert", args: list | None = None) -> Path:
    running_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "pid": pid,
        "command": command,
        "args": args or [],
        "phase": "bm25",
        "current": 5,
        "total": 100,
        "started_at": "2026-01-01T12:00:00+00:00",
        "last_updated": "2026-01-01T12:00:01+00:00",
        "message": "test",
    }
    p = running_dir / f"{pid}.json"
    p.write_text(json.dumps(data))
    return p


def test_status_no_follow_one_shot(tmp_path: Path) -> None:
    """Without --follow, status exits after a single snapshot."""
    running_dir = tmp_path / ".zkm-state" / "running"
    _make_pid_file(running_dir, os.getpid())

    # Guard: install a no-op SIGUSR1 handler so _take_status_snapshot's signal
    # doesn't terminate the test process (default action for unhandled SIGUSR1).
    old_handler = signal.signal(signal.SIGUSR1, lambda *_: None)
    try:
        runner = CliRunner()
        result = runner.invoke(main, ["status", "--store", str(tmp_path)])
    finally:
        signal.signal(signal.SIGUSR1, old_handler)

    assert result.exit_code == 0
    assert "convert" in result.output


def test_status_no_processes_no_follow(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["status", "--store", str(tmp_path)])
    assert result.exit_code == 0
    assert "no running zkm processes" in result.output


def test_status_leave_if_done_exits_immediately_when_empty(tmp_path: Path) -> None:
    """`--follow --leave-if-done` exits immediately when no processes are present."""
    runner = CliRunner()
    result = runner.invoke(main, ["status", "--follow", "--leave-if-done", "--store", str(tmp_path)])
    assert result.exit_code == 0
    assert "no running" in result.output


def test_status_leave_if_done_exits_after_process_gone(tmp_path: Path) -> None:
    """`--follow --leave-if-done` exits on the iteration where the PID file disappears."""
    running_dir = tmp_path / ".zkm-state" / "running"
    pid_file = _make_pid_file(running_dir, os.getpid())

    call_count = 0

    def _fake_snapshot(_rd: Path, send_sigusr1: bool = True) -> list[dict]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [json.loads(pid_file.read_text())]
        # Second call: file is gone
        return []

    from zkm import cli as _cli_mod
    import unittest.mock as _mock

    with _mock.patch.object(_cli_mod, "_take_status_snapshot", _fake_snapshot):
        with _mock.patch("time.sleep"):
            runner = CliRunner()
            result = runner.invoke(main, ["status", "--follow", "--leave-if-done", "--store", str(tmp_path)])
    assert result.exit_code == 0
    assert call_count == 2


def test_status_json_follow_leave_if_done(tmp_path: Path) -> None:
    """`--json --follow --leave-if-done` emits JSON and exits when empty."""
    import unittest.mock as _mock

    call_count = 0

    def _fake_snapshot(_rd: Path, send_sigusr1: bool = True) -> list[dict]:
        nonlocal call_count
        call_count += 1
        return []

    from zkm import cli as _cli_mod

    with _mock.patch.object(_cli_mod, "_take_status_snapshot", _fake_snapshot):
        with _mock.patch("time.sleep"):
            runner = CliRunner()
            result = runner.invoke(main, ["status", "--json", "--follow", "--leave-if-done", "--store", str(tmp_path)])
    assert result.exit_code == 0
    assert result.output.strip() == "[]"


def test_status_follow_does_not_send_sigusr1_in_loop(tmp_path: Path) -> None:
    """In --follow mode, SIGUSR1 is sent only on the initial snapshot, not in the poll loop."""
    import unittest.mock as _mock
    from zkm import cli as _cli_mod

    sigusr1_flags: list[bool] = []

    def _tracking_snapshot(_rd: Path, send_sigusr1: bool = True) -> list[dict]:
        sigusr1_flags.append(send_sigusr1)
        return []

    with _mock.patch.object(_cli_mod, "_take_status_snapshot", _tracking_snapshot):
        with _mock.patch("time.sleep"):
            runner = CliRunner()
            runner.invoke(main, ["status", "--follow", "--leave-if-done", "--store", str(tmp_path)])

    # First snapshot (before the loop) uses default send_sigusr1=True.
    # Loop iterations use send_sigusr1=False.
    assert len(sigusr1_flags) >= 1
    assert sigusr1_flags[0] is True
    assert all(f is False for f in sigusr1_flags[1:])


def test_status_wait_implies_follow_leave_if_done(tmp_path: Path) -> None:
    """`--wait` is a shorthand for `--follow --leave-if-done` and exits when table is empty."""
    runner = CliRunner()
    result = runner.invoke(main, ["status", "--wait", "--store", str(tmp_path)])
    assert result.exit_code == 0
    assert "no running" in result.output
