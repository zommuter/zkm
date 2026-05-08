"""Frontmatter amendment engine: emit, queue, and apply per-field md updates.

Contract: md *body* is single-writer; md *frontmatter* is multi-writer via
amendment records. See docs/plugin-spec.md §169–210 for full spec.

Queue layout: <store>/.zkm-state/amendments/<emitted_by>/<sha1>.json
Applied sidecar: <md-path>.amendments.json

Concurrency note: apply_queue is single-writer; two parallel apply calls are
not safe. Emit from multiple amenders to different queue subdirs is safe.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter

from .atomic import write_atomic

_SCHEMA = 1
_QUEUE_DIR = ".zkm-state/amendments"
_APPLIED_SUFFIX = ".amendments.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def emit(
    store: Path,
    *,
    key: dict,
    fields: dict,
    emitted_by: str,
    emitted_at: str | None = None,
) -> Path:
    """Write a pending amendment record to the queue. Returns the queue file path.

    Idempotent: same (key, fields, emitted_by) maps to the same SHA1 filename;
    if the file already exists it is left untouched and its path is returned.
    """
    if not key:
        raise ValueError("key must be non-empty")
    if not fields:
        raise ValueError("fields must be non-empty")
    if not emitted_by:
        raise ValueError("emitted_by must be non-empty")

    record: dict[str, Any] = {
        "schema": _SCHEMA,
        "key": key,
        "fields": fields,
        "emitted_by": emitted_by,
        "emitted_at": emitted_at or datetime.now(timezone.utc).isoformat(),
    }
    h = _record_hash(record)
    queue_dir = store / _QUEUE_DIR / emitted_by
    queue_dir.mkdir(parents=True, exist_ok=True)
    path = queue_dir / f"{h}.json"
    if path.exists():
        return path
    write_atomic(path, json.dumps(record, indent=2))
    return path


def apply_queue(store: Path) -> tuple[int, int]:
    """Apply every pending record in the queue to the md tree.

    Builds a one-shot index of {message_id: path, sha256: path} over all md
    files, then for each queue record: resolves the key, merges fields into
    frontmatter atomically, appends the record to the per-md attribution
    sidecar, and unlinks the queue file.

    Records whose key cannot be resolved are left in the queue (md not yet
    written by the source plugin). Already-applied records (detected via the
    attribution sidecar) are unlinked without re-applying.

    Returns (applied, pending).
    """
    queue_root = store / _QUEUE_DIR
    if not queue_root.exists():
        return 0, 0

    queue_files = sorted(queue_root.rglob("*.json"))
    if not queue_files:
        return 0, 0

    index = _build_md_index(store)
    applied = 0
    pending = 0

    for qf in queue_files:
        try:
            record = json.loads(qf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pending += 1
            continue

        md_path = _resolve_key(store, record.get("key", {}), index)
        if md_path is None:
            pending += 1
            continue

        if _record_hash(record) in _read_applied_hashes(md_path):
            qf.unlink(missing_ok=True)
            continue

        _apply_to_md(md_path, record)
        qf.unlink(missing_ok=True)
        applied += 1

    return applied, pending


def merge_fields(existing: dict, incoming: dict) -> dict:
    """Apply per-field merge rules; returns a new frontmatter dict.

    - 'tags':     set-union, sorted
    - 'entities': set-union with role-tagged dedup on (name, role);
                  existing entries take precedence to keep order stable
    - other:      last-write-wins (scalar overwrite)
    """
    result = dict(existing)
    for field, value in incoming.items():
        if field == "tags":
            existing_tags: list = result.get("tags") or []
            result["tags"] = sorted(set(existing_tags) | set(value or []))
        elif field == "entities":
            existing_ents: list = result.get("entities") or []
            seen = {(e["name"], e.get("role")) for e in existing_ents}
            merged = list(existing_ents)
            for ent in value or []:
                key = (ent["name"], ent.get("role"))
                if key not in seen:
                    merged.append(ent)
                    seen.add(key)
            result["entities"] = merged
        else:
            result[field] = value
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _record_hash(record: dict) -> str:
    """SHA1 of canonical JSON over (key, fields, emitted_by); stable across emitted_at."""
    payload = {k: record[k] for k in ("key", "fields", "emitted_by") if k in record}
    return hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _build_md_index(store: Path) -> dict[str, dict[str, Path]]:
    """Walk the md tree and build lookup dicts keyed by message_id and sha256."""
    index: dict[str, dict[str, Path]] = {"message_id": {}, "sha256": {}}
    for md_path in store.rglob("*.md"):
        # skip hidden dirs (.git, .zkm-state, .zkm-index, etc.)
        if any(part.startswith(".") for part in md_path.relative_to(store).parts[:-1]):
            continue
        try:
            post = frontmatter.load(md_path)
        except Exception:  # noqa: BLE001
            continue
        if mid := post.metadata.get("message_id"):
            index["message_id"][mid] = md_path
        if sha := post.metadata.get("sha256"):
            index["sha256"][sha] = md_path
    return index


def _resolve_key(store: Path, key: dict, index: dict) -> Path | None:
    """Resolve a record key to a md Path. Returns None if unresolvable."""
    if mid := key.get("message_id"):
        return index["message_id"].get(mid)
    if sha := key.get("sha256"):
        return index["sha256"].get(sha)
    if rel := key.get("path"):
        candidate = store / rel
        return candidate if candidate.exists() else None
    return None


def _read_applied_hashes(md_path: Path) -> set[str]:
    """Return the set of record hashes already applied to *md_path*."""
    sidecar = Path(str(md_path) + _APPLIED_SUFFIX)
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        return {_record_hash(r) for r in data.get("applied", [])}
    except (OSError, json.JSONDecodeError, TypeError):
        return set()


def _apply_to_md(md_path: Path, record: dict) -> None:
    """Merge *record* fields into *md_path* frontmatter and update attribution sidecar."""
    post = frontmatter.load(md_path)
    merged = merge_fields(dict(post.metadata), record["fields"])
    new_post = frontmatter.Post(post.content, **merged)
    write_atomic(md_path, frontmatter.dumps(new_post))

    sidecar = Path(str(md_path) + _APPLIED_SUFFIX)
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {"schema": _SCHEMA, "applied": []}
    data["applied"].append(record)
    write_atomic(sidecar, json.dumps(data, indent=2))
