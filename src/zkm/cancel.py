"""Cooperative cancellation for plugin runs.

Two-tier cancel via signals or ESC key:
  - 1st SIGINT/SIGTERM (or ESC in TTY) → soft cancel, plugin finishes current
    item, must yield within SOFT_DEADLINE_SECONDS (30s by default).
  - 2nd signal, or 30s timer expiry → hard cancel, KeyboardInterrupt raised
    in main thread, plugin's `finally` blocks run for atomic-write cleanup.
  - SIGKILL is OS-handled; no graceful path possible.

Plugins observe cancel via the progress callback raising PluginInterrupt.
The plugin contract is: call progress() between items; let exceptions
propagate; use try/finally for cleanup that must run on cancel.
"""

from __future__ import annotations

import _thread
import signal
import sys
import threading
import time
from collections.abc import Callable
from types import FrameType


class PluginInterrupt(KeyboardInterrupt):
    """Raised inside a plugin's progress() call when cancellation is requested.

    Subclasses KeyboardInterrupt so `except Exception` does not catch it
    (matches Python convention for user-requested termination).
    """


class CancelController:
    """Context manager that catches cancel intent and escalates after 30s.

    Usage in CLI:
        with CancelController(on_status=update_bar_description) as cancel:
            def progress_cb(current, total, message=""):
                cancel.check()  # raises PluginInterrupt on soft cancel
                # ... update bar ...
            run_plugin(progress=progress_cb)
    """

    SOFT_DEADLINE_SECONDS = 30

    def __init__(self, on_status: Callable[[str], None] | None = None) -> None:
        self._on_status = on_status or (lambda _s: None)
        self._soft = threading.Event()
        self._press_count = 0
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._countdown_thread: threading.Thread | None = None
        self._esc_thread: threading.Thread | None = None
        self._esc_stop = threading.Event()
        self._old_handlers: dict[int, object] = {}
        self._soft_at: float | None = None

    @property
    def soft_cancel_set(self) -> bool:
        return self._soft.is_set()

    def __enter__(self) -> CancelController:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._old_handlers[sig] = signal.signal(sig, self._on_signal)
            except (ValueError, OSError):
                # Not in main thread, or signal not supported
                pass
        if sys.stdin.isatty():
            self._esc_thread = threading.Thread(target=self._watch_esc, daemon=True)
            self._esc_thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._esc_stop.set()
        if self._timer is not None:
            self._timer.cancel()
        for sig, handler in self._old_handlers.items():
            try:
                signal.signal(sig, handler)  # type: ignore[arg-type]
            except (ValueError, OSError):
                pass

    def check(self) -> None:
        """Raise PluginInterrupt if a soft cancel has been requested.

        Plugins should call this via the progress callback at item boundaries.
        Hard cancel uses _thread.interrupt_main() to raise KeyboardInterrupt
        directly in the main thread, bypassing this check entirely.
        """
        if self._soft.is_set():
            raise PluginInterrupt("cancellation requested")

    # -- internal --

    def _on_signal(self, signum: int, frame: FrameType | None) -> None:
        with self._lock:
            self._press_count += 1
            if self._press_count == 1:
                self._enter_soft()
            else:
                self._enter_hard()

    def _enter_soft(self) -> None:
        if self._soft.is_set():
            return
        self._soft.set()
        self._soft_at = time.monotonic()
        self._on_status(f"cancel in {self.SOFT_DEADLINE_SECONDS}s")
        self._timer = threading.Timer(self.SOFT_DEADLINE_SECONDS, self._enter_hard)
        self._timer.daemon = True
        self._timer.start()
        self._countdown_thread = threading.Thread(target=self._countdown_loop, daemon=True)
        self._countdown_thread.start()

    def _enter_hard(self) -> None:
        self._on_status("cancelling NOW")
        if self._timer is not None:
            self._timer.cancel()
        # Raise KeyboardInterrupt in main thread; works during blocking I/O too.
        _thread.interrupt_main()

    def _countdown_loop(self) -> None:
        while not self._esc_stop.is_set():
            elapsed = time.monotonic() - (self._soft_at or 0)
            remaining = max(0, int(self.SOFT_DEADLINE_SECONDS - elapsed))
            self._on_status(f"cancel in {remaining}s")
            if remaining <= 0:
                break
            time.sleep(1)

    def _watch_esc(self) -> None:
        try:
            import select
            import termios
            import tty
        except ImportError:
            return
        try:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
        except (termios.error, ValueError, OSError):
            return
        try:
            tty.setcbreak(fd)
            while not self._esc_stop.is_set():
                r, _, _ = select.select([sys.stdin], [], [], 0.2)
                if r:
                    try:
                        ch = sys.stdin.read(1)
                    except (OSError, ValueError):
                        return
                    if ch == "\x1b":
                        with self._lock:
                            self._press_count += 1
                            if self._press_count == 1:
                                self._enter_soft()
                            else:
                                self._enter_hard()
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass
