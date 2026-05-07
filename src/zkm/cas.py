"""Content-addressed storage: write_object(store, subdir, src) -> Path."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .atomic import write_atomic
from .hashing import sha256_file


def write_object(store: Path, subdir: str, src: Path | bytes) -> Path:
    """Write *src* into <store>/<subdir>/_objects/<aa>/<rest> keyed by SHA-256.

    Idempotent: if the object already exists, returns its path without re-writing.
    *src* may be a Path (content is read) or raw bytes.
    Returns the absolute Path to the CAS object.
    """
    if isinstance(src, (bytes, bytearray)):
        data: bytes = bytes(src)
        sha = hashlib.sha256(data).hexdigest()
    else:
        sha = sha256_file(src)
        data = src.read_bytes()

    objects_dir = store / subdir / "_objects"
    shard_dir = objects_dir / sha[:2]
    shard_dir.mkdir(parents=True, exist_ok=True)
    obj_path = shard_dir / sha[2:]

    if not obj_path.exists():
        write_atomic(obj_path, data)

    return obj_path
