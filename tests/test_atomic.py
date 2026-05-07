"""Tests for zkm.atomic.write_atomic."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from zkm.atomic import write_atomic


def test_write_bytes(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    write_atomic(target, b"hello bytes")
    assert target.read_bytes() == b"hello bytes"


def test_write_str_utf8(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    write_atomic(target, "hëllo wörld")
    assert target.read_text(encoding="utf-8") == "hëllo wörld"


def test_write_str_custom_encoding(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    write_atomic(target, "café", encoding="latin-1")
    assert target.read_bytes() == "café".encode("latin-1")


def test_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    target.write_text("old", encoding="utf-8")
    write_atomic(target, b"new")
    assert target.read_bytes() == b"new"


def test_no_tmp_leak_on_write_failure(tmp_path: Path) -> None:
    target = tmp_path / "f.bin"

    def fail_write(fd: int, _data: bytes) -> int:
        os.close(fd)
        raise OSError("disk full")

    with patch("os.write", side_effect=fail_write):
        with pytest.raises(OSError, match="disk full"):
            write_atomic(target, b"data")

    # No .tmp files should remain.
    assert list(tmp_path.glob("*.tmp")) == []
    assert not target.exists()


def test_file_matches_input_exactly(tmp_path: Path) -> None:
    payload = os.urandom(1024 * 1024)  # 1 MiB random
    target = tmp_path / "large.bin"
    write_atomic(target, payload)
    assert target.read_bytes() == payload
