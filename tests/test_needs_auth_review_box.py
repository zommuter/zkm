# roadmap:cf18
"""Red-test spec for the `@needs-auth` REVIEW_ME box (ROADMAP id:cf18).

INBOUND routed:9b68 from dotclaude-skills id:1750. The 2nd-annex-copy step
(TODO id:0b37 — `git annex copy --to <fievel-annex-remote>` against the real
`~/knowledge` store) is blocked on a human-held credential a relay child cannot
supply unattended. That wall must be recorded as a conforming `@needs-auth` box in
this repo's REVIEW_ME.md so the offline lister
(dotclaude-skills `gather-human-backlog.sh --needs-auth`) surfaces it. RED until
the box lands.

The `@needs-auth` convention (dotclaude-skills `relay/references/hard-lanes.md`
§"The `@needs-auth` marker", id:a505) mandates FOUR fields per box:
  what-secret / where-it-goes / exact-command / why.

What this test can and cannot do (honesty about the instrument):
  - It pins the *structural* contract of the box: the `@needs-auth` marker, a
    reference to the blocked work (id:0b37), all four mandatory field labels, the
    `git annex copy --to` exact-command, and the single-store "why". A box that
    drops the marker, forgets a field, or loses the 0b37 link fails here.
  - It does NOT verify the credential works or that any copy succeeds — that is
    the human run-half (id:0b37 / id:5f86), out of scope for this prose item.

Triangulation: the specs assert several DISTINCT properties (marker, back-link,
each of the four field labels, the command, the rationale) so that satisfying the
letter of one assertion cannot pass the others without writing the real box.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_ME = REPO_ROOT / "REVIEW_ME.md"


def _review_me_text() -> str:
    assert REVIEW_ME.exists(), f"{REVIEW_ME} is missing"
    return REVIEW_ME.read_text(encoding="utf-8")


def _needs_auth_block() -> str:
    """Return the text of the top-level bullet block carrying the @needs-auth marker.

    A REVIEW_ME box is a top-level `- [ ]`/`- [x]` bullet plus its indented
    continuation lines, up to the next top-level bullet or a heading. We isolate
    the block that contains `@needs-auth` AND references 0b37 so the field-label
    assertions below cannot be satisfied by unrelated boxes elsewhere in the file.
    """
    text = _review_me_text()
    lines = text.splitlines(keepends=True)
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        is_top_bullet = bool(re.match(r"^- \[[ x]\]", line))
        is_heading = line.startswith("#")
        if is_top_bullet or is_heading:
            if current:
                blocks.append("".join(current))
            current = [line] if is_top_bullet else []
        elif current:
            current.append(line)
    if current:
        blocks.append("".join(current))

    matching = [
        b for b in blocks if "@needs-auth" in b and re.search(r"\b0b37\b", b)
    ]
    assert matching, (
        "no REVIEW_ME box carries both the `@needs-auth` marker and a reference to "
        "id:0b37 — the second-annex-copy auth wall is not recorded yet"
    )
    assert len(matching) == 1, (
        f"expected exactly one @needs-auth box for 0b37, found {len(matching)}"
    )
    return matching[0]


def test_needs_auth_marker_present() -> None:
    """The REVIEW_ME box must carry the literal `@needs-auth` marker token."""
    assert "@needs-auth" in _review_me_text(), (
        "REVIEW_ME.md carries no `@needs-auth` marker — the offline lister and "
        "roadmap-lint recognise the box only by that token"
    )


def test_box_references_blocked_work_0b37() -> None:
    """The box must link back to the blocked work (TODO id:0b37) for traceability."""
    block = _needs_auth_block()
    assert re.search(r"\b0b37\b", block), (
        "the @needs-auth box does not reference id:0b37 (the git-annex 2nd-copy step)"
    )


@pytest.mark.parametrize(
    "field_label",
    ["what-secret", "where-it-goes", "exact-command", "why"],
)
def test_box_carries_all_four_mandatory_fields(field_label: str) -> None:
    """All four mandatory @needs-auth field labels must appear in the box."""
    block = _needs_auth_block()
    assert field_label in block, (
        f"the @needs-auth box is missing the mandatory `{field_label}` field "
        "(convention: what-secret / where-it-goes / exact-command / why)"
    )


def test_exact_command_is_git_annex_copy_to() -> None:
    """The exact-command field must name the real unblock command from 0b37."""
    block = _needs_auth_block()
    assert re.search(r"git annex copy\s+--to", block), (
        "the exact-command must be `git annex copy --to <fievel-annex-remote>` "
        "(the concrete step id:0b37 is blocked on), not a paraphrase"
    )


def test_why_states_the_single_store_risk() -> None:
    """The `why` must explain what strands: the store is otherwise single-copy."""
    block = _needs_auth_block().lower()
    assert "single-copy" in block or "single copy" in block or "one disk" in block, (
        "the `why` field must state the stranding risk — the store stays single-copy "
        "('one disk = total loss') without the 2nd annex copy"
    )
