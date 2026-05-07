"""Tests for zkm.hashing: sha256_file and git_blob_sha1."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from zkm.hashing import git_blob_sha1, git_blob_sha1_bytes, sha256_file


def test_sha256_file_empty(tmp_path: Path) -> None:
    f = tmp_path / "empty"
    f.write_bytes(b"")
    assert sha256_file(f) == hashlib.sha256(b"").hexdigest()


def test_sha256_file_text(tmp_path: Path) -> None:
    content = b"hello world\n"
    f = tmp_path / "hello.txt"
    f.write_bytes(content)
    assert sha256_file(f) == hashlib.sha256(content).hexdigest()


def test_sha256_file_large(tmp_path: Path) -> None:
    content = os.urandom(1024 * 1024)  # 1 MiB
    f = tmp_path / "large.bin"
    f.write_bytes(content)
    assert sha256_file(f) == hashlib.sha256(content).hexdigest()


def test_git_blob_sha1_empty(tmp_path: Path) -> None:
    f = tmp_path / "empty"
    f.write_bytes(b"")
    expected = subprocess.check_output(["git", "hash-object", str(f)], text=True).strip()
    assert git_blob_sha1(f) == expected


def test_git_blob_sha1_text(tmp_path: Path) -> None:
    f = tmp_path / "hello.txt"
    f.write_bytes(b"hello world\n")
    expected = subprocess.check_output(["git", "hash-object", str(f)], text=True).strip()
    assert git_blob_sha1(f) == expected


def test_git_blob_sha1_binary(tmp_path: Path) -> None:
    f = tmp_path / "bin"
    f.write_bytes(bytes(range(256)))
    expected = subprocess.check_output(["git", "hash-object", str(f)], text=True).strip()
    assert git_blob_sha1(f) == expected


def test_sha256_file_returns_hex_string(tmp_path: Path) -> None:
    f = tmp_path / "f"
    f.write_bytes(b"x")
    digest = sha256_file(f)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_git_blob_sha1_bytes_matches_path_form(tmp_path: Path) -> None:
    f = tmp_path / "sample.txt"
    f.write_bytes(b"same content for both forms\n")
    assert git_blob_sha1_bytes(f.read_bytes()) == git_blob_sha1(f)


def test_git_blob_sha1_bytes_matches_git(tmp_path: Path) -> None:
    f = tmp_path / "data.bin"
    f.write_bytes(bytes(range(256)))
    expected = subprocess.check_output(["git", "hash-object", str(f)], text=True).strip()
    assert git_blob_sha1_bytes(f.read_bytes()) == expected
