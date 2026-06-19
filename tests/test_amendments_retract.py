"""RED spec for the declarative-set retract primitive (id:25ec, f103 D1-D5).

# roadmap:25ec

Specs the core declarative producer-set model: a producer emits its FULL current
asserted set for a key each run; core stores each producer's last set per md-key
in the attribution sidecar and computes REMOVALS by diffing prior-vs-new.
Additions stay set-union (byte-identical to today's merge_fields path). A tag is
dropped from frontmatter iff it ref-counts to zero across all producers' current
sets (D2). Empty asserted set = no-op, never bulk-retract (D4a). Diff is scoped to
keys reported this run (D4b). Legacy append-only sidecars bootstrap gracefully (D4d).

This file is RED until id:25ec ships. Design:
docs/meeting-notes/2026-06-18-1944-f103-tag-removal-core-semantic.md
"""

from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

# These symbols do not exist yet — importing them is the first RED assertion.
emit_set = pytest.importorskip("zkm.amendments").__dict__.get("emit_set")

from zkm.amendments import apply_queue, emit  # noqa: E402


def _make_md(directory: Path, filename: str, *, message_id: str,
             tags: list | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    post = frontmatter.Post(
        "body text",
        source="zkm-eml",
        date="2026-05-08T12:00:00+00:00",
        message_id=message_id,
        tags=tags if tags is not None else [],
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


def _tags(md_path: Path) -> list:
    return frontmatter.load(md_path).metadata.get("tags", [])


@pytest.mark.skipif(emit_set is None, reason="emit_set not implemented yet (id:25ec)")
def test_retract_sole_producer_drops_tag(tmp_path: Path) -> None:
    """Producer asserts {a,b} then re-asserts {a}; b ref-counts to zero -> removed."""
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<r1@host>")
    emit_set(tmp_path, key={"message_id": "<r1@host>"},
             fields={"tags": ["a", "b"]}, emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    assert sorted(_tags(md)) == ["a", "b"]

    # producer drops 'b' from its asserted set
    emit_set(tmp_path, key={"message_id": "<r1@host>"},
             fields={"tags": ["a"]}, emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    assert _tags(md) == ["a"]


@pytest.mark.skipif(emit_set is None, reason="emit_set not implemented yet (id:25ec)")
def test_retract_keeps_tag_asserted_by_other_producer(tmp_path: Path) -> None:
    """notmuch drops 'shared' but zkm-priority still asserts it -> tag stays (D2)."""
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<r2@host>")
    emit_set(tmp_path, key={"message_id": "<r2@host>"},
             fields={"tags": ["shared"]}, emitted_by="zkm-notmuch")
    emit_set(tmp_path, key={"message_id": "<r2@host>"},
             fields={"tags": ["shared"]}, emitted_by="zkm-priority")
    apply_queue(tmp_path)
    assert _tags(md) == ["shared"]

    # notmuch drops it; priority still asserts -> ref-count stays 1 -> kept
    emit_set(tmp_path, key={"message_id": "<r2@host>"},
             fields={"tags": []}, emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    assert _tags(md) == ["shared"]


@pytest.mark.skipif(emit_set is None, reason="emit_set not implemented yet (id:25ec)")
def test_empty_asserted_set_is_noop_not_bulk_retract(tmp_path: Path) -> None:
    """A first-ever empty asserted set retracts nothing (D4a guard)."""
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<r3@host>",
                  tags=["preexisting"])
    emit_set(tmp_path, key={"message_id": "<r3@host>"},
             fields={"tags": []}, emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    assert _tags(md) == ["preexisting"]


@pytest.mark.skipif(emit_set is None, reason="emit_set not implemented yet (id:25ec)")
def test_retract_idempotent(tmp_path: Path) -> None:
    """Re-applying the same declarative set after a retract is a no-op."""
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<r4@host>")
    emit_set(tmp_path, key={"message_id": "<r4@host>"},
             fields={"tags": ["a"]}, emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    emit_set(tmp_path, key={"message_id": "<r4@host>"},
             fields={"tags": ["a"]}, emitted_by="zkm-notmuch")
    applied, pending = apply_queue(tmp_path)
    assert applied == 0 and pending == 0
    assert _tags(md) == ["a"]


@pytest.mark.skipif(emit_set is None, reason="emit_set not implemented yet (id:25ec)")
def test_additive_emit_unaffected_by_retract_machinery(tmp_path: Path) -> None:
    """The legacy additive emit() path stays set-union (byte-identical)."""
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<r5@host>",
                  tags=["kept"])
    emit(tmp_path, key={"message_id": "<r5@host>"},
         fields={"tags": ["added"]}, emitted_by="zkm-eml")
    apply_queue(tmp_path)
    assert sorted(_tags(md)) == ["added", "kept"]
