"""PID-file progress tracking for long-running zkm commands.

RunSession writes a JSON status file to <store>/.zkm-state/running/<pid>.json
so `zkm status` can survey live processes. It installs a SIGUSR1 handler that
forces an immediate file update and emits a dd-style stderr line.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType
from typing import Any

import click

# Write at these progress counts; also write if ≥60s elapsed since last write.
_FIBONACCI: frozenset[int] = frozenset((1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610))

# Commands that must not run concurrently due to the sidecar read-modify-write race.
_MUTUAL_EXCLUSIVE: frozenset[str] = frozenset({"convert", "scrub"})

# Default path for the gamemode lock file (overridden by $ZKM_GAMEMODE_LOCK).
GAMEMODE_LOCK_DEFAULT: Path = Path("/tmp/zomni-gamemode.lock")


class ConcurrentRunError(click.ClickException):
    """Raised when a conflicting zkm process is already running (EX_TEMPFAIL)."""

    exit_code = 75


def _scan_running_dir(running_dir: Path) -> list[dict]:
    """Read live PID files from running_dir; silently drop stale ones. No SIGUSR1 sent."""
    if not running_dir.exists():
        return []
    rows: list[dict] = []
    for pid_file in sorted(running_dir.glob("*.json")):
        try:
            pid = int(pid_file.stem)
        except ValueError:
            continue
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            try:
                pid_file.unlink(missing_ok=True)
            except OSError:
                pass
            continue
        except PermissionError:
            pass  # process exists but we can't signal it — treat as live
        try:
            data = json.loads(pid_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append(data)
    return rows


def _conflicts_with(my_command: str, my_first_arg: str, row: dict) -> bool:
    """Return True if the running row conflicts with a new (my_command, my_first_arg) session."""
    other_cmd = str(row.get("command", ""))
    other_args = row.get("args") or []
    other_first = str(other_args[0]) if other_args else ""
    # Same key always conflicts.
    if my_command == other_cmd and my_first_arg == other_first:
        return True
    # Any two commands in the mutual-exclusive set conflict regardless of args,
    # because they share sidecar files that have a cross-process race.
    if my_command in _MUTUAL_EXCLUSIVE and other_cmd in _MUTUAL_EXCLUSIVE:
        return True
    return False


def _should_write(count: int) -> bool:
    return count in _FIBONACCI


class RunSession:
    """Context manager owning a PID file + SIGUSR1 handler for a command run.

    Usage::

        with RunSession(store, "convert", args=["eml"]) as session:
            for i, item in enumerate(items):
                session.tick(i + 1, len(items), phase="convert", message=item.name)
                process(item)
    """

    def __init__(
        self,
        store: Path,
        command: str,
        args: list[str] | None = None,
    ) -> None:
        self._store = store
        self._command = command
        self._args = list(args or [])
        self._pid = os.getpid()
        self._started_at = datetime.now(timezone.utc).isoformat()

        self._phase = "init"
        self._current = 0
        self._total: int | None = None
        self._message = ""
        self._eta_seconds: float | None = None
        self._phase_start_time: float = 0.0
        self._last_write_time = 0.0
        self._tick_count = 0

        self._pid_file: Path | None = None
        self._old_sigusr1: Any = None

    def __enter__(self) -> RunSession:
        self._phase_start_time = time.monotonic()
        running_dir = self._store / ".zkm-state" / "running"
        running_dir.mkdir(parents=True, exist_ok=True)

        if os.environ.get("ZKM_BYPASS_RUN_GUARD") != "1":
            lock_env = os.environ.get("ZKM_GAMEMODE_LOCK")
            lock_path = Path(lock_env) if lock_env is not None else GAMEMODE_LOCK_DEFAULT
            if lock_path.exists():
                raise ConcurrentRunError(f"gamemode lock present: {lock_path} — remove to resume")

            my_first = self._args[0] if self._args else ""
            for row in _scan_running_dir(running_dir):
                if _conflicts_with(self._command, my_first, row):
                    other_pid = row.get("pid", "?")
                    other_started = row.get("started_at", "?")
                    label = f"{self._command}({my_first})" if my_first else self._command
                    raise ConcurrentRunError(
                        f"{label} already running (pid {other_pid}, started {other_started})"
                    )

        self._pid_file = running_dir / f"{self._pid}.json"
        self._write_file()
        try:
            self._old_sigusr1 = signal.signal(signal.SIGUSR1, self._on_sigusr1)
        except (ValueError, OSError, AttributeError):
            # Not in main thread, or platform lacks SIGUSR1 (e.g. Windows).
            pass
        return self

    def __exit__(self, *exc: object) -> None:
        if self._old_sigusr1 is not None:
            try:
                signal.signal(signal.SIGUSR1, self._old_sigusr1)
            except (ValueError, OSError, AttributeError):
                pass
        if self._pid_file is not None:
            try:
                self._pid_file.unlink(missing_ok=True)
            except OSError:
                pass

    def tick(
        self,
        current: int,
        total: int | None,
        phase: str = "",
        message: str = "",
        eta_seconds: float | None = None,
    ) -> None:
        """Update progress counters; write the PID file at fibonacci-spaced intervals."""
        self._tick_count += 1
        self._current = current
        if total is not None:
            self._total = total
        if phase:
            self._phase = phase
        if message:
            self._message = message

        if eta_seconds is not None:
            self._eta_seconds = eta_seconds
        elif self._current > 0 and self._total is not None and self._total > 0:
            elapsed = time.monotonic() - self._phase_start_time
            self._eta_seconds = elapsed / self._current * (self._total - self._current)
        else:
            self._eta_seconds = None

        now = time.monotonic()
        if _should_write(self._tick_count) or (now - self._last_write_time >= 60.0):
            self._write_file()

    def set_phase(self, phase: str) -> None:
        """Transition to a new phase and force an immediate file write."""
        self._phase = phase
        self._current = 0
        self._total = None
        self._message = ""
        self._eta_seconds = None
        self._phase_start_time = time.monotonic()
        self._tick_count = 0
        self._write_file()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _payload(self) -> dict:
        return {
            "command": self._command,
            "pid": self._pid,
            "started_at": self._started_at,
            "args": self._args,
            "phase": self._phase,
            "current": self._current,
            "total": self._total,
            "message": self._message,
            "eta_seconds": self._eta_seconds,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def _write_file(self) -> None:
        if self._pid_file is None:
            return
        data = json.dumps(self._payload(), ensure_ascii=False)
        tmp = self._pid_file.with_suffix(".tmp")
        try:
            tmp.write_text(data, encoding="utf-8")
            tmp.replace(self._pid_file)
        except OSError:
            return
        self._last_write_time = time.monotonic()

    def _on_sigusr1(self, signum: int, frame: FrameType | None) -> None:
        self._write_file()
        pct = f"{self._current}/{self._total}" if self._total else str(self._current)
        eta_str = ""
        if self._eta_seconds is not None:
            mins, secs = divmod(int(self._eta_seconds), 60)
            eta_str = f" ETA ~{mins}m{secs:02d}s" if mins else f" ETA ~{secs}s"
        sys.stderr.write(
            f"{self._command} phase={self._phase} {pct} "
            f"{datetime.now(timezone.utc).astimezone().strftime('%H:%M:%S')}"
            f"{eta_str}\n"
        )
        sys.stderr.flush()
