"""Shared source-state management for zkm plugins.

State file: <store>/.zkm-state/zkm-<plugin>.json
Schema: { "<abs_source_path>": { ... plugin-specific fields ... } }

Watermark semantics (inherited from zkm-whatsapp):
- watermark is a speed optimisation only; deleting the file is always safe.
- correctness comes from dedup-on-key; the watermark merely skips already-seen rows.
- multi-account independence: each source (resolved to absolute path) is an independent key.
"""

from __future__ import annotations

import json
from pathlib import Path

from zkm.atomic import write_atomic


def _state_path(store: Path, plugin: str) -> Path:
    return store / ".zkm-state" / f"zkm-{plugin}.json"


def load_state(store: Path, plugin: str, source: Path) -> dict:
    """Return the state dict for *source* within *plugin*, or {} if not recorded."""
    path = _state_path(store, plugin)
    if not path.exists():
        return {}
    all_state: dict = json.loads(path.read_text(encoding="utf-8"))
    return all_state.get(str(source.resolve()), {})


def save_state(store: Path, plugin: str, source: Path, state: dict) -> None:
    """Persist *state* for *source* within *plugin* (merges with other source entries)."""
    path = _state_path(store, plugin)
    path.parent.mkdir(parents=True, exist_ok=True)
    all_state: dict = {}
    if path.exists():
        all_state = json.loads(path.read_text(encoding="utf-8"))
    all_state[str(source.resolve())] = state
    write_atomic(path, json.dumps(all_state, indent=2, ensure_ascii=False))
