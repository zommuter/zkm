# 2026-05-11 — NER: next after N9b

**Started:** 2026-05-11 09:46
**Session:** 2777a347-4ec9-49b0-b447-7e630d9f6b28
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🧠 Mira (ML quality — NER POS-filter lens), Zommuter (user)
**Topic:** What's next for zkm-ner after N9b cleanup landed — `zkm status` invisibility observation, N9c design (common-noun FP filter), remaining NER items (N10/N11), CLAUDE.md version-mention drift.

## Agenda

1. `zkm status` didn't show `zkm convert zkm-ner` during a direct run — bug vs. expected?
2. N9c common-noun FP filter — POS-filter, denylist, or hybrid?
3. Remaining NER items — N10 docs, N11 PII, CLAUDE.md version orphan.

## Past meetings audit

- Scrub CLI meeting (2026-05-10-2142): Sc1–Sc9 done. **Sc10 orphan:** `CLAUDE.md:116` still says `currently 0.2.0` but pyproject is `0.3.0`. Fold into N10/CLAUDE.md cleanup.
- All other recent NER meeting action items tracked or done.

## Discussion

### Item 1 — `zkm status` invisibility

**🏗️ Archie:** Wiring is correct — `cmd_convert` at `cli.py:455` enters `RunSession(sdir, "convert", args=[plugin])`; `session.tick()` fires per file via `progress_cb`; zkm-ner's `convert()` calls `progress(i, total, ...)` at `plugins/zkm-ner/convert.py:58-59`. PID file should be visible throughout a direct run.

Three candidate explanations: (a) fully-warm cache — every body sha256 hits extraction cache, loop is frontmatter.load + cache.get + return; still 5–15 min wall time. (b) `ZKM_STORE` mismatch across shells. (c) Real bug in PID file lifecycle.

Clarification: if run was triggered via post-commit hook chain (mbsync → `zkm convert zkm-eml` → amender chain), `zkm status` would show `convert(zkm-eml)` for the whole duration — amenders run inside the parent RunSession at `cli.py:513-519` without their own session. That's expected.

**😈 Riku:** n=1, uncontrolled. "Observe before preventing" — no instrumentation without evidence.

**✂️ Petra:** Cheapest evidence: next NER run, parallel `zkm status` in a second terminal. Log-and-wait as TODO.

**User:** Direct standalone invocation. Log-and-wait.

### Item 2 — N9c common-noun FP filter design

**🧠 Mira:** POS map of user-listed FPs: PRON/VERB/NOUN cluster (`Du`, `wünschen`, `Zeit`, `Internet`, `EUR`, `CHF`) — caught by PROPN-only filter. PROPN cluster (`UTC`, `MESZ`, `CEST`, `CV`, `AGB`, `HRB`) — needs closed-set denylist. Implementation locus: `plugins/zkm-ner/src/zkm_ner/extract.py`, after `nlp(text)`, before pattern overlay merge.

Risk: PROPN-only filter has false negatives on German common-noun-headed org names (e.g. "Bank Vontobel" — root `Bank/NOUN`). Empirically low in mail corpora; must measure via re-pilot.

**🏗️ Archie:** Two symmetric mechanisms: (1) POS-filter `_pos_filter(ent)` keeping `ent.root.pos_ == "PROPN"` on spaCy NER outputs only (pattern overlay bypasses — pre-typed). (2) `_COMMONNOUN_STOPLIST` in `textfilter.py`, parallel to N9b `_STOPLIST`. One cache invalidation: bump `model_version` to `+textfilter-v1+posfilter-v1`. Scrub() extends to apply both predicates.

**✂️ Petra:** N=2 real for stoplist (second user of the stoplist mechanism). POS-filter is single-consumer but is the principled long-term fix per the NER cleanup taxonomy. Effort: ~1 session, ~120k tok.

**😈 Riku:** Land with re-pilot measurement. Target: <5% legit-ORG loss vs. post-N9b baseline.

**🧠 Mira:** Apply uniformly to all spaCy entity types (PERSON/ORG/LOC/MISC). PERSON-only restriction adds conditional complexity without commensurate safety.

**User:** Hybrid mechanism, all entity types. Raised: "might we need local-LLM processing here as well?"

**🧠 Mira:** Per-entity LLM classification = ~106h on 760k mentions (infeasible). Per-doc LLM extraction = ~76h (infeasible). GLiNER already wired as opt-in (`ZKM_NER_MODEL=gliner` per N2). Suspicion-gated LLM pass on ~10k NOUN-tagged residuals ≈ ~30 min — but new mechanism class, N=2 doesn't hold yet.

**🏗️ Archie:** LLM verifier is orthogonal — composes *after* POS+denylist. Backlog as N9d, gated on post-N9c re-pilot residuals.

**User:** Backlog N9d. Also: bidirectional feedback loop — "if heuristic denies `Du`, LLM should still confirm once; if heuristic passes but LLM denies, heuristic should from then on skip it."

