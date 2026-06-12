"""Self-scoping under systemd-run for long-running commands (roadmap:62f3).

`zkm index` re-execs itself into a transient systemd user scope named
`zkm-index.scope` so external tooling (the zomni gamemode toggle) can
`systemctl --user freeze zkm-index.scope` / `thaw` it as one unit.

Design (see ARCHITECTURE.md §D7 and REVIEW_ME.md):

- **Loop guard**: the re-exec'd child inherits ZKM_SELF_SCOPED=1 (systemd-run
  --scope runs the command as its own child, so plain environ inheritance is
  enough — no --setenv needed).
- **Fail-open**: any precheck problem (no systemd-run on PATH, systemctl
  missing/erroring, non-systemd platforms like Termux or Raspbian-lite) means
  we simply run unscoped. Indexing must never break on account of a
  zomni-only convenience.
- **Existing scope**: if `zkm-index.scope` is already active — frozen by the
  gamemode toggle or genuinely running — starting a second one would collide
  on the unit name, so exit 75 (EX_TEMPFAIL, the repo-wide "retry later"
  convention) naming the freezer state. Joining/blocking on a frozen scope
  was rejected: a frozen parent would silently hold the caller (mbsync hook)
  for hours.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import click


class ScopeBusyError(click.ClickException):
    """The target scope unit already exists (frozen or running). EX_TEMPFAIL."""

    exit_code = 75


def _scope_state(unit: str) -> dict[str, str]:
    """Return {ActiveState, FreezerState} for *unit*.scope via systemctl --user.

    Raises on any subprocess problem — callers treat that as "no usable
    systemd user manager" and fail open.
    """
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            f"{unit}.scope",
            "--property=ActiveState,FreezerState",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    props: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            props[key.strip()] = value.strip()
    return props


def maybe_reexec_under_scope(unit: str = "zkm-index") -> None:
    """Re-exec the current command under `systemd-run --user --scope` if sensible.

    Returns without side effects (run unscoped) when:
    - ZKM_NO_SELF_SCOPE=1 (explicit opt-out; autouse in the test suite),
    - ZKM_SELF_SCOPED is set (we ARE the re-exec'd child — loop guard),
    - INVOCATION_ID is set (already started by systemd, e.g. a timer unit),
    - systemd-run is not on PATH, or
    - the scope-state precheck errors in any way (fail-open).

    Raises ScopeBusyError (exit 75) when *unit*.scope already exists.
    On success this function does NOT return — the process is replaced.
    """
    if os.environ.get("ZKM_NO_SELF_SCOPE") == "1":
        return
    if os.environ.get("ZKM_SELF_SCOPED"):
        return
    if os.environ.get("INVOCATION_ID"):
        return
    if shutil.which("systemd-run") is None:
        return

    try:
        props = _scope_state(unit)
    except Exception:  # noqa: BLE001 — deliberate fail-open, see module docstring
        return

    if props.get("ActiveState") == "active":
        state = props.get("FreezerState", "unknown")
        raise ScopeBusyError(
            f"{unit}.scope already exists (FreezerState={state}). "
            f"Retry after it finishes, or thaw it: systemctl --user thaw {unit}.scope"
        )

    os.environ["ZKM_SELF_SCOPED"] = "1"
    argv = [
        "systemd-run",
        "--user",
        "--scope",
        "--collect",
        "--quiet",
        f"--unit={unit}",
        *sys.argv,
    ]
    try:
        os.execvpe("systemd-run", argv, os.environ)
    except OSError:
        # exec failed → undo the loop guard and run unscoped (fail-open).
        os.environ.pop("ZKM_SELF_SCOPED", None)
        return
