"""Tests for zkm.cas.write_object."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from zkm.cas import write_object


def test_write_bytes_creates_object(tmp_path: Path) -> None:
    obj = write_object(tmp_path, "mail", b"hello")
    sha = hashlib.sha256(b"hello").hexdigest()
    expected = tmp_path / "mail" / "_objects" / sha[:2] / sha[2:]
    assert obj == expected
    assert obj.read_bytes() == b"hello"


def test_write_path_creates_object(tmp_path: Path) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"from file")
    obj = write_object(tmp_path, "docs", src)
    sha = hashlib.sha256(b"from file").hexdigest()
    expected = tmp_path / "docs" / "_objects" / sha[:2] / sha[2:]
    assert obj == expected
    assert obj.read_bytes() == b"from file"


def test_idempotent_bytes(tmp_path: Path) -> None:
    write_object(tmp_path, "mail", b"data")
    obj = write_object(tmp_path, "mail", b"data")
    sha = hashlib.sha256(b"data").hexdigest()
    expected = tmp_path / "mail" / "_objects" / sha[:2] / sha[2:]
    assert obj == expected
    # Only one object file exists (no duplicates)
    objects_dir = tmp_path / "mail" / "_objects"
    all_objects = [p for p in objects_dir.rglob("*") if p.is_file()]
    assert len(all_objects) == 1


def test_idempotent_preserves_mtime(tmp_path: Path) -> None:
    obj = write_object(tmp_path, "mail", b"stable")
    mtime_before = obj.stat().st_mtime
    write_object(tmp_path, "mail", b"stable")
    assert obj.stat().st_mtime == mtime_before


def test_different_content_different_objects(tmp_path: Path) -> None:
    obj_a = write_object(tmp_path, "mail", b"aaa")
    obj_b = write_object(tmp_path, "mail", b"bbb")
    assert obj_a != obj_b
    assert obj_a.read_bytes() == b"aaa"
    assert obj_b.read_bytes() == b"bbb"


def test_returned_path_is_absolute(tmp_path: Path) -> None:
    obj = write_object(tmp_path, "mail", b"x")
    assert obj.is_absolute()


def test_shard_layout(tmp_path: Path) -> None:
    obj = write_object(tmp_path, "mail", b"test shard")
    sha = hashlib.sha256(b"test shard").hexdigest()
    # Parent dir name = sha[:2], filename = sha[2:]
    assert obj.parent.name == sha[:2]
    assert obj.name == sha[2:]


def test_large_payload(tmp_path: Path) -> None:
    data = os.urandom(512 * 1024)
    obj = write_object(tmp_path, "mail", data)
    assert obj.read_bytes() == data
