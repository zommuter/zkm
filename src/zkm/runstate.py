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

# Write at these progress counts; also write if ≥60s elapsed since last write.
_FIBONACCI: frozenset[int] = frozenset((1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610))


def _should_write(count: int) -> bool:
    return count in _FIBONACCI


class RunSession:
    """Context manager owning a PID file + SIGUSR1 handler for a command run.

    Usage::

        with RunSession(store, "convert", args=["zkm-eml"]) as session:
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
        self._last_write_time = 0.0
        self._tick_count = 0

        self._pid_file: Path | None = None
        self._old_sigusr1: Any = None

    def __enter__(self) -> RunSession:
        running_dir = self._store / ".zkm-state" / "running"
        running_dir.mkdir(parents=True, exist_ok=True)
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

        now = time.monotonic()
        if _should_write(self._tick_count) or (now - self._last_write_time >= 60.0):
            self._write_file()

    def set_phase(self, phase: str) -> None:
        """Transition to a new phase and force an immediate file write."""
        self._phase = phase
        self._current = 0
        self._total = None
        self._message = ""
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
        sys.stderr.write(
            f"{self._command} phase={self._phase} {pct} "
            f"{datetime.now(timezone.utc).strftime('%H:%M:%S')}\n"
        )
        sys.stderr.flush()