**🏗️ Archie:** Closed-loop heuristic ⇄ verifier learning. Per-entity provenance state at `.zkm-state/ner-denylist-learned.jsonl` (`{value, verdict, source, confirmed_by, timestamp}`). Requires N9d as foundation. Backlog as N9e.

**😈 Riku:** Per-entity allow + deny with provenance and conflict resolution ("Bank Vontobel" → heuristic NOUN-drop → LLM says legit → reinstate via allowlist). Real design conversation, not a one-liner.

### Item 3 — N10/N11 docs and CLAUDE.md drift

**✂️ Petra:** Bundle N10 (`docs/ner.md` + entity-model + CLAUDE.md) + N11 (1-paragraph PII note) + CLAUDE.md orphan fix as one docs commit *after* N9c code lands and re-pilot is documented. Avoids documenting a moving target.

**User:** Sequence confirmed. Also: "should CLAUDE.md name the version at all? I don't want re-bumping there in addition to git tag and pyproject.toml."

**🏗️ Archie:** Drop explicit `(currently X.Y.Z)` literals from CLAUDE.md lines 116-118. Keep structural assertion ("own git repo, own `vX.Y.Z` tags"). Single source of truth = pyproject + git tag. Reader who needs current version: `git describe --tags`.

**😈 Riku:** Accepted. Drift cost > 3-keystroke lookup cost.

## Decisions

1. **`zkm status` invisibility**: standalone direct invocation, n=1 unconfirmed. Log-and-wait. Add 1-line TODO to observe parallel `zkm status` during next NER convert run.
2. **N9c mechanism**: hybrid POS-filter + closed-set common-noun denylist.
   - POS-filter on all spaCy NER types (PERSON/ORG/LOC/MISC); keep `ent.root.pos_ == "PROPN"` only; pattern-overlay entities bypass.
   - `_COMMONNOUN_STOPLIST` = {`Du`, `wünschen`, `Zeit`, `EUR`, `CHF`, `UTC`, `MESZ`, `CEST`, `Internet`, `CV`, `AGB`, `HRB`}; parallel to N9b `_STOPLIST`.
   - Cache invalidation: `model_version` → `+textfilter-v1+posfilter-v1`.
   - `scrub()` extended to apply both predicates; re-pilot required (target: <5% legit-ORG loss).
3. **N9d (backlog)**: LLM verifier on residuals + GLiNER promotion option; gated on N9c re-pilot residual rate.
4. **N9e (backlog)**: closed-loop learned denylist with per-entity provenance state; depends on N9d.
5. **Sequencing**: N9c code + re-pilot first; N10/N11/CLAUDE.md docs commit follows.
6. **CLAUDE.md version literals**: drop all `(currently X.Y.Z)` from lines 116-118; keep structural assertion only.

**Out of scope:** LLM verifier code (N9d), closed-loop state (N9e), status-system instrumentation, GLiNER as tracked task, PERSON-only POS-filter restriction.

## Action items

- [ ] **N9c-1.** POS-filter in `plugins/zkm-ner/src/zkm_ner/extract.py` — `_pos_filter(ent)` keeps `ent.root.pos_ == "PROPN"`; applied to spaCy NER outputs only. 6 tests in `plugins/zkm-ner/tests/test_pos_filter.py`.
- [ ] **N9c-2.** `_COMMONNOUN_STOPLIST` + `drop_commonnoun_stoplist` in `plugins/zkm-ner/src/zkm_ner/textfilter.py`. Parametrised tests (each word + case-insensitivity) added to `plugins/zkm-ner/tests/test_textfilter.py`.
- [ ] **N9c-3.** Bump `model_version` in `plugins/zkm-ner/src/zkm_ner/version.py` to `+textfilter-v1+posfilter-v1`.
- [ ] **N9c-4.** Extend zkm-ner `scrub()` in `plugins/zkm-ner/convert.py` — both `_COMMONNOUN_STOPLIST` predicate (cheap) and isolated-POS-tag predicate (expensive, principled). 3 tests in `plugins/zkm-ner/tests/test_scrub.py`.
- [ ] **N9c-5.** Run `zkm convert zkm-ner` (cache bust) then `zkm scrub zkm-ner --apply`. Commit.
- [ ] **N9c-6.** Re-run `plugins/zkm-ner/scripts/pilot.sh`; compare person/org top-N; target <5% legit-ORG loss. Document delta in TODO.md.
- [ ] **N9c-7.** Add N9d and N9e backlog items to TODO.md.
- [ ] **N10.** `docs/ner.md` (new); update `docs/entity-model.md` Phase 2.5; update `CLAUDE.md` Phase 2.5 sequencing.
- [ ] **N11.** PII redaction 1-paragraph design note in `docs/entity-model.md`.
- [ ] **CLAUDE.md cleanup** (with N10): drop `(currently X.Y.Z)` from lines 116-118; keep structural assertion only.
- [ ] **Status observation TODO**: 1-line entry to observe parallel `zkm status` on next NER run (n=1 unconfirmed, 2026-05-11).
- [ ] **Update `docs/meeting-notes/meeting-style.md`** Past meetings index.
