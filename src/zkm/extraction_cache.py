"""Extraction cache for per-document extractor results.

Per-store at <store>/.zkm-state/extraction-cache/<extractor_name>/.
Key: (body_sha256, model_name, model_version).

Layout:
    <store>/.zkm-state/extraction-cache/<extractor>/<sha256[:2]>/<sha256[2:]>.json

Each file holds all model variants for one document body so a model swap
preserves the other variants.  File content:

    {
      "_schema_version": 1,
      "body_sha256": "abc...",
      "extractor": "ner",
      "entries": {
        "<model_name>:<model_version>": {
          "entities": [...],
          "cached_at": "<iso8601>"
        }
      }
    }

Bump _SCHEMA_VERSION when the file structure changes; all existing entries
for that extractor become cache misses and are lazily overwritten on next put.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from zkm.atomic import write_atomic

_SCHEMA_VERSION = 1
_STATE_DIR = ".zkm-state/extraction-cache"


class ExtractionCache:
    """Read/write extraction results keyed by (body_sha256, model_name, model_version)."""

    def __init__(self, store_path: Path, *, extractor_name: str) -> None:
        self._base = store_path / _STATE_DIR / extractor_name
        self._extractor = extractor_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(
        self,
        body_sha256: str,
        *,
        model_name: str,
        model_version: str,
    ) -> list | None:
        """Return cached value list or ``None`` on miss.

        Returns ``None`` when the file is absent, unreadable, has a wrong
        schema version, or the specific model variant is not present.
        """
        path = self._entry_path(body_sha256)
        if not path.exists():
            return None
        data = self._load(path)
        if data is None:
            return None
        entry = data.get("entries", {}).get(f"{model_name}:{model_version}")
        if entry is None:
            return None
        return entry.get("entities")

    def put(
        self,
        body_sha256: str,
        value: list,
        *,
        model_name: str,
        model_version: str,
    ) -> None:
        """Write *value* to the cache under the given key.

        Preserves any existing model variants for the same document body.
        If the on-disk schema version differs, existing variants are dropped.
        """
        path = self._entry_path(body_sha256)
        path.parent.mkdir(parents=True, exist_ok=True)

        existing = self._load(path) if path.exists() else None
        entries: dict = existing.get("entries", {}) if existing is not None else {}

        entries[f"{model_name}:{model_version}"] = {
            "entities": value,
            "cached_at": datetime.now(UTC).isoformat(),
        }

        payload = {
            "_schema_version": _SCHEMA_VERSION,
            "body_sha256": body_sha256,
            "extractor": self._extractor,
            "entries": entries,
        }
        write_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2))

    # ------------------------------------------------------------------

    def _entry_path(self, body_sha256: str) -> Path:
        return self._base / body_sha256[:2] / f"{body_sha256[2:]}.json"

    def _load(self, path: Path) -> dict | None:
        """Return parsed JSON dict, or None if unreadable or wrong schema version."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if data.get("_schema_version") != _SCHEMA_VERSION:
            return None
        return data
