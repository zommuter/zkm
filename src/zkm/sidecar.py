"""Spec v1 sidecar: read / merge_producer / rebuild .origin.json files."""

from __future__ import annotations

import json
from pathlib import Path

from .atomic import write_atomic

_REQUIRED_PRODUCER_KEYS = {"plugin", "message", "sha256"}


def read_sidecar(path: Path) -> dict | None:
    """Return the parsed sidecar dict at *path*, or None if missing or malformed."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def merge_producer(path: Path, *, sha256: str, producer: dict) -> None:
    """Merge *producer* into the sidecar at *path*.

    Creates the sidecar if it doesn't exist. Deduplicates by producer['sha256']
    (source-content hash — stable across message path changes). Sorts producers
    by 'message' (ascending). Writes atomically.

    *producer* must contain keys: plugin, message, sha256.
    """
    missing = _REQUIRED_PRODUCER_KEYS - producer.keys()
    if missing:
        raise ValueError(f"producer is missing required keys: {missing}")

    existing = read_sidecar(path)
    if existing is not None:
        producers: list[dict] = existing.get("producers", [])
        if not any(p.get("sha256") == producer["sha256"] for p in producers):
            producers.append(producer)
            producers.sort(key=lambda p: p.get("message", ""))
        data = {**existing, "producers": producers}
    else:
        data = {
            "schema": 1,
            "sha256": sha256,
            "producers": [producer],
        }

    write_atomic(path, json.dumps(data, indent=2))


def rebuild_sidecar(path: Path, *, sha256: str, producers: list[dict]) -> None:
    """Atomically write a fresh sidecar from a complete *producers* list.

    Intended for --reprocess-all: rebuilds the sidecar from a trusted scan
    rather than merging incrementally. Producers are sorted by 'message'.
    """
    for p in producers:
        missing = _REQUIRED_PRODUCER_KEYS - p.keys()
        if missing:
            raise ValueError(f"producer is missing required keys: {missing}")

    sorted_producers = sorted(producers, key=lambda p: p.get("message", ""))
    data = {"schema": 1, "sha256": sha256, "producers": sorted_producers}
    write_atomic(path, json.dumps(data, indent=2))
