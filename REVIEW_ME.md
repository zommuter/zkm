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
