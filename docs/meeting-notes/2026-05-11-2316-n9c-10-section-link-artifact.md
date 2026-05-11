# 2026-05-11 — N9c-10: Section N] markdown link-target artifact filter

**Started:** 2026-05-11 23:16
**Session:** 26a67bed-3383-4a0a-8db0-b32852c65261
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Add textfilter rule to drop `Section N]` NER false positives (class 7 pollution).

## Context

The N9d-β re-pilot (2026-05-11) classified 571+ misc-type entities matching `Section N]` as
closed-set FPs — broken markdown link-target fragments produced by the zkm-eml converter
(`[Section 5](url)` → `Section 5]` after the opening bracket is lost). The N9d warrant-check
meeting explicitly noted this as "fixable with textfilter before N9d design meeting."

Actual corpus count at fix time: **936** entities (with `]`), some with trailing spillage
(`Section 5]\n\n++ Footer\n\nSocial Media`). The root cause is in zkm-eml's markdown link
parser; fixing that would require re-rendering 55k mails and is deferred.

## Plan

Mirror the N9c-8 / N9f shape:

1. `_RE_SECTION_LINK_ARTIFACT = re.compile(r"^Section\s+\d+\]")` in `textfilter.py` (anchored
   at start — catches any trailing content including newlines and continued markdown).
2. `drop_section_link_artefacts(entities)` function in the same file.
3. Wire into `extract.py` post-filter chain next to `drop_structural_artefacts`.
4. Extend `scrub()._is_scrub_candidate` in `convert.py` with the same regex.
5. Bump cache key `+textfilter-v4` → `+textfilter-v5` in `version.py`.
6. 8 new tests in `tests/test_textfilter.py` (5 positive, 3 negative + empty-list).
7. Bump `pyproject.toml` 0.4.1 → 0.5.0; tag `v0.5.0`.

Without closing `]`: `Section N` values are ambiguous vs. legitimate legal/standard references
(e.g. `Section 5.1 & 6.5`) — left to N9d / LLM verifier.

## Implementation findings

- All 124 tests pass (96 prior + 8 new).
- Committed `5a504ab` in `plugins/zkm-ner/`, tagged `v0.5.0`.
- Live cleanup (`zkm convert ner` → cache bust, 55k files) in progress at meeting-note write
  time; `zkm scrub ner --apply` and pilot re-run to follow once convert completes.
- Pilot grep for `Section [0-9]*\]` expected to return 0 post-scrub.

## Decisions

- `Section N]` (closing bracket present) → drop unconditionally (closed-set, no ambiguity).
- `Section N` (no bracket) → do not filter (could be a legitimate section reference).
- Root cause in zkm-eml (broken link parser) → deferred; would require 55k-mail re-render.
- Scope: post-extraction filter only, same as all prior N9 rules.

## Action items

- [ ] After `zkm convert ner` finishes: `zkm scrub ner --apply`; verify `entities_removed ≈ 936`.
- [ ] Re-run `bash plugins/zkm-ner/scripts/pilot.sh`; confirm `Section N]` absent from top-N.
- [ ] Update `TODO.md`: add N9c-10 sub-item; remove the "may be fixable with textfilter" note from N9d entry; add `docs/object-storage.md reconciliation` orphan.
- [ ] Push `plugins/zkm-ner/` (main + v0.5.0 tag) to fievel.
- [ ] Update `docs/meeting-notes/meeting-style.md` past-meetings index.
