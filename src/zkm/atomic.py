"""Atomic file-write helper: write to a tmp file then os.replace."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_atomic(path: Path, content: bytes | str, *, encoding: str = "utf-8") -> None:
    """Write *content* to *path* atomically via tmp file + os.replace.

    Cleans up the tmp file if any step before the replace fails.
    *path*'s parent directory must already exist.
    """
    if isinstance(content, str):
        data = content.encode(encoding)
    else:
        data = content

    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, data)
        os.close(fd)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, path)
