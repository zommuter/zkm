# roadmap:62f3
"""Tests for zkm.selfscope — systemd-run self-scoping of `zkm index`.

Contract (ROADMAP id:62f3): `zkm index` re-execs itself under
`systemd-run --user --scope --collect --unit=zkm-index` so the zomni gamemode
toggle can `systemctl --user freeze zkm-index.scope`. Skip (run unscoped) when
already scoped (ZKM_SELF_SCOPED loop guard), under systemd (INVOCATION_ID),
opted out (ZKM_NO_SELF_SCOPE=1), systemd-run missing, or on ANY precheck error
(fail-open — fievel/pixel have no systemd user manager). An already-existing
zkm-index.scope (frozen or running) exits 75.

All systemd interaction is monkeypatched — no real systemctl/systemd-run calls.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click
import pytest


class ExecRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], dict]] = []

    def __call__(self, file: str, args: list[str], env: dict) -> None:
        self.calls.append((file, args, env))
        raise AssertionError("execvpe must not return — recorder should be last")


@pytest.fixture()
def no_exec(monkeypatch: pytest.MonkeyPatch) -> ExecRecorder:
    """Record exec attempts; tests assert on .calls."""
    import os

    rec = ExecRecorder()
    monkeypatch.setattr(os, "execvpe", rec)
    return rec


@pytest.fixture()
def scopeable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment where self-scoping SHOULD trigger (unless a test says otherwise)."""
    monkeypatch.delenv("ZKM_NO_SELF_SCOPE", raising=False)
    monkeypatch.delenv("ZKM_SELF_SCOPED", raising=False)
    monkeypatch.delenv("INVOCATION_ID", raising=False)
    monkeypatch.setattr(shutil, "which", lambda cmd: f"/usr/bin/{cmd}")


def _mock_systemctl(monkeypatch: pytest.MonkeyPatch, *, active: str, frozen: str = "running"):
    """systemctl --user show … returns the given ActiveState/FreezerState."""

    def fake_run(cmd, **kwargs):
        assert cmd[0] == "systemctl", cmd
        return subprocess.CompletedProcess(
            cmd, 0, stdout=f"ActiveState={active}\nFreezerState={frozen}\n", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)


# ---------------------------------------------------------------------------
# Skip conditions — run unscoped, no exec
# ---------------------------------------------------------------------------


def test_skips_when_already_self_scoped(
    scopeable, no_exec: ExecRecorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zkm.selfscope import maybe_reexec_under_scope

    monkeypatch.setenv("ZKM_SELF_SCOPED", "1")
    maybe_reexec_under_scope()
    assert no_exec.calls == []


def test_skips_under_systemd_invocation(
    scopeable, no_exec: ExecRecorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zkm.selfscope import maybe_reexec_under_scope

    monkeypatch.setenv("INVOCATION_ID", "abc123")
    maybe_reexec_under_scope()
    assert no_exec.calls == []


def test_skips_when_opted_out(
    scopeable, no_exec: ExecRecorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zkm.selfscope import maybe_reexec_under_scope

    monkeypatch.setenv("ZKM_NO_SELF_SCOPE", "1")
    maybe_reexec_under_scope()
    assert no_exec.calls == []


def test_skips_when_systemd_run_missing(
    scopeable, no_exec: ExecRecorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zkm.selfscope import maybe_reexec_under_scope

    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    maybe_reexec_under_scope()
    assert no_exec.calls == []


def test_precheck_failure_runs_unscoped(
    scopeable, no_exec: ExecRecorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail-open: a broken/absent systemd user manager must not block indexing."""
    from zkm.selfscope import maybe_reexec_under_scope

    def boom(cmd, **kwargs):
        raise FileNotFoundError("no systemctl")

    monkeypatch.setattr(subprocess, "run", boom)
    maybe_reexec_under_scope()  # must not raise
    assert no_exec.calls == []


def test_exec_failure_falls_back_unscoped(
    scopeable, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If execvpe itself fails, continue unscoped and clear the loop-guard env."""
    import os

    from zkm.selfscope import maybe_reexec_under_scope

    _mock_systemctl(monkeypatch, active="inactive")

    def fail_exec(file, args, env):
        raise OSError("exec failed")

    monkeypatch.setattr(os, "execvpe", fail_exec)
    maybe_reexec_under_scope()  # must not raise
    assert "ZKM_SELF_SCOPED" not in os.environ


# ---------------------------------------------------------------------------
# Re-exec path
# ---------------------------------------------------------------------------


def test_reexecs_with_expected_argv(
    scopeable, no_exec: ExecRecorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zkm.selfscope import maybe_reexec_under_scope

    _mock_systemctl(monkeypatch, active="inactive")

    with pytest.raises(AssertionError, match="execvpe must not return"):
        maybe_reexec_under_scope()

    assert len(no_exec.calls) == 1
    file, args, env = no_exec.calls[0]
    assert file == "systemd-run"
    head = args[: args.index(sys.argv[0])]
    assert head[0] == "systemd-run"
    assert {"--user", "--scope", "--collect"} <= set(head)
    assert "--unit=zkm-index" in head
    # Original command line is preserved verbatim after the systemd-run flags.
    assert args[args.index(sys.argv[0]):] == sys.argv
    # Loop guard travels into the scoped child.
    assert env.get("ZKM_SELF_SCOPED") == "1"


# ---------------------------------------------------------------------------
# Existing scope (frozen or running) → exit 75
# ---------------------------------------------------------------------------


def test_existing_frozen_scope_exits_75(
    scopeable, no_exec: ExecRecorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zkm.selfscope import maybe_reexec_under_scope

    _mock_systemctl(monkeypatch, active="active", frozen="frozen")

    with pytest.raises(click.ClickException) as excinfo:
        maybe_reexec_under_scope()
    assert excinfo.value.exit_code == 75
    assert "frozen" in excinfo.value.format_message()
    assert no_exec.calls == []


def test_existing_running_scope_exits_75(
    scopeable, no_exec: ExecRecorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zkm.selfscope import maybe_reexec_under_scope

    _mock_systemctl(monkeypatch, active="active", frozen="running")

    with pytest.raises(click.ClickException) as excinfo:
        maybe_reexec_under_scope()
    assert excinfo.value.exit_code == 75
    assert no_exec.calls == []


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cmd_index_calls_selfscope(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    import zkm.selfscope as selfscope
    from zkm.cli import main

    called: list[str] = []
    monkeypatch.setattr(
        selfscope, "maybe_reexec_under_scope", lambda *a, **kw: called.append("index")
    )

    runner = CliRunner()
    result = runner.invoke(main, ["index", "--store", str(store), "--no-embed"])
    assert result.exit_code == 0, result.output
    assert called == ["index"]
