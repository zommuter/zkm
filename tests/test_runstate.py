"""Tests for zkm.runstate — PID-file progress tracking."""

from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

import pytest

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
    with RunSession(tmp_path, "convert", args=["zkm-eml"]) as session:
        assert session._pid_file is not None
        assert session._pid_file.exists()
        data = json.loads(session._pid_file.read_text())
        assert data["command"] == "convert"
        assert data["args"] == ["zkm-eml"]
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


def test_sigusr1_handler_restored_on_exit(tmp_path: Path) -> None:
    old_handler = signal.getsignal(signal.SIGUSR1)
    with RunSession(tmp_path, "convert"):
        pass
    restored = signal.getsignal(signal.SIGUSR1)
    assert restored == old_handler
