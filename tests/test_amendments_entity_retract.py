"""RED spec for declarative set-retraction applied to ENTITIES (id:29ac).

# roadmap:29ac

`emit_set` retraction currently only applies to the `tags` field (`_SET_FIELDS =
("tags",)`). For zkm-ner scrub↔cache coherence (meeting D1, id:7b4e) the same
ref-count-to-zero removal must apply to the `entities` field. Entities are typed
records `{scope, type, value}` (NOT bare strings), so adding `"entities"` to
`_SET_FIELDS` requires keying the producer-set diff by the `(scope, type, value)`
tuple (the same dedup key `merge_fields` already uses), not by string identity.

This file is RED until id:29ac ships. Design:
docs/meeting-notes/2026-06-23-1807-zkm-amendments-removal-coherence.md (D1).
"""

from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

emit_set = pytest.importorskip("zkm.amendments").__dict__.get("emit_set")

from zkm.amendments import apply_queue  # noqa: E402


def _make_md(directory: Path, filename: str, *, message_id: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    post = frontmatter.Post(
        "body text",
        source="zkm-eml",
        date="2026-05-08T12:00:00+00:00",
        message_id=message_id,
        entities=[],
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


def _entity_keys(md_path: Path) -> set:
    ents = frontmatter.load(md_path).metadata.get("entities", []) or []
    return {(e.get("scope", "body"), e["type"], e["value"]) for e in ents}


@pytest.mark.skipif(emit_set is None, reason="emit_set not implemented yet (id:25ec)")
def test_entity_sole_producer_dropped_when_unasserted(tmp_path: Path) -> None:
    """Producer asserts two entities then re-asserts one; the dropped one
    ref-counts to zero across producers and is removed from frontmatter."""
    md = _make_md(tmp_path / "mail", "msg.md", message_id="<e1@host>")
    e_iban = {"scope": "body", "type": "iban", "value": "CH9300762011623852957"}
    e_date = {"scope": "body", "type": "date", "value": "2026-05-08"}

    emit_set(tmp_path, key={"message_id": "<e1@host>"},
             fields={"entities": [e_iban, e_date]}, emitted_by="zkm-ner")
    apply_queue(tmp_path)
    assert _entity_keys(md) == {
        ("body", "iban", "CH9300762011623852957"),
        ("body", "date", "2026-05-08"),
    }

    # scrub removed the iban; producer now asserts only the date.
    emit_set(tmp_path, key={"message_id": "<e1@host>"},
             fields={"entities": [e_date]}, emitted_by="zkm-ner")
    apply_queue(tmp_path)
    assert _entity_keys(md) == {("body", "date", "2026-05-08")}


@pytest.mark.skipif(emit_set is None, reason="emit_set not implemented yet (id:25ec)")
def test_entity_kept_when_other_producer_still_asserts(tmp_path: Path) -> None:
    """An entity another producer still asserts survives one producer's retraction
    (D2 ref-count-to-zero, keyed on (scope,type,value))."""
    md = _make_md(tmp_path / "mail", "msg2.md", message_id="<e2@host>")
    e_person = {"scope": "body", "type": "person", "value": "Alice"}

    emit_set(tmp_path, key={"message_id": "<e2@host>"},
             fields={"entities": [e_person]}, emitted_by="zkm-ner")
    emit_set(tmp_path, key={"message_id": "<e2@host>"},
             fields={"entities": [e_person]}, emitted_by="zkm-eml")
    apply_queue(tmp_path)
    assert _entity_keys(md) == {("body", "person", "Alice")}

    # zkm-ner drops it (scrub false-positive); zkm-eml still asserts -> kept.
    emit_set(tmp_path, key={"message_id": "<e2@host>"},
             fields={"entities": []}, emitted_by="zkm-ner")
    apply_queue(tmp_path)
    assert _entity_keys(md) == {("body", "person", "Alice")}
