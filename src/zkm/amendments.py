"""Frontmatter amendment engine: emit, queue, and apply per-field md updates.

Contract: md *body* is single-writer; md *frontmatter* is multi-writer via
amendment records. See docs/plugin-spec.md §169–210 for full spec.

Queue layout: <store>/.zkm-state/amendments/<emitted_by>/<sha1>.json
Applied sidecar: <md-path>.amendments.json

Two emit modes:
  - `emit`     — additive (set-union) merge; legacy path, byte-identical.
  - `emit_set` — DECLARATIVE: the record carries a producer's FULL current
                 asserted set for a key. On apply, core stores each producer's
                 last set per md-key in the attribution sidecar (`producer_sets`)
                 and computes REMOVALS by diffing prior-vs-new. A value is dropped
                 from frontmatter iff it ref-counts to zero across all producers'
                 current sets (D2). Additions are still set-union — the declarative
                 model strictly ADDS removal computation, it does not change the
                 addition semantics. See
                 docs/meeting-notes/2026-06-18-1944-f103-tag-removal-core-semantic.md.

Concurrency note: apply_queue is single-writer; two parallel apply calls are
not safe. Emit from multiple amenders to different queue subdirs is safe. The
per-md attribution sidecar read-modify-write is fcntl-locked (closes the
2026-05-14 _apply_to_md race).
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import frontmatter

from .atomic import write_atomic

# schema 2 adds the `producer_sets` block to the attribution sidecar (declarative
# emit_set bookkeeping). Schema-1 sidecars are read gracefully (D4d): a producer's
# stored set is bootstrapped from the union of its prior applied `fields`.
_SCHEMA = 2
_QUEUE_DIR = ".zkm-state/amendments"
_APPLIED_SUFFIX = ".amendments.json"

# Fields that carry a producer-asserted *set* (declarative retraction applies to
# these). Other fields are scalar last-write-wins and are never retracted.
# - "tags":     set of strings — hashable, sorted list in JSON storage.
# - "entities": set of {scope, type, value} dicts — NOT directly hashable; keyed
#               internally by (scope, type, value) tuple (same dedup key as
#               merge_fields uses). JSON storage: list of dicts sorted by tuple key.
_SET_FIELDS = ("tags", "entities")


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
    """Write a pending ADDITIVE amendment record to the queue.

    Idempotent: same (mode, key, fields, emitted_by) maps to the same SHA1
    filename; if the file already exists it is left untouched and its path is
    returned. Additive records merge their fields set-union (legacy semantics).
    """
    return _emit(store, key=key, fields=fields, emitted_by=emitted_by,
                 emitted_at=emitted_at, mode="additive")


def emit_set(
    store: Path,
    *,
    key: dict,
    fields: dict,
    emitted_by: str,
    emitted_at: str | None = None,
) -> Path:
    """Write a pending DECLARATIVE amendment record (full asserted set, D1).

    *fields* declares the producer's COMPLETE current asserted set for the key
    (e.g. ``{"tags": ["a", "b"]}`` means this producer now asserts exactly a, b).
    On apply, removals are computed by diffing the producer's stored set against
    this new set; a value ref-counting to zero across all producers is dropped
    from frontmatter (D2). An empty set for a key retracts only this producer's
    own claims and is never a bulk-retract (D4a). Diff is scoped to keys reported
    in the current run (D4b). Idempotent like ``emit``.

    Unlike ``emit``, ``emit_set`` accepts an empty *fields* mapping value (an
    empty asserted set is a legitimate full-retraction-of-own-claims signal); the
    *fields* dict itself must still be present (declares which field is a set).
    """
    return _emit(store, key=key, fields=fields, emitted_by=emitted_by,
                 emitted_at=emitted_at, mode="set")


def _emit(
    store: Path,
    *,
    key: dict,
    fields: dict,
    emitted_by: str,
    emitted_at: str | None,
    mode: str,
) -> Path:
    if not key:
        raise ValueError("key must be non-empty")
    if fields is None:
        raise ValueError("fields must be present")
    # Additive emit requires non-empty fields (nothing to add otherwise); a
    # declarative set may legitimately assert an empty set (full self-retraction).
    if mode == "additive" and not fields:
        raise ValueError("fields must be non-empty")
    if not emitted_by:
        raise ValueError("emitted_by must be non-empty")

    record: dict[str, Any] = {
        "schema": _SCHEMA,
        "mode": mode,
        "key": key,
        "fields": fields,
        "emitted_by": emitted_by,
        "emitted_at": emitted_at or datetime.now(UTC).isoformat(),
    }
    h = _record_hash(record)
    queue_dir = store / _QUEUE_DIR / emitted_by
    queue_dir.mkdir(parents=True, exist_ok=True)
    path = queue_dir / f"{h}.json"
    if path.exists():
        return path
    write_atomic(path, json.dumps(record, indent=2))
    return path


def apply_queue(store: Path, *, dry_run: bool = False) -> tuple[int, int]:
    """Apply every pending record in the queue to the md tree.

    Builds a one-shot index of {message_id: path, sha256: path} over all md
    files, then for each queue record: resolves the key, merges fields into
    frontmatter atomically, appends the record to the per-md attribution
    sidecar, and unlinks the queue file.

    Records whose key cannot be resolved are left in the queue (md not yet
    written by the source plugin). Already-applied records (detected via the
    attribution sidecar) are unlinked without re-applying.

    ``dry_run`` (D3): compute and return planned changes WITHOUT touching any md,
    sidecar, or queue file. Pending retractions are emitted via
    ``plan_retractions`` instead — use that for a structured preview.

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
            if not dry_run:
                qf.unlink(missing_ok=True)
            continue

        if dry_run:
            applied += 1
            continue

        _apply_to_md(md_path, record)
        qf.unlink(missing_ok=True)
        applied += 1

    return applied, pending


