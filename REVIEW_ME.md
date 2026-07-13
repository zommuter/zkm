# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [x] **Three OPEN TODO items carry gate vocabulary but no typed `gated-on:` edge**
  (`orphan-scan.sh --shipped` UNMARKED-GATE, id:46f6): id:c63c (density-ratio pilot,
  "gated, OPEN"), id:f1cf (forward-flag `@{u}` done-gate script, "Gate: next todo-update
  revision OR second need"), id:3174 (subject-clouds overlap, "GATED on slice-0 miss-set
  non-empty"). Each states its gate in prose but lacks the machine-readable `gated-on:`
  sibling comment the typed-ledger reconciler reads. Add a typed `gated-on:` edge to each
  (or confirm the gate is intentionally prose-only) so closure-tracking sees them. Advisory
  — report-only, does not block. (relay review 2026-07-11)
  **RESOLVED 2026-07-11 (/meeting) — confirmed intentionally prose-only.** The `gated-on:`
  marker is id-typed: `orphan-scan.sh:295-311` parses `<!-- gated-on:d,e -->` as TODO-id
  tokens and checks each against local `[x]` state. All three gates are **external-condition**
  gates, not TODO-id dependencies — c63c: labeled-PDF-corpus evidence; f1cf: skill-revision-
  or-2nd-need; 3174: slice-0 miss-set data. None depends on another local TODO id, so an
  id-typed `gated-on:` edge does not apply; the prose gate is correct. NOTE: the UNMARKED-GATE
  backstop has no non-hacky suppressor for external-condition gates and will re-fire on these
  each `--shipped` scan — a durable `prose-only confirmed` marker for orphan-scan.sh is routed
  to dotclaude-skills so the loud detector shrinks rather than re-litigating. See
  docs/meeting-notes/2026-07-11-2132-inventory-data-scope.md (Amendment session).

- [ ] **CI `ruff check` tier is RED (122 errors) — PRE-EXISTING, not this window.**
  (relay review 2026-07-12) The `.github/workflows/ci.yml` Lint step runs
  `uv run ruff check`; against the locked ruff 0.15.10 it reports 122 violations
  (78 E501 line-too-long, 24 I001 import-order, 7 UP017, 6 UP035, 3 F401, 2 UP037,
  1 F841, 1 F541). This is repo-wide lint debt from ruff-version drift (pin `>=0.4`
  → locked 0.15.10), **NOT introduced by this window's commits**: the changed source
  files carry the *same* count at the checkpoint tree (`cli.py` 13 both, `convert.py`
  2 both, `store.py` 0 both — id:998b added zero lint errors). The pytest tier is
  fully green (628 passed). Decide: run `ruff check --fix` for the 43 auto-fixable
  (I001/F401) + address E501, or relax the ruff config — either way the CI Lint step
  fails today. Advisory — does not block this review (pytest green, work verified
  genuine).
  — DECIDED 2026-07-13 (relay human): FIX + E501 path — run `ruff check --fix` (43 auto: I001/F401) then manually resolve the 78 E501 line-too-long; do NOT relax config or pin an older ruff. Re-lane as [ROUTINE] executor work.
