# 2026-05-10 — TODO audit + N9a entity value normalization

**Started:** 2026-05-10 16:27
**Session:** 94db7a96-e8e1-44bd-a7f5-6a5dd0eaf1d9
**Attendees:** Zommuter (user), audit only — no persona session required
**Topic:** Default-mode TODO audit; Class 1 item dispatched to implementation.

## Agenda

1. Classify open TODO items by impl-readiness.
2. Dispatch head-1 of highest-priority class.

## TODO classification

### Class 1 — impl-ready
- **N9a** — strip whitespace from entity `value` strings (`patterns.py` + `spacy_backend.py`)
- **N10** — write `docs/ner.md` + update `docs/entity-model.md` + `CLAUDE.md`
- **N11** — one-paragraph PII design note in `docs/entity-model.md`
- **Journald rate-limit** — `--ratelimit-interval 0` in `plugins/zkm-eml/hooks/post-commit`

### Class 3 — meeting-worthy
- **N9b** — email-header stoplist design decision (pilot window closes 2026-06-05)
- **Session 15** — WhatsApp scoping meeting
- **Plugin-specific deps** — subprocess isolation vs. uv-run scoping meeting
- **Derivable-but-expensive data in git** — extraction-cache gitignore design meeting

Candidate selected: **N9a** (clear pilot-data bug, unblocks cleaner pilot results).

## Decisions

- Normalize `Entity.value` in `Entity.__post_init__` (covers all extractors, not just patterns + spaCy).
- Regression tests added in `test_patterns.py` (2 cases: trailing newlines, leading+trailing whitespace) and `test_spacy_backend.py` (1 case: no whitespace on real extraction result).

## Action items

- [x] `plugins/zkm-ner/src/zkm_ner/_types.py` — add `__post_init__` stripping `self.value`
- [x] `plugins/zkm-ner/tests/test_patterns.py` — `test_entity_value_strips_trailing_newlines`, `test_entity_value_strips_leading_and_trailing_whitespace`
- [x] `plugins/zkm-ner/tests/test_spacy_backend.py` — `test_spacy_entity_values_have_no_surrounding_whitespace`
- [ ] N9b design meeting before 2026-06-05 (pilot window closes)
