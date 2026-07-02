"""Red-test spec for url_sha256 as the source=social identity hash (ROADMAP id:1e4f).

`source: social` docs carry `url_sha256:` (hash of the normalized profile URL —
an IDENTITY-ONLY dedup key, zkm-social D4 / plugin roadmap id:72ef) instead of the
byte-content `sha256:`. Core conformance must accept `url_sha256` as satisfying the
hash requirement for source=social documents, while every other source keeps
requiring the byte `sha256`. RED until `zkm.conformance.validate_frontmatter`
learns the source=social exemption.

Inbox routed:7f55; core half of TODO id:1e4f (the zkm-social transitional-dup
removal in _github.py/_linkedin.py is plugin-repo follow-up, not this item).
"""

from __future__ import annotations

from zkm.conformance import validate_frontmatter


def _social_meta(**overrides):
    meta = {
        "source": "social",
        "date": "2026-07-02T10:00:00+02:00",
        "tags": ["social"],
        "url_sha256": "a" * 64,
        "processor": "social",
        "processor_version": "1.0.0",
    }
    meta.update(overrides)
    return {k: v for k, v in meta.items() if v is not None}


def test_social_doc_with_url_sha256_needs_no_sha256():  # roadmap:1e4f
    findings = validate_frontmatter(_social_meta(), "social")
    assert not any("sha256" in f.message for f in findings), [str(f) for f in findings]


def test_social_doc_with_neither_hash_fails():  # roadmap:1e4f
    findings = validate_frontmatter(_social_meta(url_sha256=None), "social")
    assert any(
        f.level == "fail" and "sha256" in f.message for f in findings
    ), [str(f) for f in findings]


def test_non_social_source_still_requires_byte_sha256():  # roadmap:1e4f
    # url_sha256 does NOT substitute for sha256 outside source=social
    meta = _social_meta(source="pdf", processor="pdf")
    findings = validate_frontmatter(meta, "pdf")
    assert any(
        f.level == "fail" and "sha256" in f.message for f in findings
    ), [str(f) for f in findings]
