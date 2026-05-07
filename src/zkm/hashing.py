"""Content-hashing helpers: SHA-256 and git blob SHA-1."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 65536


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of *path*, streamed in 64K chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(path: Path) -> str:
    """Return the git blob SHA-1 of *path* without invoking git."""
    return git_blob_sha1_bytes(path.read_bytes())


def git_blob_sha1_bytes(data: bytes) -> str:
    """Return the git blob SHA-1 of in-memory *data* without invoking git."""
    h = hashlib.sha1(usedforsecurity=False)
    h.update(f"blob {len(data)}\0".encode())
    h.update(data)
    return h.hexdigest()
