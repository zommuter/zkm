"""Tests for zkm.sidecar: read_sidecar, merge_producer, rebuild_sidecar."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zkm.sidecar import merge_producer, read_sidecar, rebuild_sidecar

# --- read_sidecar ---

def test_read_sidecar_missing(tmp_path: Path) -> None:
    assert read_sidecar(tmp_path / "nope.json") is None


def test_read_sidecar_malformed(tmp_path: Path) -> None:
    f = tmp_path / "bad.json"
    f.write_bytes(b"not-json{{")
    assert read_sidecar(f) is None


def test_read_sidecar_valid(tmp_path: Path) -> None:
    f = tmp_path / "s.json"
    data = {"schema": 1, "sha256": "a" * 64, "producers": []}
    f.write_text(json.dumps(data), encoding="utf-8")
    assert read_sidecar(f) == data


# --- merge_producer ---

def _make_producer(sha: str, msg: str = "mail/m.md", plugin: str = "eml") -> dict:
    return {"plugin": plugin, "message": msg, "sha256": sha}


def test_merge_producer_creates_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "s.origin.json"
    producer = _make_producer("b" * 64, "mail/messages/2026/05/x.md")
    merge_producer(path, sha256="a" * 64, producer=producer)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == 1
    assert data["sha256"] == "a" * 64
    assert data["producers"] == [producer]


def test_merge_producer_appends_new_producer(tmp_path: Path) -> None:
    path = tmp_path / "s.origin.json"
    p1 = _make_producer("b" * 64, "mail/messages/2026/05/a.md")
    p2 = _make_producer("c" * 64, "mail/messages/2026/05/b.md")
    merge_producer(path, sha256="a" * 64, producer=p1)
    merge_producer(path, sha256="a" * 64, producer=p2)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["producers"]) == 2


def test_merge_producer_dedup_by_source_sha256(tmp_path: Path) -> None:
    """Regression: same source sha256 with a different message path must NOT grow producers."""
    path = tmp_path / "s.origin.json"
    msg_sha = "b" * 64
    msg = "mail/messages/2026/04/original.md"
    msg_drift = "mail/messages/2026/04/original_1.md"
    merge_producer(path, sha256="a" * 64, producer=_make_producer(msg_sha, msg))
    merge_producer(path, sha256="a" * 64, producer=_make_producer(msg_sha, msg_drift))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["producers"]) == 1, (
        "Sidecar producer list grew despite same source sha256 — "
        "dedup key must be sha256, not message path"
    )


def test_merge_producer_sort_by_message(tmp_path: Path) -> None:
    path = tmp_path / "s.origin.json"
    p_b = _make_producer("b" * 64, "mail/messages/2026/05/b.md")
    p_a = _make_producer("c" * 64, "mail/messages/2026/05/a.md")
    merge_producer(path, sha256="a" * 64, producer=p_b)
    merge_producer(path, sha256="a" * 64, producer=p_a)
    data = json.loads(path.read_text(encoding="utf-8"))
    msgs = [p["message"] for p in data["producers"]]
    assert msgs == sorted(msgs)


def test_merge_producer_missing_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    with pytest.raises(ValueError, match="missing required keys"):
        merge_producer(path, sha256="a" * 64, producer={"plugin": "eml", "message": "x.md"})


def test_merge_producer_recovers_from_corrupt_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.json"
    path.write_bytes(b"{{bad")
    producer = _make_producer("b" * 64)
    merge_producer(path, sha256="a" * 64, producer=producer)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["producers"]) == 1


# --- rebuild_sidecar ---

def test_rebuild_sidecar_writes_fresh(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    producers = [
        _make_producer("b" * 64, "mail/messages/2026/05/b.md"),
        _make_producer("c" * 64, "mail/messages/2026/05/a.md"),
    ]
    rebuild_sidecar(path, sha256="a" * 64, producers=producers)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == 1
    assert len(data["producers"]) == 2
    msgs = [p["message"] for p in data["producers"]]
    assert msgs == sorted(msgs)


def test_rebuild_sidecar_overwrites_existing(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    rebuild_sidecar(path, sha256="a" * 64, producers=[_make_producer("b" * 64)])
    rebuild_sidecar(path, sha256="a" * 64, producers=[_make_producer("c" * 64)])
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["producers"]) == 1
    assert data["producers"][0]["sha256"] == "c" * 64


def test_rebuild_sidecar_missing_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    with pytest.raises(ValueError, match="missing required keys"):
        rebuild_sidecar(path, sha256="a" * 64, producers=[{"plugin": "eml"}])
