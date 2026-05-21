# 2026-05-21 — γ schema E1–E14 gap audit

**Started:** 2026-05-21 08:16
**Session:** 16129970-6ba5-4c3d-9ad5-96d600ccf537
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Reconcile why the γ schema E1–E14 items are absent from TODO.md and determine what (if anything) to add.

## Context

The no-arg `/meeting` invocation flagged the γ schema rollout as a gap: the
`2026-05-12-1500-entity-vs-datamining.md` meeting defined a 14-item E1–E14 sequence, but
**none of the E items appear as `[ ]` entries in `TODO.md`**.

The sequencing from that meeting: E1+E2+E3 (schema + amendments + normaliser) → E4
(suspicious dispatch) → E6 (`amount` pilot) → E7 (more value-types) → E8+E9 (P2 index
integration + field-test). Effort estimate: ~6–8 sessions.

## Plan

Audit each E item by reading the meeting note for its spec and cross-checking the current
codebase state. For each item: DONE / PARTIALLY DONE / OPEN. Then decide, per the drift-
aversion principle, whether to add done-checkboxes (clutter) or a minimal status summary +
only the genuinely-open items.

## Implementation findings

All five γ-schema structural areas were verified by reading source:

| Item | Description | State | Evidence |
|------|-------------|-------|----------|
| E1 | `entities[]` typed-slot dataclass (scope/canonical/standard/unit/valid) | **DONE** | `plugins/zkm-ner/src/zkm_ner/_types.py:8-53` |
| E2 | amendments dedup key → `(scope,type,value)` | **DONE** | `src/zkm/amendments.py:135-157` |
| E3 | `zkm.canonical` module (iban/amount/email/phone/iso8601) | **DONE** | `src/zkm/canonical.py` |
| E4 | `suspicious.py` `_PREDICATES` dispatch table | **DONE** | `plugins/zkm-ner/src/zkm_ner/suspicious.py:70-97` (iban/amount stubs are by design; validity enforced at extraction time in `patterns.py:264-270`) |
| E5 | `verify_gamma_migration.py` pre-v1.x hard-gate | **DONE** | `plugins/zkm-ner/tests/test_verify_gamma_migration.py` |
| E6 | `amount` extractor pilot | **DONE** | `plugins/zkm-ner/src/zkm_ner/patterns.py:305` |
| E7 | more value-types: iban, email, phone, url, invoice_id, tracking_id, registration | **DONE** | all 8 extractor functions present in `patterns.py`, wired through `extract_all` |
| E8 | P2 index integration (BM25 + dense, entities + participants) | **DONE** | `src/zkm/index.py:68-80`, `src/zkm/embed.py:376-392` (7b tokenize bug found and fixed during step 7) |
| E9 | P2 field-test pilot | **MOSTLY** | step 7 logged live results 2026-05-12 in `docs/field-test-bge-m3.md`; **7c typed-value query probe + embed rebuild explicitly deferred** — extractors (E6/E7) landed after the last `zkm convert ner` run, so the mail corpus `entities[]` doesn't yet contain IBAN/amount entries |
| E10 | redactor scope design note in `docs/entity-model.md` | **DONE** | `docs/entity-model.md:98-104` |
| E11 | docs contract tables (valid-types table + provenance-scopes table) | **DONE** | `docs/entity-model.md:51` (types), `:74` (scopes) |
| E12 | N9g-pre — signature/salutation γ-scope extraction in zkm-eml | **DONE** | `plugins/zkm-eml/src/zkm_eml/render.py:42-74`, `frontmatter.py:27-65` |
| E13 | N9g re-evaluation (after γ + per-type extractors + P2 land) | **OPEN** | all gates satisfied; re-audit residual body-NER FPs; expected close-as-moot |
| E14 | promote E1–E13 into `TODO.md` | **NOT DONE** | the entire gap |

**Root cause:** E14 itself was the bookkeeping step that would have added the other E items to
`TODO.md`. It was never run, which is why all E items appear absent. The work was done; only the
ledger update was skipped. This is the known pattern where `todo-update` doesn't reliably capture
closures made in mid-session or adjacent sessions (per `docs/meeting-notes/2026-05-14-2016-disable-orphan-scan.md`).

**Chosen approach:** minimal — one-line status summary ("γ rollout COMPLETE (E1–E12)") + two
genuinely-open `[ ]` items. No done-checkboxes (drift-aversion: don't add a third copy of
information already canonical in code + git log).

## Decisions

- **γ rollout is substantially complete.** E1–E12 all shipped; the gap was purely bookkeeping.
- **Minimal reconciliation chosen over full E1–E13 checklist.** Adding 12 done-checkboxes would
  be redundant state — canonical evidence is in code + git log. Out of scope: running `zkm convert
  ner` or embed rebuild in this session (filed as a TODO item instead).
- **Two live TODO items added:** E9-followup (re-run convert + embed rebuild + 7c probe) and E13
  (N9g re-evaluation, now unblocked).
- **E prefix table in `CLAUDE.md` retained as-is** — the E prefix already exists; with <3 open
  items the ≥3-threshold rule no longer applies, but removing the row is unnecessary churn.

## Action items

- [ ] **E9 follow-up:** `zkm convert ner` (cache-bust) → rebuild dense embed index → run 7c typed-value probe. See `docs/field-test-bge-m3.md` step 7c. Contract: IBAN search returns source doc via `entities[]`.
- [ ] **E13:** re-audit residual body-NER false positives; expected close-as-moot. See `docs/meeting-notes/2026-05-12-1500-entity-vs-datamining.md`.
