"""Tests for zkm.amendments: emit, apply_queue, merge_fields."""

from __future__ import annotations

import json
from pathlib import Path

import frontmatter
import pytest

from zkm.amendments import (
    _APPLIED_SUFFIX,
    _QUEUE_DIR,
    _record_hash,
    apply_queue,
    emit,
    merge_fields,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_md(directory: Path, filename: str, *, message_id: str | None = None,
             sha256: str | None = None, tags: list | None = None) -> Path:
    """Write a minimal zkm-eml-style md file; returns its path."""
    meta: dict = {
        "source": "zkm-eml",
        "date": "2026-05-08T12:00:00+00:00",
        "tags": tags if tags is not None else [],
    }
    if message_id:
        meta["message_id"] = message_id
    if sha256:
        meta["sha256"] = sha256

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    post = frontmatter.Post("body text", **meta)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


def _load_tags(md_path: Path) -> list:
    return frontmatter.load(md_path).metadata.get("tags", [])


def _load_attribution(md_path: Path) -> dict:
    sidecar = Path(str(md_path) + _APPLIED_SUFFIX)
    return json.loads(sidecar.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# emit
# ---------------------------------------------------------------------------


def test_emit_writes_record_under_emitter_dir(tmp_path: Path) -> None:
    qp = emit(tmp_path, key={"message_id": "<a@b>"}, fields={"tags": ["bill"]},
              emitted_by="zkm-notmuch")
    assert qp.parent == tmp_path / _QUEUE_DIR / "zkm-notmuch"
    data = json.loads(qp.read_text(encoding="utf-8"))
    assert data["key"] == {"message_id": "<a@b>"}
    assert data["fields"] == {"tags": ["bill"]}
    assert data["emitted_by"] == "zkm-notmuch"
    assert data["schema"] == 1


def test_emit_idempotent_same_record_same_path(tmp_path: Path) -> None:
    p1 = emit(tmp_path, key={"message_id": "<a@b>"}, fields={"tags": ["bill"]},
              emitted_by="zkm-notmuch")
    p2 = emit(tmp_path, key={"message_id": "<a@b>"}, fields={"tags": ["bill"]},
              emitted_by="zkm-notmuch")
    assert p1 == p2
    queue_dir = tmp_path / _QUEUE_DIR / "zkm-notmuch"
    assert len(list(queue_dir.glob("*.json"))) == 1


def test_emit_different_fields_different_file(tmp_path: Path) -> None:
    p1 = emit(tmp_path, key={"message_id": "<a@b>"}, fields={"tags": ["bill"]},
              emitted_by="zkm-notmuch")
    p2 = emit(tmp_path, key={"message_id": "<a@b>"}, fields={"tags": ["invoice"]},
              emitted_by="zkm-notmuch")
    assert p1 != p2


def test_emit_validates_missing_key(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="key"):
        emit(tmp_path, key={}, fields={"tags": ["x"]}, emitted_by="p")


def test_emit_validates_missing_fields(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fields"):
        emit(tmp_path, key={"path": "x.md"}, fields={}, emitted_by="p")


def test_emit_validates_missing_emitted_by(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="emitted_by"):
        emit(tmp_path, key={"path": "x.md"}, fields={"tags": ["x"]}, emitted_by="")


def test_emit_accepts_custom_emitted_at(tmp_path: Path) -> None:
    ts = "2026-05-08T10:00:00+02:00"
    qp = emit(tmp_path, key={"path": "x.md"}, fields={"tags": ["x"]},
              emitted_by="p", emitted_at=ts)
    data = json.loads(qp.read_text(encoding="utf-8"))
    assert data["emitted_at"] == ts


# ---------------------------------------------------------------------------
# apply_queue — key resolution
# ---------------------------------------------------------------------------


def test_apply_queue_resolves_by_message_id(tmp_path: Path) -> None:
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<test@host>")
    emit(tmp_path, key={"message_id": "<test@host>"}, fields={"tags": ["bill"]},
         emitted_by="zkm-notmuch")
    applied, pending = apply_queue(tmp_path)
    assert applied == 1 and pending == 0
    assert _load_tags(md) == ["bill"]


def test_apply_queue_resolves_by_sha256(tmp_path: Path) -> None:
    sha = "a" * 64
    md = _make_md(tmp_path / "docs", "doc.md", sha256=sha)
    emit(tmp_path, key={"sha256": sha}, fields={"tags": ["receipt"]},
         emitted_by="zkm-scan")
    applied, pending = apply_queue(tmp_path)
    assert applied == 1 and pending == 0
    assert "receipt" in _load_tags(md)


def test_apply_queue_resolves_by_relative_path(tmp_path: Path) -> None:
    md = _make_md(tmp_path / "notes", "note.md")
    emit(tmp_path, key={"path": "notes/note.md"}, fields={"tags": ["idea"]},
         emitted_by="zkm-tag")
    applied, pending = apply_queue(tmp_path)
    assert applied == 1 and pending == 0
    assert "idea" in _load_tags(md)


def test_apply_queue_leaves_unresolved_records_in_queue(tmp_path: Path) -> None:
    emit(tmp_path, key={"message_id": "<ghost@host>"}, fields={"tags": ["x"]},
         emitted_by="zkm-notmuch")
    applied, pending = apply_queue(tmp_path)
    assert applied == 0 and pending == 1
    queue_dir = tmp_path / _QUEUE_DIR / "zkm-notmuch"
    assert len(list(queue_dir.glob("*.json"))) == 1


def test_apply_queue_replays_after_md_appears(tmp_path: Path) -> None:
    emit(tmp_path, key={"message_id": "<late@host>"}, fields={"tags": ["bill"]},
         emitted_by="zkm-notmuch")
    assert apply_queue(tmp_path) == (0, 1)

    md = _make_md(tmp_path / "mail", "late.md", message_id="<late@host>")
    applied, pending = apply_queue(tmp_path)
    assert applied == 1 and pending == 0
    assert "bill" in _load_tags(md)


# ---------------------------------------------------------------------------
# apply_queue — round-trip and idempotency
# ---------------------------------------------------------------------------


def test_apply_queue_round_trip_tags_set_union(tmp_path: Path) -> None:
    """Spec round-trip: zkm-eml writes tags:[]; amendment tags:[bill] → merged."""
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<rt@host>", tags=[])
    emit(tmp_path, key={"message_id": "<rt@host>"}, fields={"tags": ["bill"]},
         emitted_by="zkm-notmuch")
    apply_queue(tmp_path)

    assert _load_tags(md) == ["bill"]
    attr = _load_attribution(md)
    assert attr["schema"] == 1
    assert len(attr["applied"]) == 1
    assert attr["applied"][0]["emitted_by"] == "zkm-notmuch"
    assert "emitted_at" in attr["applied"][0]


def test_apply_queue_idempotent_no_double_apply(tmp_path: Path) -> None:
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<idem@host>")
    emit(tmp_path, key={"message_id": "<idem@host>"}, fields={"tags": ["bill"]},
         emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    # re-emit (simulates amender re-run after apply)
    emit(tmp_path, key={"message_id": "<idem@host>"}, fields={"tags": ["bill"]},
         emitted_by="zkm-notmuch")
    applied, pending = apply_queue(tmp_path)
    assert applied == 0 and pending == 0
    assert _load_attribution(md)["applied"].__len__() == 1


def test_apply_queue_returns_zero_zero_with_empty_queue(tmp_path: Path) -> None:
    assert apply_queue(tmp_path) == (0, 0)


def test_apply_queue_returns_applied_pending_counts(tmp_path: Path) -> None:
    _make_md(tmp_path / "mail", "found.md", message_id="<found@host>")
    emit(tmp_path, key={"message_id": "<found@host>"}, fields={"tags": ["a"]},
         emitted_by="p")
    emit(tmp_path, key={"message_id": "<missing@host>"}, fields={"tags": ["b"]},
         emitted_by="p")
    applied, pending = apply_queue(tmp_path)
    assert applied == 1 and pending == 1


def test_apply_queue_two_amenders_same_md(tmp_path: Path) -> None:
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<multi@host>")
    emit(tmp_path, key={"message_id": "<multi@host>"}, fields={"tags": ["bill"]},
         emitted_by="zkm-notmuch")
    emit(tmp_path, key={"message_id": "<multi@host>"}, fields={"tags": ["important"]},
         emitted_by="zkm-priority")
    apply_queue(tmp_path)

    tags = _load_tags(md)
    assert "bill" in tags and "important" in tags
    attr = _load_attribution(md)
    emitters = {r["emitted_by"] for r in attr["applied"]}
    assert emitters == {"zkm-notmuch", "zkm-priority"}


def test_apply_queue_preserves_existing_tags(tmp_path: Path) -> None:
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<pre@host>",
                  tags=["existing"])
    emit(tmp_path, key={"message_id": "<pre@host>"}, fields={"tags": ["new"]},
         emitted_by="p")
    apply_queue(tmp_path)
    assert sorted(_load_tags(md)) == ["existing", "new"]


# ---------------------------------------------------------------------------
# merge_fields
# ---------------------------------------------------------------------------


def test_merge_fields_tags_set_union_sorted() -> None:
    result = merge_fields({"tags": ["b", "a"]}, {"tags": ["c", "a"]})
    assert result["tags"] == ["a", "b", "c"]


def test_merge_fields_tags_empty_existing() -> None:
    result = merge_fields({"tags": []}, {"tags": ["bill"]})
    assert result["tags"] == ["bill"]


def test_merge_fields_entities_role_tagged_dedup() -> None:
    alice_sender = {"name": "Alice", "role": "sender"}
    alice_recip = {"name": "Alice", "role": "recipient"}
    bob = {"name": "Bob", "role": "sender"}
    result = merge_fields(
        {"entities": [alice_sender]},
        {"entities": [alice_sender, alice_recip, bob]},
    )
    ents = result["entities"]
    # alice_sender already present → not duplicated; alice_recip + bob added
    assert len(ents) == 3
    assert alice_sender in ents
    assert alice_recip in ents
    assert bob in ents


def test_merge_fields_entities_existing_takes_precedence() -> None:
    ent = {"name": "Alice", "role": "sender"}
    result = merge_fields({"entities": [ent]}, {"entities": [ent]})
    assert len(result["entities"]) == 1


def test_merge_fields_scalar_last_write_wins() -> None:
    result = merge_fields({"date": "2026-01-01", "title": "old"}, {"title": "new"})
    assert result["title"] == "new"
    assert result["date"] == "2026-01-01"


def test_merge_fields_does_not_mutate_existing() -> None:
    existing = {"tags": ["a"]}
    merge_fields(existing, {"tags": ["b"]})
    assert existing["tags"] == ["a"]


# ---------------------------------------------------------------------------
# _record_hash
# ---------------------------------------------------------------------------


def test_record_hash_stable_across_emitted_at() -> None:
    r1 = {"key": {"message_id": "<a@b>"}, "fields": {"tags": ["x"]},
          "emitted_by": "p", "emitted_at": "2026-01-01T00:00:00+00:00"}
    r2 = {**r1, "emitted_at": "2026-06-01T00:00:00+00:00"}
    assert _record_hash(r1) == _record_hash(r2)


def test_record_hash_differs_on_different_fields() -> None:
    r1 = {"key": {"message_id": "<a@b>"}, "fields": {"tags": ["x"]}, "emitted_by": "p"}
    r2 = {**r1, "fields": {"tags": ["y"]}}
    assert _record_hash(r1) != _record_hash(r2)
