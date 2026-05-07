"""Cross-cutting hygiene helpers: plan_rm, plan_gc, apply_plan."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .sidecar import read_sidecar, rebuild_sidecar

_SIDECAR_SUFFIX = ".origin.json"


@dataclass
class SidecarUpdate:
    sidecar_path: Path
    sha256: str
    new_producers: list[dict]


@dataclass
class HygieneAction:
    """Declarative description of what rm/gc would do.

    sidecar_updates: sidecars whose producer list shrinks (but is non-empty).
    deletions:       paths to unlink (symlinks, sidecars, CAS objects, .md).
    md_path:         the managed .md being removed (None for gc orphan-only actions).
    """
    sidecar_updates: list[SidecarUpdate] = field(default_factory=list)
    deletions: list[Path] = field(default_factory=list)
    md_path: Path | None = None


def _iter_inbox_sidecars(store: Path):
    """Yield every .origin.json sidecar under <store>/inbox/."""
    inbox = store / "inbox"
    if not inbox.exists():
        return
    yield from inbox.rglob(f"*{_SIDECAR_SUFFIX}")


def _symlink_for_sidecar(sidecar_path: Path) -> Path:
    """Return the inbox symlink path for a given sidecar path."""
    name = sidecar_path.name
    assert name.endswith(_SIDECAR_SUFFIX)
    return sidecar_path.parent / name[: -len(_SIDECAR_SUFFIX)]


def _cas_object_for_symlink(link: Path) -> Path | None:
    """Resolve the symlink to the CAS object path; None if the link is broken."""
    try:
        rel = Path(os.readlink(link))
        target = (link.parent / rel).resolve()
        return target if target.exists() else None
    except OSError:
        return None


def plan_rm(store: Path, md_relpath: Path) -> HygieneAction:
    """Plan removal of the managed .md at *md_relpath* (relative to store).

    Raises FileNotFoundError if the .md does not exist.
    Raises ValueError if no sidecar references the .md (unmanaged file).
    """
    md_abs = store / md_relpath
    if not md_abs.exists():
        raise FileNotFoundError(f"{md_relpath} not found in store")

    md_rel_str = str(md_relpath)
    action = HygieneAction(md_path=md_abs)
    found = False

    for sidecar_path in _iter_inbox_sidecars(store):
        data = read_sidecar(sidecar_path)
        if data is None:
            continue
        producers = data.get("producers", [])
        matching = [p for p in producers if p.get("message") == md_rel_str]
        if not matching:
            continue

        found = True
        new_producers = [p for p in producers if p.get("message") != md_rel_str]
        link = _symlink_for_sidecar(sidecar_path)

        if new_producers:
            action.sidecar_updates.append(
                SidecarUpdate(sidecar_path, data.get("sha256", ""), new_producers)
            )
        else:
            # Last producer gone — delete link, sidecar, CAS object.
            action.deletions.append(link)
            action.deletions.append(sidecar_path)
            cas = _cas_object_for_symlink(link)
            if cas is not None:
                action.deletions.append(cas)

    if not found:
        raise ValueError(f"{md_relpath} is not managed (no sidecar references it)")

    action.deletions.append(md_abs)
    return action


def plan_gc(store: Path) -> list[HygieneAction]:
    """Plan removal of all orphaned inbox symlinks (empty/missing producers)."""
    actions: list[HygieneAction] = []

    for sidecar_path in _iter_inbox_sidecars(store):
        data = read_sidecar(sidecar_path)
        if data is None:
            continue
        if data.get("producers"):
            continue  # healthy — skip

        link = _symlink_for_sidecar(sidecar_path)
        cas = _cas_object_for_symlink(link)
        deletions: list[Path] = [link, sidecar_path]
        if cas is not None:
            deletions.append(cas)
        actions.append(HygieneAction(deletions=deletions))

    return actions


def apply_plan(action: HygieneAction) -> None:
    """Execute *action* in a safe order (rewrites before deletes, .md last)."""
    # 1. Rewrite reduced (non-empty) sidecars first.
    for upd in action.sidecar_updates:
        rebuild_sidecar(upd.sidecar_path, sha256=upd.sha256, producers=upd.new_producers)

    # 2. Deletions in the order they were queued (symlinks, sidecars, CAS objects).
    #    The .md is always last (appended last in plan_rm).
    for path in action.deletions:
        try:
            path.unlink()
        except FileNotFoundError:
            pass  # concurrent removal — tolerate


def format_plan(action: HygieneAction) -> str:
    """Return a human-readable dry-run summary of *action*."""
    lines: list[str] = []
    for upd in action.sidecar_updates:
        n = len(upd.new_producers)
        lines.append(
            f"  update sidecar ({n} producer(s) remain): {upd.sidecar_path}"
        )
    for path in action.deletions:
        lines.append(f"  delete: {path}")
    return "\n".join(lines) if lines else "  (nothing to do)"


def format_gc_plan(actions: list[HygieneAction]) -> str:
    """Return a human-readable dry-run summary of a gc plan."""
    if not actions:
        return "No orphans found."
    lines: list[str] = [f"Found {len(actions)} orphaned object(s):"]
    for a in actions:
        for path in a.deletions:
            lines.append(f"  delete: {path}")
    return "\n".join(lines)
