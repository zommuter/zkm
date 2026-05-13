"""Dirty-tree guard for state-modifying commands.

Prevents editable installs from running WIP code against the live store.
Bypass: ZKM_BYPASS_DIRTY_CHECK=1
Non-editable installs (no .git/ ancestor of zkm.__file__) are always allowed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import click

_DIRTY_HINT = (
    "Options:\n"
    "  • Commit the changes, then re-run.\n"
    "  • ZKM_BYPASS_DIRTY_CHECK=1  — runs with your WIP code as-is.\n"
    "  • git stash  — ONLY to revert to HEAD; your WIP will NOT run."
)

_STASH_WARNING = (
    "Note: {ref} in {root} contains source changes.\n"
    "Running with committed HEAD code; your stashed WIP is not active.\n"
    "Set ZKM_BYPASS_DIRTY_CHECK=1 to silence this when intentional."
)


def find_repo_root(start: Path) -> Path | None:
    """Walk up from *start* to find the nearest .git/ directory. Return root or None."""
    for candidate in [start, *start.parents]:
        if (candidate / ".git").is_dir():
            return candidate
    return None


def is_dirty(repo_root: Path) -> tuple[bool, str]:
    """Return (dirty, summary) for the git repo at *repo_root*.

    Checks only tracked-file modifications (untracked files and unpushed commits
    do not count). Summary is populated only when dirty.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "diff-index", "--quiet", "HEAD", "--"],
        capture_output=True,
    )
    if result.returncode == 0:
        return False, ""
    status = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--short"],
        capture_output=True,
        text=True,
    )
    return True, status.stdout.strip()


def _stash_touches_scope(repo_root: Path) -> str | None:
    """Return the first stash ref in *repo_root* that modifies any tracked file.

    Returns None when no stash exists or all git calls fail (advisory only).
    """
    try:
        pre = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", "refs/stash"],
            capture_output=True,
        )
        if pre.returncode != 0:
            return None
        refs_result = subprocess.run(
            ["git", "-C", str(repo_root), "stash", "list", "--format=%gd"],
            capture_output=True,
            text=True,
        )
        if refs_result.returncode != 0:
            return None
        for ref in refs_result.stdout.strip().splitlines():
            ref = ref.strip()
            if not ref:
                continue
            show = subprocess.run(
                ["git", "-C", str(repo_root), "stash", "show", "--name-only", ref],
                capture_output=True,
                text=True,
            )
            if show.returncode == 0 and show.stdout.strip():
                return ref
    except Exception:  # noqa: BLE001
        pass
    return None


def _zkm_module_path() -> Path:
    import zkm
    return Path(zkm.__file__).resolve()


def assert_clean(plugin_name: str | None = None) -> None:
    """Raise ClickException if the source tree has uncommitted tracked changes.

    Checks src/zkm/ always. If *plugin_name* is given, also checks that plugin's
    own git repo (plugins are independent repos; editing zkm-pdf does not gate
    a zkm-eml convert).

    When the tree is clean but a stash exists containing source changes, emits a
    stderr warning so the user knows their WIP is not active.
    """
    if os.environ.get("ZKM_BYPASS_DIRTY_CHECK"):
        return

    core_root = find_repo_root(_zkm_module_path().parent)
    if core_root is None:
        return  # non-editable install — no .git/ ancestor, binary is frozen

    dirty, summary = is_dirty(core_root)
    if dirty:
        raise click.ClickException(
            f"zkm core has uncommitted changes at {core_root}:\n"
            f"{summary}\n\n{_DIRTY_HINT}"
        )
    else:
        stash_ref = _stash_touches_scope(core_root)
        if stash_ref is not None:
            click.echo(_STASH_WARNING.format(ref=stash_ref, root=core_root), err=True)

    if plugin_name is not None:
        from zkm.convert import find_plugin
        plugin = find_plugin(plugin_name)
        if plugin is None:
            return  # unknown plugin — convert will error clearly later
        plugin_root = find_repo_root(plugin.path)
        if plugin_root is None:
            return  # plugin not under a git repo (e.g. plain symlink) — no-op
        dirty, summary = is_dirty(plugin_root)
        if dirty:
            raise click.ClickException(
                f"plugin '{plugin_name}' has uncommitted changes at {plugin_root}:\n"
                f"{summary}\n\n{_DIRTY_HINT}"
            )
        else:
            stash_ref = _stash_touches_scope(plugin_root)
            if stash_ref is not None:
                click.echo(_STASH_WARNING.format(ref=stash_ref, root=plugin_root), err=True)
