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

import json
from pathlib import Path

import frontmatter
import pytest

# These symbols do not exist yet — importing them is the first RED assertion.
emit_set = pytest.importorskip("zkm.amendments").__dict__.get("emit_set")

from zkm.amendments import (  # noqa: E402
    _APPLIED_SUFFIX,
    apply_queue,
    emit,
    plan_retractions,
)


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


@pytest.mark.skipif(emit_set is None, reason="emit_set not implemented yet (id:25ec)")
def test_retract_run_scoped_does_not_touch_other_keys(tmp_path: Path) -> None:
    """D4b: a key absent from this run keeps its stored set untouched.

    Producer asserts on two messages, then a later run re-asserts on only ONE
    of them — the OTHER message's tags must be left alone (no implicit retract).
    """
    md_a = _make_md(tmp_path / "mail", "a.md", message_id="<rs-a@host>")
    md_b = _make_md(tmp_path / "mail", "b.md", message_id="<rs-b@host>")
    for mid in ("<rs-a@host>", "<rs-b@host>"):
        emit_set(tmp_path, key={"message_id": mid},
                 fields={"tags": ["x"]}, emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    assert _tags(md_a) == ["x"] and _tags(md_b) == ["x"]

    # This run reports only message a (dropping x there); b is not reported.
    emit_set(tmp_path, key={"message_id": "<rs-a@host>"},
             fields={"tags": []}, emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    assert _tags(md_a) == []          # a's x retracted
    assert _tags(md_b) == ["x"]       # b untouched — not in this run


@pytest.mark.skipif(emit_set is None, reason="emit_set not implemented yet (id:25ec)")
def test_graceful_read_bootstraps_set_from_legacy_sidecar(tmp_path: Path) -> None:
    """D4d: a schema-1 (additive) sidecar bootstraps the producer's stored set.

    Tags applied via the legacy additive path (no producer_sets block) must be
    retractable by a later declarative emit_set — the stored set is bootstrapped
    from the union of prior applied fields, with no on-disk migration.
    """
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<gr@host>")
    # Legacy additive application: notmuch added a, b via emit() (schema-1 shape).
    emit(tmp_path, key={"message_id": "<gr@host>"},
         fields={"tags": ["a", "b"]}, emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    sidecar = Path(str(md) + _APPLIED_SUFFIX)
    raw = json.loads(sidecar.read_text(encoding="utf-8"))
    # Force a legacy-shaped sidecar: drop any producer_sets block, pin schema 1.
    raw.pop("producer_sets", None)
    raw["schema"] = 1
    sidecar.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    assert sorted(_tags(md)) == ["a", "b"]

    # Declarative re-assert drops 'b'; stored set bootstrapped from legacy applied.
    emit_set(tmp_path, key={"message_id": "<gr@host>"},
             fields={"tags": ["a"]}, emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    assert _tags(md) == ["a"]


@pytest.mark.skipif(emit_set is None, reason="emit_set not implemented yet (id:25ec)")
def test_dry_run_lists_pending_retractions_without_applying(tmp_path: Path) -> None:
    """D3: plan_retractions previews drops; apply_queue(dry_run=True) mutates nothing."""
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<dr@host>")
    emit_set(tmp_path, key={"message_id": "<dr@host>"},
             fields={"tags": ["a", "b"]}, emitted_by="zkm-notmuch")
    apply_queue(tmp_path)
    assert sorted(_tags(md)) == ["a", "b"]

    # queue a retraction of 'b' but preview only
    emit_set(tmp_path, key={"message_id": "<dr@host>"},
             fields={"tags": ["a"]}, emitted_by="zkm-notmuch")
    plan = plan_retractions(tmp_path)
    assert {"md": str(md), "field": "tags", "value": "b",
            "producer": "zkm-notmuch"} in plan
    # dry-run apply must not touch the md or drain the queue
    apply_queue(tmp_path, dry_run=True)
    assert sorted(_tags(md)) == ["a", "b"]

    # real apply now performs the drop
    apply_queue(tmp_path)
    assert _tags(md) == ["a"]
