# 2026-06-18 — f103: propagate notmuch tag REMOVALS to frontmatter

**Started:** 2026-06-18 19:44
**Session:** 2178c046-0ef3-4010-806a-9cdf8adc7f8a
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🧮 Reni (reconciliation/provenance — new)
**Topic:** How should the zkm amendment engine support retracting a frontmatter field (tag removed in notmuch), attribution-aware and data-loss-safe, across the core↔plugin boundary?

## Surfaced discoveries

- [2026-05-14 zkm] atomic-write makes a single write safe but does NOT make read-modify-write atomic across processes (`sidecar.py` merge_producer race) — directly relevant to retraction sidecar bookkeeping.
- [2026-06-04 zkm] provenance-named fields, never bare `verified: true` — attribution discipline precedent.

## Agenda

1. **Producer model** — additive-emit + tombstone retraction records vs declarative full-asserted-set-per-producer.
2. **Data-loss policy** — auto-remove sole-attributed tag drops vs quarantine ambiguous removals for manual review.
3. **Scope & sequencing** — general `zkm.amendments` retract primitive (N=2?) vs notmuch special-case; confirm core-first / plugin-diff-second split.

## Discussion

### DP1 — Producer model: how is a retraction expressed?

🏗️ **Archie:** Two approaches. **(a) Additive + tombstone:** the plugin computes the diff itself (prior notmuch-attributed tags from the sidecar, minus current notmuch tags) and emits a retraction record — a new subtract-mode merge. Small, incremental, additive path untouched. **(b) Declarative producer-set:** the producer emits its entire current asserted set each run; core stores each producer's last set and computes additions **and** removals by diffing. Idempotent by construction, removal falls out for free — but bigger core change + schema bump.

🧮 **Reni:** "Where does the diff live" is the real question. (a) → every amender re-implements ledger-reading to compute its own delta. (b) → diff lives in core once. Also: `src/zkm/sidecar.py` already implements this machinery for CAS objects (`merge_producer`/`remove_producer`/`rebuild_sidecar` under fcntl lock) — (b) mirrors a pattern the repo already trusts.

😈 **Riku:** (b) has larger blast radius — today's amendments sidecar is append-only log; (b) makes it authoritative per-producer state. And `amendments.py::_apply_to_md` writes the sidecar with no lock (2026-05-14 race). Botched (a) only fails to remove; botched (b) wrongly removes. Hard preconditions: fcntl lock + schema bump + graceful read.

✂️ **Petra:** N=2 justifies a core primitive (notmuch tag-drop + zkm-ner stale-entity-drop, both real near-term). But N=2 decides *locus* (core), not the model — (a)'s tombstone mode is also reusable.

🏗️ **Archie:** Both consumers (notmuch, ner) already emit their whole set naturally. Forcing them to diff means each re-derives prior state from the ledger anyway — (b) moves that unavoidable work to core.

🧮 **Reni:** Middle option: **(b) for removals only** — additions stay set-union (byte-identical), we strictly add a removal computation on the declarative diff.

**DP1 DECIDED:** Declarative producer-set, removals-only.

### DP2 — Data-loss policy: when is removing a tag safe?

🧮 **Reni:** Ref-count-to-zero rule (mirrors `sidecar.py:remove_producer`): drop tag T iff (1) T ∈ producer's stored set, (2) T ∉ producer's new set, (3) T is in no other producer's current set.

😈 **Riku:** Blind spot: a user-hand-typed tag that matches a notmuch tag gets absorbed into notmuch's set — when notmuch drops it, rule (3) passes and we delete user-intended data. The "name is not a UID" identity-conservatism hazard.

✂️ **Petra:** Frequency argument: notmuch removals are constant (`inbox`, `unread`). A mandatory review queue for every tag-drop is unusable. The manual-merge signal is for rare high-stakes identity ambiguity, not tag churn.

🏗️ **Archie:** Reversibility net already exists: every amendment is git-committed + sidecar-recorded. Wrong removal → auditable + recoverable, not silent loss. Offer a non-mandatory `--dry-run` listing so the preview is real.

😈 **Riku:** Concede frequency kills pure quarantine. `--dry-run` at apply time is the minimum bar.

🧮 **Reni:** Free under the declarative model — diff computed before apply, so "would retract: {d} from msg X (sole producer: notmuch)" is free to emit.

