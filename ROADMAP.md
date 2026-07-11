# Roadmap <!-- fables-turn roadmap v1 -->

Executor-facing task spec. Each item is sized for ONE Sonnet session. Items are
the single source of truth — TODO.md carries only a summary line. Executors tick
checkboxes; only the reviewer adds, removes, or re-scopes items.

**Scope rule for this repo**: every item below is runnable in the zkm core repo
alone — `plugins/` is empty in a fresh worktree and the suite must stay green
without any plugin repo present. Plugin-repo work stays in TODO.md (central
ledger by design) and is NOT mirrored here.

## Phase 2 "done" definition (CONFIRMED — owner 2026-06-13)

Phase 2 is declared done when all three hold:

1. **γ schema shipped** — DONE (E1–E13 closed 2026-05-21).
2. **Store hygiene + management landed** — DONE (`zkm rm`/`zkm gc` dry-run-first,
   `zkm remote/clone/push/pull` backend-aware).
3. **Observation-period gate** — 14 consecutive days of real-store operation
   (mbsync-triggered converts + manual index/search) with zero manual
   interventions for data integrity (no orphaned CAS objects beyond `zkm gc`
   dry-run noise, no sidecar duplicate-producer recurrences, no run-guard
   false positives). Clock starts when the last [ROUTINE] item below ships;
   any intervention restarts the window.

Rationale: 1–2 are already true, so the binding criterion is 3 — it follows the
"observe before preventing" heuristic and avoids declaring victory on the same
day the last feature merges. FP-rate targets for NER are explicitly NOT part of
the gate (N9c/N9d accepted-as-is decisions stand).

## Items

## Pointers (NOT executor items — wrong repo or gated)

- zkm-whatsapp W-series (W6f media manifest, W-key secret source, W8 owner-JID
  autodetect, W10 Syncthing auto-decrypt, W11 number-change tracking) — live in
  `plugins/zkm-whatsapp` (own repo). W9 WAL-safe backup handling shipped
  v0.3.0 (2026-06-11); no core-side blocker remains.
- NER FP backlog (N9c pipe-cell filter, HTML-entity artefacts) — fix paths are
  in zkm-ner / zkm-eml repos per TODO.md; core `scrub.py` is only the dispatcher.
- SOC1–SOC6 zkm-social — gated on GitHub remote + user review (TODO id:e395).
- Stage 2 OIDC trusted publishing — cross-repo CI work across all 7 repos.
