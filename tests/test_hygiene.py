"""Tests for zkm.hygiene (plan_rm, plan_gc, apply_plan) and CLI cmd_rm/cmd_gc."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from zkm.cas import write_object
from zkm.cli import main
from zkm.hygiene import (
    HygieneAction,
    apply_plan,
    format_gc_plan,
    format_plan,
    plan_gc,
    plan_rm,
)
from zkm.inbox import symlink_with_sidecar
from zkm.sidecar import read_sidecar

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git(path: Path) -> None:
    for cmd in [
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@test"],
        ["git", "config", "user.name", "T"],
        ["git", "commit", "--allow-empty", "-m", "init", "-q"],
    ]:
        subprocess.run(cmd, cwd=path, check=True, capture_output=True)


def _producer(sha: str, message: str, plugin: str = "testplugin") -> dict:
    return {"plugin": plugin, "message": message, "sha256": sha}


def _make_managed_md(store: Path, content: bytes, message: str, plugin: str = "testplugin"):
    """Write a CAS object, create inbox symlink+sidecar, and write the .md file.

    Returns (cas_path, link_path, sidecar_path, md_abs).
    """
    subdir = message.split("/")[0]  # e.g. "mail" from "mail/messages/..."
    cas = write_object(store, subdir, content)
    sha = cas.parts[-2] + cas.parts[-1]

    link_dir = store / "inbox" / subdir / "2026" / "05"
    link_dir.mkdir(parents=True, exist_ok=True)
    canonical: dict = {}
    link = symlink_with_sidecar(
        cas_object=cas,
        link_dir=link_dir,
        link_name="file.bin",
        producer=_producer(sha, message, plugin),
        canonical_index=canonical,
    )
    sidecar = link.parent / (link.name + ".origin.json")

    md_abs = store / message
    md_abs.parent.mkdir(parents=True, exist_ok=True)
    md_abs.write_text("# note\n", encoding="utf-8")

    return cas, link, sidecar, md_abs


# ---------------------------------------------------------------------------
# plan_rm tests
# ---------------------------------------------------------------------------


def test_rm_dry_run_lists_actions_no_changes(tmp_path):
    store = tmp_path
    message = "mail/messages/2026/05/note.md"
    cas, link, sidecar, md_abs = _make_managed_md(store, b"hello", message)

    action = plan_rm(store, Path(message))

    # plan only — nothing deleted yet
    assert md_abs.exists()
    assert link.is_symlink()
    assert sidecar.exists()
    assert cas.exists()

    # action queues link, sidecar, cas, md deletions (last producer gone)
    assert md_abs in action.deletions
    assert link in action.deletions
    assert sidecar in action.deletions
    assert cas in action.deletions
    assert action.sidecar_updates == []


def test_rm_apply_removes_symlink_sidecar_cas_and_md(tmp_path):
    store = tmp_path
    message = "mail/messages/2026/05/note.md"
    cas, link, sidecar, md_abs = _make_managed_md(store, b"data", message)

    action = plan_rm(store, Path(message))
    apply_plan(action)

    assert not md_abs.exists()
    assert not link.exists()
    assert not sidecar.exists()
    assert not cas.exists()


def test_rm_keeps_cas_when_other_producers_remain(tmp_path):
    """Two producers share the same CAS object; removing one .md keeps the other."""
    store = tmp_path
    # Both .md files share the same raw bytes → same CAS sha
    content = b"shared attachment"
    subdir = "mail"
    cas = write_object(store, subdir, content)

    link_dir = store / "inbox" / subdir / "2026" / "05"
    link_dir.mkdir(parents=True, exist_ok=True)
    canonical: dict = {}

    message1 = "mail/messages/2026/05/a.md"
    message2 = "mail/messages/2026/05/b.md"

    # Producer sha256 is the *source* sha (e.g. the .eml hash), not the CAS sha.
    # Two sources can produce the same attachment (same CAS) but have distinct
    # producer sha values so both are recorded in the sidecar.
    src_sha1 = "a" * 64
    src_sha2 = "b" * 64

    link = symlink_with_sidecar(
        cas_object=cas,
        link_dir=link_dir,
        link_name="file.bin",
        producer={"plugin": "testplugin", "message": message1, "sha256": src_sha1},
        canonical_index=canonical,
    )
    symlink_with_sidecar(
        cas_object=cas,
        link_dir=link_dir,
        link_name="file.bin",
        producer={"plugin": "testplugin", "message": message2, "sha256": src_sha2},
        canonical_index=canonical,
    )

    for msg in (message1, message2):
        md = store / msg
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("# md\n", encoding="utf-8")

    # Remove only message1
    action = plan_rm(store, Path(message1))
    # Should be a sidecar *update* (not a deletion), since message2 still remains
    assert len(action.sidecar_updates) == 1
    assert action.sidecar_updates[0].new_producers[0]["message"] == message2

    apply_plan(action)

    # CAS and symlink survive; only message1's .md is gone
    assert cas.exists()
    assert link.is_symlink()
    assert not (store / message1).exists()
    assert (store / message2).exists()

    # Sidecar now has only one producer
    data = read_sidecar(link.parent / (link.name + ".origin.json"))
    assert data is not None
    assert len(data["producers"]) == 1
    assert data["producers"][0]["message"] == message2


def test_rm_unmanaged_md_errors(tmp_path):
    store = tmp_path
    md = store / "notes" / "manual.md"
    md.parent.mkdir(parents=True)
    md.write_text("# manual\n")

    with pytest.raises(ValueError, match="not managed"):
        plan_rm(store, Path("notes/manual.md"))


def test_rm_nonexistent_md_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        plan_rm(tmp_path, Path("nonexistent.md"))


def test_rm_rejects_path_outside_store(tmp_path):
    from zkm.cli import _normalise_relpath

    with pytest.raises(ValueError, match="outside the store"):
        _normalise_relpath(tmp_path, "/etc/passwd")


# ---------------------------------------------------------------------------
# plan_gc tests
# ---------------------------------------------------------------------------


def test_gc_finds_orphan_sidecar(tmp_path):
    store = tmp_path
    message = "mail/messages/2026/05/orphan.md"
    cas, link, sidecar, _md = _make_managed_md(store, b"orphan", message)

    # Simulate an orphaned state: manually zero out the producers list
    import json

    data = json.loads(sidecar.read_text())
    data["producers"] = []
    sidecar.write_text(json.dumps(data))

    actions = plan_gc(store)
    assert len(actions) == 1
    assert link in actions[0].deletions
    assert sidecar in actions[0].deletions
    assert cas in actions[0].deletions

    apply_plan(actions[0])

    assert not link.exists()
    assert not sidecar.exists()
    assert not cas.exists()


def test_gc_ignores_healthy_sidecar(tmp_path):
    store = tmp_path
    message = "mail/messages/2026/05/healthy.md"
    _make_managed_md(store, b"healthy", message)

    actions = plan_gc(store)
    assert actions == []


def test_gc_empty_store_no_inbox(tmp_path):
    actions = plan_gc(tmp_path)
    assert actions == []


# ---------------------------------------------------------------------------
# format helpers
# ---------------------------------------------------------------------------


def test_format_plan_deletions(tmp_path):
    action = HygieneAction(deletions=[tmp_path / "foo.md"])
    out = format_plan(action)
    assert "delete:" in out
    assert "foo.md" in out


def test_format_plan_nothing():
    action = HygieneAction()
    assert "(nothing to do)" in format_plan(action)


def test_format_gc_plan_empty():
    assert "No orphans" in format_gc_plan([])


def test_format_gc_plan_with_action(tmp_path):
    action = HygieneAction(deletions=[tmp_path / "x"])
    out = format_gc_plan([action])
    assert "1 orphaned" in out


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


def _init_store(path: Path) -> None:
    """Minimal git-initialized store (no .zkm-config needed for rm/gc)."""
    _init_git(path)


def test_cli_rm_dry_run(tmp_path):
    _init_store(tmp_path)
    message = "mail/messages/2026/05/note.md"
    _make_managed_md(tmp_path, b"data", message)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["rm", str(tmp_path / message), "--store", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "delete:" in result.output
    assert "Dry run" in result.output
    # file still exists
    assert (tmp_path / message).exists()


def test_cli_rm_apply(tmp_path):
    _init_store(tmp_path)
    message = "mail/messages/2026/05/note.md"
    cas, _link, _sidecar, md_abs = _make_managed_md(tmp_path, b"data", message)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["rm", str(md_abs), "--store", str(tmp_path), "--apply", "--no-commit"],
    )
    assert result.exit_code == 0, result.output
    assert "Applied." in result.output
    assert not md_abs.exists()
    assert not cas.exists()


def test_cli_rm_apply_auto_commits(tmp_path):
    _init_store(tmp_path)
    message = "mail/messages/2026/05/note.md"
    _cas, _link, _sidecar, md_abs = _make_managed_md(tmp_path, b"data", message)

    # Stage the managed files so they're tracked
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add managed file", "-q"], cwd=tmp_path, check=True
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["rm", str(md_abs), "--store", str(tmp_path), "--apply"],
    )
    assert result.exit_code == 0, result.output
    assert "Committed:" in result.output

    log = subprocess.run(
        ["git", "log", "--oneline", "-1"], cwd=tmp_path, capture_output=True, text=True
    )
    assert "rm" in log.stdout


def test_cli_rm_apply_no_commit_skips_commit(tmp_path):
    _init_store(tmp_path)
    message = "mail/messages/2026/05/note.md"
    _cas, _link, _sidecar, md_abs = _make_managed_md(tmp_path, b"data", message)

    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "add managed file", "-q"], cwd=tmp_path, check=True
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["rm", str(md_abs), "--store", str(tmp_path), "--apply", "--no-commit"],
    )
    assert result.exit_code == 0, result.output
    assert "Committed:" not in result.output

    log = subprocess.run(
        ["git", "log", "--oneline", "-1"], cwd=tmp_path, capture_output=True, text=True
    )
    # Most recent commit should still be the "add" one, not an rm commit
    assert "add managed file" in log.stdout


def test_cli_gc_dry_run(tmp_path):
    import json

    _init_store(tmp_path)
    message = "mail/messages/2026/05/orphan.md"
    cas, link, sidecar, md_abs = _make_managed_md(tmp_path, b"orphan", message)

    data = json.loads(sidecar.read_text())
    data["producers"] = []
    sidecar.write_text(json.dumps(data))

    runner = CliRunner()
    result = runner.invoke(main, ["gc", "--store", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "orphaned" in result.output
    assert "Dry run" in result.output
    assert cas.exists()  # not deleted yet


def test_cli_gc_apply(tmp_path):
    import json

    _init_store(tmp_path)
    message = "mail/messages/2026/05/orphan.md"
    cas, link, sidecar, md_abs = _make_managed_md(tmp_path, b"orphan", message)

    data = json.loads(sidecar.read_text())
    data["producers"] = []
    sidecar.write_text(json.dumps(data))

    runner = CliRunner()
    result = runner.invoke(main, ["gc", "--store", str(tmp_path), "--apply", "--no-commit"])
    assert result.exit_code == 0, result.output
    assert "Applied." in result.output
    assert not cas.exists()
    assert not sidecar.exists()


def test_cli_gc_clean_store(tmp_path):
    _init_store(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["gc", "--store", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "No orphans" in result.output
