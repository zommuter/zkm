"""Tests for zkm.inbox: build_canonical_index and symlink_with_sidecar."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from zkm.cas import write_object
from zkm.inbox import build_canonical_index, symlink_with_sidecar


def _producer(sha: str, msg: str = "mail/messages/2026/05/x.md", plugin: str = "eml") -> dict:
    return {"plugin": plugin, "message": msg, "sha256": sha}


def _link_dir(store: Path) -> Path:
    d = store / "inbox" / "mail" / "2026" / "05"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- build_canonical_index ---

def test_build_canonical_index_empty_store(tmp_path: Path) -> None:
    assert build_canonical_index(tmp_path, "inbox/mail") == {}


def test_build_canonical_index_finds_link(tmp_path: Path) -> None:
    cas = write_object(tmp_path, "mail", b"attachment content")
    link_dir = _link_dir(tmp_path)
    idx: dict = {}
    symlink_with_sidecar(
        cas_object=cas,
        link_dir=link_dir,
        link_name="doc.pdf",
        producer=_producer("b" * 64),
        canonical_index=idx,
    )

    fresh_idx = build_canonical_index(tmp_path, "inbox/mail")
    sha = hashlib.sha256(b"attachment content").hexdigest()
    assert sha in fresh_idx
    assert fresh_idx[sha] == idx[sha]


# --- symlink_with_sidecar ---

def test_first_call_creates_symlink_and_sidecar(tmp_path: Path) -> None:
    cas = write_object(tmp_path, "mail", b"pdf bytes")
    link_dir = _link_dir(tmp_path)
    idx: dict = {}
    link = symlink_with_sidecar(
        cas_object=cas,
        link_dir=link_dir,
        link_name="report.pdf",
        producer=_producer("b" * 64),
        canonical_index=idx,
    )
    assert link.is_symlink()
    sidecar = link.parent / (link.name + ".origin.json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert len(data["producers"]) == 1


def test_second_call_same_sha_no_new_symlink(tmp_path: Path) -> None:
    cas = write_object(tmp_path, "mail", b"same content")
    link_dir = _link_dir(tmp_path)
    idx: dict = {}
    link1 = symlink_with_sidecar(
        cas_object=cas,
        link_dir=link_dir,
        link_name="a.bin",
        producer=_producer("b" * 64, "mail/messages/2026/05/msg1.md"),
        canonical_index=idx,
    )
    link2 = symlink_with_sidecar(
        cas_object=cas,
        link_dir=link_dir,
        link_name="a.bin",
        producer=_producer("c" * 64, "mail/messages/2026/05/msg2.md"),
        canonical_index=idx,
    )
    # Same canonical link returned both times — only one symlink exists.
    assert link1 == link2
    symlinks = [p for p in link_dir.iterdir() if p.is_symlink()]
    assert len(symlinks) == 1
    # Sidecar has both producers.
    sidecar = link1.parent / (link1.name + ".origin.json")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert len(data["producers"]) == 2


def test_symlink_resolves_to_cas_object(tmp_path: Path) -> None:
    cas = write_object(tmp_path, "mail", b"resolve me")
    link_dir = _link_dir(tmp_path)
    link = symlink_with_sidecar(
        cas_object=cas,
        link_dir=link_dir,
        link_name="f.bin",
        producer=_producer("b" * 64),
        canonical_index={},
    )
    assert link.resolve() == cas.resolve()


def test_collision_suffix_different_sha(tmp_path: Path) -> None:
    cas_a = write_object(tmp_path, "mail", b"content A")
    cas_b = write_object(tmp_path, "mail", b"content B")
    link_dir = _link_dir(tmp_path)

    link_a = symlink_with_sidecar(
        cas_object=cas_a,
        link_dir=link_dir,
        link_name="file.pdf",
        producer=_producer("b" * 64),
        canonical_index={},
    )
    sha_b = hashlib.sha256(b"content B").hexdigest()
    link_b = symlink_with_sidecar(
        cas_object=cas_b,
        link_dir=link_dir,
        link_name="file.pdf",  # same name, different sha
        producer=_producer("c" * 64),
        canonical_index={},
    )
    assert link_a.name == "file.pdf"
    assert link_b.name == f"file_{sha_b[:8]}.pdf"


def test_relative_target_is_correct(tmp_path: Path) -> None:
    cas = write_object(tmp_path, "mail", b"target test")
    link_dir = _link_dir(tmp_path)
    link = symlink_with_sidecar(
        cas_object=cas,
        link_dir=link_dir,
        link_name="t.bin",
        producer=_producer("b" * 64),
        canonical_index={},
    )
    raw_target = Path(os.readlink(link))
    # Must be relative (not absolute).
    assert not raw_target.is_absolute()
    # Following it from link_dir must land on the CAS object.
    resolved = (link_dir / raw_target).resolve()
    assert resolved == cas.resolve()


def test_canonical_index_updated_on_create(tmp_path: Path) -> None:
    cas = write_object(tmp_path, "mail", b"idx update")
    sha = hashlib.sha256(b"idx update").hexdigest()
    link_dir = _link_dir(tmp_path)
    idx: dict = {}
    symlink_with_sidecar(
        cas_object=cas,
        link_dir=link_dir,
        link_name="idx.bin",
        producer=_producer("b" * 64),
        canonical_index=idx,
    )
    assert sha in idx