**DP2 DECIDED:** Auto-remove + sidecar-audit + non-mandatory dry-run. Reserve quarantine for hypothetical future high-stakes producers (none on roadmap).

### DP3 — Scope & sequencing

✂️ **Petra:** N=2 ratified → core primitive, not notmuch-special-case. Question: staging.

🏗️ **Archie:** Stage 1 (core): declarative-set merge + fcntl lock + schema bump + test suite + tag + publish. Stage 2 (zkm-notmuch, = f103): switch `convert()` to declarative emit against the released API, separate session.

🧮 **Reni:** Migration free — bootstrap stored set for existing mds from legacy append-only sidecar (union of `fields.tags` across `emitted_by == notmuch` applied records). No data rewrite.

😈 **Riku:** Two hard acceptance criteria: (1) empty asserted set for a key = no-op, never bulk-retract (guards failed/empty notmuch dump). (2) diff scoped to keys reported this run; absent keys keep stored set (created-scoping, id:63bb).

✂️ **Petra:** Don't bundle repos — relay convention is one subagent per repo; the cross-repo single turn is exactly what got deferred twice.

**DP3 DECIDED:** General primitive in core, core-first staged.

## Decisions

- **D1 — Declarative producer-set model.** Retraction is implemented in core `zkm.amendments` as a declarative-set merge: a producer emits its full current asserted set (new `asserted_set=` flag on `emit`, or a sibling `emit_set()`); core stores each producer's set per md-key in the attribution sidecar and computes removals by diffing prior-vs-new. Additions stay `merge_fields` set-union, byte-identical. *Out of scope:* rewriting the addition path; the additive+tombstone/delta model.
- **D2 — Ref-count-to-zero removal rule.** Drop tag T from a message's frontmatter iff (1) T ∈ producer's stored set, (2) T ∉ producer's new set, (3) T is asserted by no other producer's current set. Otherwise drop only this producer's claim and keep the tag. Mirrors `sidecar.py:remove_producer` remaining-count semantics. *Out of scope:* cross-producer priority beyond set-presence.
- **D3 — Auto-remove + audit + dry-run.** Removals apply automatically; every retraction is recorded in `<md>.amendments.json` (auditable, git-reversible); non-mandatory `--dry-run` lists pending retractions before apply. *Out of scope:* quarantine queue, per-tag allow/denylist, baseline-snapshot protection, interactive confirm-each.
- **D4 — Hard safety invariants (core acceptance criteria).** (a) A producer that emits no asserted set for a key is a **no-op**, never a bulk-retract. (b) Diff is **scoped to keys reported in the current run** — absent keys keep their stored set, never retracted (created-scoping, id:63bb). (c) Amendments-sidecar writer is **fcntl-locked** (mirror `sidecar.py:_sidecar_lock`; closes the 2026-05-14 race). (d) `_SCHEMA` bumped with **graceful read** of legacy append-only sidecars: stored set bootstrapped from union of prior applied `fields` — no data migration.
- **D5 — General primitive, core-first staged.** N=2: notmuch tag-drop + zkm-ner stale-entity-drop. Stage 1 = core `zkm.amendments` primitive + tag + publish. Stage 2 = `zkm-notmuch` declarative emit (= f103), separate session, against released API. *Out of scope:* bundling both repos; a notmuch-only narrow primitive.

## Action items

- [ ] **[core]** Implement declarative-set retract primitive in `src/zkm/amendments.py`: `emit_set()` / `asserted_set=` mode; per-producer stored set in `<md>.amendments.json`; prior-vs-new diff; ref-count-to-zero removal (D2); sidecar-recorded retractions; non-mandatory dry-run listing; fcntl lock; `_SCHEMA` bump + graceful read/bootstrap from legacy sidecars. Tests: idempotence (apply twice → no-op), no-op-on-empty (D4a), run-scoped diff (D4b), multi-producer keep (D2), graceful-read. Update `docs/plugin-spec.md` + CLAUDE.md multi-producer note. Bump+tag+`uv publish`. *Contract: producer drops a tag from asserted set → removed from frontmatter iff sole producer; legacy sidecar still applies cleanly; empty asserted set retracts nothing.* <!-- id:25ec -->
- → routed to zkm-notmuch inbox (Stage 2 = f103 implementation, design resolved here) <!-- routed:8b00 -->