def plan_retractions(store: Path) -> list[dict]:
    """Return a non-mandatory dry-run preview of pending tag retractions (D3).

    Each entry: ``{"md": <str path>, "field": <str>, "value": <str>,
    "producer": <emitted_by>}`` for every value a queued ``set`` record would
    drop from frontmatter (i.e. removed from the producer's set AND ref-counting
    to zero across all producers' current sets). Reads only; mutates nothing.
    Free under the declarative model — the diff is computed before apply anyway.
    """
    queue_root = store / _QUEUE_DIR
    if not queue_root.exists():
        return []
    index = _build_md_index(store)
    plan: list[dict] = []
    for qf in sorted(queue_root.rglob("*.json")):
        try:
            record = json.loads(qf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("mode") != "set":
            continue
        md_path = _resolve_key(store, record.get("key", {}), index)
        if md_path is None:
            continue
        if _record_hash(record) in _read_applied_hashes(md_path):
            continue
        data = _read_sidecar_data(md_path)
        producer = record["emitted_by"]
        for field in _SET_FIELDS:
            removable = _retractable_values(data, producer, field, record["fields"])
            for value in sorted(removable):
                plan.append({"md": str(md_path), "field": field,
                             "value": value, "producer": producer})
    return plan


def merge_fields(existing: dict, incoming: dict) -> dict:
    """Apply per-field merge rules; returns a new frontmatter dict.

    - 'tags':     set-union, sorted
    - 'entities': set-union with dedup on (scope, type, value);
                  missing scope treated as 'body' (graceful read for pre-γ entries);
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
            seen = {(_ent_scope(e), e["type"], e["value"]) for e in existing_ents}
            merged = list(existing_ents)
            for ent in value or []:
                key = (_ent_scope(ent), ent["type"], ent["value"])
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


def _ent_scope(ent: dict) -> str:
    """Return the scope of an entity record, defaulting to 'body' for pre-γ entries."""
    return ent.get("scope", "body")


def _field_value_key(field: str, value: Any) -> Any:
    """Return the canonical hashable key for a field value.

    - "tags":     the string itself.
    - "entities": (scope, type, value) tuple — same dedup key as ``merge_fields``.
    """
    if field == "entities":
        return (_ent_scope(value), value["type"], value["value"])
    return value


def _field_keys_from_list(field: str, values: list) -> set:
    """Convert a stored list of field values to a set of hashable keys."""
    return {_field_value_key(field, v) for v in (values or [])}


def _field_to_stored_list(field: str, values: list) -> list:
    """Convert a list of field values to a JSON-safe sorted list for ``producer_sets``.

    - "tags":     sorted list of strings (existing behaviour).
    - "entities": list of dicts, sorted by (scope, type, value) tuple key, deduplicated.
    """
    if field == "entities":
        seen: set = set()
        result = []
        for v in (values or []):
            k = _field_value_key("entities", v)
            if k not in seen:
                seen.add(k)
                result.append(v)
        result.sort(key=lambda e: (_ent_scope(e), e["type"], e["value"]))
        return result
    return sorted(set(values or []))


def _record_hash(record: dict) -> str:
    """SHA1 of canonical JSON over (key, fields, emitted_by[, mode]); stable across emitted_at.

    Backward-compat: an additive record (mode missing or == "additive") hashes
    EXACTLY as a schema-1 record did — `mode` is folded into the payload only for
    declarative ``set`` records, so already-applied legacy additive records stay
    idempotent across the schema bump.
    """
    payload = {k: record[k] for k in ("key", "fields", "emitted_by") if k in record}
    if record.get("mode") == "set":
        payload["mode"] = "set"
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


@contextlib.contextmanager
def _sidecar_lock(md_path: Path) -> Generator[None, None, None]:
    """Exclusive fcntl lock serialising read-modify-write of *md_path*'s sidecar.

    Mirrors ``sidecar.py:_sidecar_lock`` — closes the 2026-05-14 race where two
    parallel ``_apply_to_md`` calls could lose one writer's attribution record.
    """
    lock_path = md_path.parent / (md_path.name + _APPLIED_SUFFIX + ".lock")
    with open(lock_path, "a") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


def _read_sidecar_data(md_path: Path) -> dict:
    """Return the parsed attribution sidecar dict, or a fresh schema-2 skeleton.

    Graceful read (D4d): a schema-1 sidecar has no ``producer_sets`` block; it is
    returned as-is and ``_producer_stored_set`` bootstraps each producer's set
    from the union of its prior applied ``fields`` — no on-disk migration.
    """
    sidecar = Path(str(md_path) + _APPLIED_SUFFIX)
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"schema": _SCHEMA, "applied": []}


def _read_applied_hashes(md_path: Path) -> set[str]:
    """Return the set of record hashes already applied to *md_path*."""
    data = _read_sidecar_data(md_path)
    try:
        return {_record_hash(r) for r in data.get("applied", [])}
    except (AttributeError, TypeError):
        return set()


def _producer_stored_set(data: dict, producer: str, field: str) -> set:
    """Return *producer*'s last-asserted set for *field* as a set of hashable keys.

    For "tags" the keys are the tag strings themselves. For "entities" the keys are
    (scope, type, value) tuples (see ``_field_value_key``).

    Schema-2: read straight from ``producer_sets``. Schema-1 graceful read (D4d):
    bootstrap from the union of the producer's prior applied ``fields[field]``.
    """
    psets = data.get("producer_sets")
    if isinstance(psets, dict) and producer in psets:
        return _field_keys_from_list(field, psets[producer].get(field, []))
    # Legacy bootstrap: union of prior applied field values for this producer.
    boot: set = set()
    for rec in data.get("applied", []):
        if rec.get("emitted_by") == producer:
            boot |= _field_keys_from_list(field, rec.get("fields", {}).get(field, []))
    return boot


def _all_current_sets_excluding(data: dict, exclude: str, field: str) -> set:
    """Union of every OTHER producer's current stored set for *field* (ref-count)."""
    others: set = set()
    psets = data.get("producer_sets")
    producers = set(psets.keys()) if isinstance(psets, dict) else set()
    # Include producers seen only in legacy applied records, too.
    for rec in data.get("applied", []):
        if rec.get("emitted_by"):
            producers.add(rec["emitted_by"])
    for p in producers:
        if p == exclude:
            continue
        others |= _producer_stored_set(data, p, field)
    return others


def _retractable_values(data: dict, producer: str, field: str, new_fields: dict) -> set:
    """Keys *producer* would drop from frontmatter for *field* (D2 ref-count-to-zero).

    Returns a set of hashable keys (strings for "tags", tuples for "entities").
    A key K is retractable iff: (1) K ∈ producer's stored set, (2) K ∉ the
    producer's NEW asserted set, (3) K ∉ any other producer's current set.
    """
    if field not in new_fields:
        # D4b: field not reported in this run → stored set untouched, no retract.
        return set()
    prior = _producer_stored_set(data, producer, field)
    new_set = _field_keys_from_list(field, new_fields.get(field, []))
    removed = prior - new_set  # (1) and (2)
    others = _all_current_sets_excluding(data, producer, field)
    return {v for v in removed if v not in others}  # (3)


def _apply_to_md(md_path: Path, record: dict) -> None:
    """Merge *record* fields into *md_path* frontmatter and update attribution sidecar.

    Additive records (``mode != "set"``) merge set-union, byte-identical to the
    legacy path. Declarative ``set`` records additionally compute ref-count-to-zero
    removals (D2) and update the producer's stored set in ``producer_sets``. The
    whole read-modify-write is fcntl-locked (D4c).
    """
    is_set = record.get("mode") == "set"
    producer = record["emitted_by"]

    with _sidecar_lock(md_path):
        data = _read_sidecar_data(md_path)

        post = frontmatter.load(md_path)
        merged = merge_fields(dict(post.metadata), record["fields"])

        if is_set:
            for field in _SET_FIELDS:
                removable = _retractable_values(data, producer, field, record["fields"])
                if removable and field in merged:
                    # removable is a set of hashable keys; convert each value to its
                    # key before the membership test (needed for entity dicts).
                    merged[field] = [v for v in (merged.get(field) or [])
                                     if _field_value_key(field, v) not in removable]
            # Record this producer's full asserted set for every reported set-field
            # (D4b: only fields present in this record are updated).
            psets = data.setdefault("producer_sets", {})
            prod_block = psets.setdefault(producer, {})
            for field in _SET_FIELDS:
                if field in record["fields"]:
                    prod_block[field] = _field_to_stored_list(
                        field, record["fields"].get(field, []) or []
                    )

        new_post = frontmatter.Post(post.content, **merged)
        write_atomic(md_path, frontmatter.dumps(new_post))

        data.setdefault("schema", _SCHEMA)
        data.setdefault("applied", []).append(record)
        write_atomic(Path(str(md_path) + _APPLIED_SUFFIX), json.dumps(data, indent=2))
