# 2026-05-11 — N9d / N9e warrant check

**Started:** 2026-05-11 22:18
**Session:** f035707b-c19d-4c41-b205-b57dac430241
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🧠 Mira (multimodal ML — classifier cost, failure modes, privacy) (re-onboarded)
**Topic:** Design the LLM verifier path (N9d) and the closed-loop heuristic↔verifier feedback (N9e), or determine that N9f's deterministic floor makes them unnecessary.

## Agenda

1. Warrant check — does N9d still earn its keep post-N9f?
2. Pilot protocol + trigger threshold (replaces deferred items 2–6).
3. Action items.

(Original agenda items 3–6 — mechanics, model/prompt, N9e schema, sequencing — deferred: contingent on pilot evidence.)

## Discussion

### Item 1 — Does N9d still earn its keep post-N9f?

🏗️ Archie laid out the state post-N9f: total mentions 760k → 340,431 (-55%). Top-of-list now reads as legitimate entities (Google LLC ×3204, PayPal ×1892, Amazon WS ×1074, SBB ×542, ETH ×485). `Tobias Kienzler` ×11,279 is **own-name signature pollution** — out of NER's scope, fix is `zkm-eml` signature stripping (already on TODO). The previously identified residual FP classes (per N9c-6) are: (a) own-name (Class C, deferred), (b) boilerplate legal text in ORG (`L-2449 Luxembourg RCS Luxembourg` ×859, deferred), (c) multi-word phrase FPs (`Hallo Tobias`, `Best Regards`) — these were the N9d trigger, but N9f already cleaned them.

😈 Riku flagged the warrant gap: TODO entry for N9d says "LLM verifier on residuals after N9d-α and N9f (if triggered)." The trigger is a post-N9f re-pilot showing residual pollution the deterministic floor missed. **No such pilot has been run.** The meeting is being held against an unknown.

✂️ Petra applied the N=2 rule: two distinct consumers for an LLM-verifier mechanism would be (1) NER residuals after N9f (unmeasured), (2) … no second consumer nearby. zkm-claude-code / zkm-claude-ai are at scoping stage and not amender-shaped. N=1 hypothetical until evidence lands.

🧠 Mira added the ML-cost lens: at 340k mentions, even a cheap local LLM at 30 tok-in / 5 tok-out × ~200 ms = ~19 hours wall-clock for one pass. Caching by `(value, type)` dedups heavily (top-20 cover ~30k entries) but cold-start still walks the long tail. Pre-empted the empirical-pilot pattern: re-pilot first; let residuals decide whether N9d is even the right tool.

🏗️ Archie + 😈 Riku converged on (A): run the existing `plugins/zkm-ner/scripts/pilot.sh` against the current corpus, inspect residuals, **then** decide. 😈 Riku added the open-set vs closed-set distinction: stoplist beats verifier whenever the FP class is finite/enumerable; verifier only wins on open-set fuzzy noise.

**Item 1 decision:** **(A) Re-pilot first.** Design deferred until residuals are visible. Agenda items 3–6 do not apply in this meeting.

### Item 2 — Pilot protocol and open-set trigger threshold

🏗️ Archie described the pilot mechanics: `pilot.sh` → `pilot.py` reads frontmatter only (no extraction, no LLM, no cache miss); produces type histogram, top-N per type, suspicious-value dump via `_is_suspicious` (short ≤2 chars, single-token misc, all-caps acronyms, person-with-lowercase-start). Cost ~1 minute over 47k md files.

😈 Riku insisted on a numeric trigger declared *before* looking at the data, to avoid re-meeting on vibes:
- **Closed-set** = top-N FPs fit into a finite enumerable phrase list (≤30 entries) covering ≥80% of FP volume → resolve with a 6th-iteration stoplist.
- **Open-set** = fuzzy / long-tailed; no finite list captures ≥80% in under 100 entries → LLM verifier is the right tool.

✂️ Petra added a volume floor: if total FP residual is ≤0.5% of mentions (~1700 entries on 340k), defer N9d regardless of shape. The cost of building infra exceeds the recall cost of leaving FPs in place. Re-open only on (open-set shape) **AND** (≥0.5% volume).

🧠 Mira raised non-stationarity: current corpus is 95% German mail-dominant. When zkm-claude-code / zkm-claude-ai lands, the corpus shifts to mixed-language conversational text; FP distribution may shift too. N9d's warrant **must be re-evaluated post-import** of any conversational corpus, regardless of today's pilot result. N9e schema design is held until N9d's warrant is established.

🏗️ Archie defined the artefact protocol: timestamped output (no overwrite); 5-bucket manual classification of top-50 per type.

😈 Riku confirmed the cache state: post-N9f convert applied in-pipeline POS filter (model_version `+textfilter-v4+posfilter-v1`); cache is current; pilot reads frontmatter not cache; safe to run.

## Decisions

- **N9d/N9e design deferred** to a future meeting, gated on pilot evidence.
- **Trigger condition** for re-opening N9d design: **(open-set shape: no ≤30-entry phrase list captures ≥80% of FP volume) AND (≥0.5% of total mentions, i.e. ≥~1700 entries on a 340k corpus).** Both required.
- **Pilot artefact protocol**: output to `<store>/.zkm-state/ner-pilot-review-YYYYMMDD-HHMM.jsonl` (timestamped, no overwrite); manually classify top-50 per type into one of five buckets: `legit | own-name | boilerplate-legal | closed-set-FP | open-set-FP`; tally volumes; apply threshold.
- **Non-stationarity rider**: N9d warrant **must** be re-evaluated after any non-mail amender plugin (zkm-claude-code, zkm-claude-ai, …) lands and produces frontmatter at scale, regardless of today's outcome. N9e schema design is held until N9d warrant is established post-amender.
- **Explicitly out of scope**: own-name signature stripping (separate TODO, `zkm-eml`), boilerplate-legal gating (Class B, deferred at N9c-6), GLiNER-as-default (already failed at N9d-α), N9e closed-loop schema design (gated on N9d warrant).

## Action items

- [ ] Patch `plugins/zkm-ner/scripts/pilot.py` (or its `pilot.sh` wrapper) so the review JSONL output path is timestamped (`ner-pilot-review-YYYYMMDD-HHMM.jsonl`), no overwrite of prior runs. Single-line change; verify by re-running pilot twice without `-f`/clobber.
- [ ] Run `plugins/zkm-ner/scripts/pilot.sh` against the current 340k-mention store; capture the artefact path.
- [ ] Eyeball-classify top-50 per type into 5 buckets (`legit | own-name | boilerplate-legal | closed-set-FP | open-set-FP`); tally per-bucket volume.
- [ ] Apply trigger: if (open-set ≥80% miss on ≤30-entry list) AND (≥0.5% volume) → reopen N9d design meeting with the residuals attached; else → close N9d in TODO.md with a one-line rationale citing this note.
- [ ] Update TODO.md N9d/N9e entries with the trigger threshold + non-stationarity rider so the next session has unambiguous criteria.
- [ ] (Orphan cleanup, separate from meeting outcome) Mark TODO.md `N9c` parent and `N9d-α` parent checkboxes as `[x]` — all sub-items are complete.
