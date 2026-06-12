# roadmap:1098
"""Spec tests for the gamemode lockfile guard (ROADMAP id:1098, currently RED).

Contract: when the lock file exists (path from $ZKM_GAMEMODE_LOCK, default
/tmp/zomni-gamemode.lock via zkm.runstate.GAMEMODE_LOCK_DEFAULT), entering a
RunSession for convert/scrub/index refuses with exit code 75 (EX_TEMPFAIL)
before writing any PID file. ZKM_BYPASS_RUN_GUARD=1 bypasses this guard too.
`zkm doctor` reports the lock informationally.

Tests marked GUARD pass pre-implementation; they pin behaviour that the green
implementation must not break. All others are the RED spec.
"""

from __future__ import annotations

from pathlib import Path

import click
import pytest
from click.testing import CliRunner


def _make_lock(tmp_path: Path) -> Path:
    lock = tmp_path / "zomni-gamemode.lock"
    lock.touch()
    return lock


# ---------------------------------------------------------------------------
# RunSession-level guard
# ---------------------------------------------------------------------------


def test_default_lock_path_constant() -> None:
    """The default lock path is a module-level constant (env var overrides it)."""
    from zkm import runstate

    assert getattr(runstate, "GAMEMODE_LOCK_DEFAULT", None) == Path(
        "/tmp/zomni-gamemode.lock"
    )


def test_runsession_refuses_when_gamemode_lock_present(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zkm.runstate import RunSession

    lock = _make_lock(tmp_path)
    monkeypatch.setenv("ZKM_GAMEMODE_LOCK", str(lock))

    with pytest.raises(click.ClickException) as excinfo:
        with RunSession(store, "index"):
            pass
    assert excinfo.value.exit_code == 75
    # The message must name the lock path so the user knows what to remove.
    assert str(lock) in excinfo.value.format_message()


def test_refusal_exits_75_and_writes_no_pid_file(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard fires BEFORE the PID file is written (no stale artefacts)."""
    from zkm.runstate import RunSession

    lock = _make_lock(tmp_path)
    monkeypatch.setenv("ZKM_GAMEMODE_LOCK", str(lock))

    with pytest.raises(click.ClickException):
        with RunSession(store, "convert", args=["eml"]):
            pass
    running_dir = store / ".zkm-state" / "running"
    assert not list(running_dir.glob("*.json")) if running_dir.exists() else True


def test_default_used_when_env_unset(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With $ZKM_GAMEMODE_LOCK unset, the guard checks GAMEMODE_LOCK_DEFAULT."""
    from zkm import runstate

    lock = _make_lock(tmp_path)
    monkeypatch.delenv("ZKM_GAMEMODE_LOCK", raising=False)
    monkeypatch.setattr(runstate, "GAMEMODE_LOCK_DEFAULT", lock, raising=False)

    with pytest.raises(click.ClickException) as excinfo:
        with runstate.RunSession(store, "scrub", args=["ner"]):
            pass
    assert excinfo.value.exit_code == 75


def test_env_var_overrides_default_lock_path(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUARD: env var pointing at a nonexistent path wins over an existing default."""
    from zkm import runstate

    lock = _make_lock(tmp_path)
    monkeypatch.setattr(runstate, "GAMEMODE_LOCK_DEFAULT", lock, raising=False)
    monkeypatch.setenv("ZKM_GAMEMODE_LOCK", str(tmp_path / "absent.lock"))

    with runstate.RunSession(store, "index"):
        pass  # must not raise


def test_bypass_run_guard_also_bypasses_gamemode_lock(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUARD (judgment call, see REVIEW_ME.md): one bypass env var for both guards."""
    from zkm.runstate import RunSession

    lock = _make_lock(tmp_path)
    monkeypatch.setenv("ZKM_GAMEMODE_LOCK", str(lock))
    monkeypatch.setenv("ZKM_BYPASS_RUN_GUARD", "1")

    with RunSession(store, "index"):
        pass  # must not raise


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_index_exits_75_when_lock_present(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from zkm.cli import main

    lock = _make_lock(tmp_path)
    monkeypatch.setenv("ZKM_GAMEMODE_LOCK", str(lock))

    runner = CliRunner()
    result = runner.invoke(main, ["index", "--store", str(store), "--no-embed"])
    assert result.exit_code == 75


def test_doctor_reports_gamemode_lock(
    store: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Doctor shows a 'gamemode lock' row informationally, without flipping
    its exit code (hermetic: endpoint probes are forced to fail either way)."""
    import httpx

    from zkm.cli import main

    def _refuse(*args, **kwargs):
        raise httpx.ConnectError("test: no network")

    monkeypatch.setattr(httpx, "post", _refuse)
    monkeypatch.setattr(httpx, "get", _refuse, raising=False)

    runner = CliRunner()

    baseline = runner.invoke(main, ["doctor", "--store", str(store)])
    assert "gamemode lock" not in baseline.output.lower()

    lock = _make_lock(tmp_path)
    monkeypatch.setenv("ZKM_GAMEMODE_LOCK", str(lock))
    result = runner.invoke(main, ["doctor", "--store", str(store)])
    assert "gamemode lock" in result.output.lower()
    # Informational only: the lock must not change doctor's exit code.
    assert result.exit_code == baseline.exit_code
