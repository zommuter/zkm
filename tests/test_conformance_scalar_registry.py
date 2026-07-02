"""Red-test spec for the core-owned scalar-key registry warn (ROADMAP id:e2c4).

`zkm test` (conformance.py) must emit a WARN-level finding when an emitted `.md`
carries a bare scalar frontmatter key that is neither in the core-owned scalar
registry (docs/plugin-spec.md registry table, ROADMAP id:4431) nor in the flat
`<plugin>_<key>` plugin-private form. Warn, not fail — existing stores must keep
validating. RED until the registry constant + check land in
`zkm.conformance.validate_frontmatter`.

Frontmatter field governance, TODO id:e2c4 (depends on the id:4431 registry table
for the authoritative key list).
"""

from __future__ import annotations

from zkm.conformance import validate_frontmatter


def _meta(**extra):
    meta = {
        "source": "social",
        "date": "2026-07-02T10:00:00+02:00",
        "tags": ["social"],
        "sha256": "a" * 64,
        "processor": "social",
        "processor_version": "1.0.0",
    }
    meta.update(extra)
    return meta


def test_unregistered_bare_scalar_warns():  # roadmap:e2c4
    findings = validate_frontmatter(_meta(confidence=0.9), "social")
    hits = [f for f in findings if "confidence" in f.message]
    assert hits, "expected a finding naming the unregistered bare scalar 'confidence'"
    assert all(f.level == "warn" for f in hits), [str(f) for f in hits]


def test_plugin_prefixed_scalar_is_private_namespace():  # roadmap:e2c4
    findings = validate_frontmatter(_meta(social_confidence=0.9), "social")
    assert not any("social_confidence" in f.message for f in findings), [
        str(f) for f in findings
    ]


def test_core_owned_scalars_pass():  # roadmap:e2c4
    # registry seed per id:4431: status, subject, project (+ the required keys)
    findings = validate_frontmatter(
        _meta(status="confirmed", subject="Re: invoice", project="zkm"), "social"
    )
    assert not any(
        key in f.message for f in findings for key in ("status", "subject", "project")
    ), [str(f) for f in findings]


def test_non_scalar_values_are_exempt():  # roadmap:e2c4
    # lists/dicts (entities, participants, messages…) are not "bare scalars"
    findings = validate_frontmatter(
        _meta(entities=[{"scope": "doc", "type": "iban", "value": "CH93"}]), "social"
    )
    assert not any("entities" in f.message for f in findings), [str(f) for f in findings]
