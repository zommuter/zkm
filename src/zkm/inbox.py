"""One-canonical-symlink-per-CAS-object inbox protocol."""

from __future__ import annotations

import os
from pathlib import Path

from .sidecar import merge_producer

_SIDECAR_SUFFIX = ".origin.json"


def build_canonical_index(store: Path, link_subdir: str) -> dict[str, Path]:
    """Scan <store>/<link_subdir>/**/* for symlinks pointing at _objects/<aa>/<rest>.

    Returns {sha256: canonical_link_path}.  Skips missing dirs and broken links
    gracefully.
    """
    index: dict[str, Path] = {}
    inbox_dir = store / link_subdir
    if not inbox_dir.exists():
        return index
    for link in inbox_dir.rglob("*"):
        if not link.is_symlink() or link.name.endswith(_SIDECAR_SUFFIX):
            continue
        try:
            parts = Path(os.readlink(link)).parts
            if len(parts) >= 2:
                sha = parts[-2] + parts[-1]
                if len(sha) == 64 and sha not in index:
                    index[sha] = link
        except OSError:
            pass
    return index


def symlink_with_sidecar(
    *,
    cas_object: Path,
    link_dir: Path,
    link_name: str,
    producer: dict,
    canonical_index: dict[str, Path],
) -> Path:
    """Create or update the canonical inbox symlink + .origin.json sidecar.

    *cas_object* — absolute Path to the CAS object (under <store>/<subdir>/_objects/).
    *link_dir*   — absolute Path where the symlink will be created.
    *link_name*  — human-readable filename for the symlink.
    *producer*   — dict with keys: plugin, message, sha256.
    *canonical_index* — {sha256: link_path}, mutated in-place; pass {} on first call.

    Invariants:
    - Only one symlink per unique CAS sha256. If a canonical link already exists,
      only the sidecar is updated.
    - Name collision (same filename, different sha256) → suffix link_name with sha[:8].
    - Relative target computed from link_dir to cas_object via os.path.relpath.

    Returns the canonical symlink path.
    """
    sha = cas_object.parts[-2] + cas_object.parts[-1]  # aa + rest = 64 hex chars
    rel_target = Path(os.path.relpath(cas_object, link_dir))

    if sha in canonical_index:
        canonical_link = canonical_index[sha]
        sidecar_path = canonical_link.parent / (canonical_link.name + _SIDECAR_SUFFIX)
        merge_producer(sidecar_path, sha256=sha, producer=producer)
        return canonical_link

    link_dir.mkdir(parents=True, exist_ok=True)
    link_path = link_dir / link_name

    if link_path.is_symlink():
        existing_target = Path(os.readlink(link_path))
        if existing_target == rel_target:
            # Already points at the right object — register and update sidecar.
            canonical_index[sha] = link_path
            sidecar_path = link_path.parent / (link_path.name + _SIDECAR_SUFFIX)
            merge_producer(sidecar_path, sha256=sha, producer=producer)
            return link_path
        # Name collision with different content — suffix with sha prefix.
        stem, _, ext = link_name.rpartition(".")
        if not stem:
            stem, ext = link_name, ""
        else:
            ext = f".{ext}"
        link_name = f"{stem}_{sha[:8]}{ext}"
        link_path = link_dir / link_name
        if link_path.is_symlink():
            # Suffixed name already exists for this sha — register and update.
            canonical_index[sha] = link_path
            sidecar_path = link_path.parent / (link_path.name + _SIDECAR_SUFFIX)
            merge_producer(sidecar_path, sha256=sha, producer=producer)
            return link_path

    link_path.symlink_to(rel_target)
    canonical_index[sha] = link_path
    sidecar_path = link_path.parent / (link_path.name + _SIDECAR_SUFFIX)
    merge_producer(sidecar_path, sha256=sha, producer=producer)
    return link_path
