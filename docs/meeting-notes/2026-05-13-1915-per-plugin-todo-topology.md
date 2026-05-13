# 2026-05-13 — Per-plugin TODO topology

**Started:** 2026-05-13 19:15
**Session:** 4253164f-8e90-41b1-a367-238bf3c571df
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), ⚙️ Sage (skill-runtime lens)
**Topic:** Where do plugin-scoped TODOs live now that all 6 plugins have independent GitHub repos?

## Agenda
1. Map the three options' concrete costs against the existing 6-plugin set.
2. Drift-aversion check: does Option 2 (per-plugin + central) create a dual-ledger problem?
3. /meeting-skill cost for Option 3: blocker, or solvable in <1 session?
4. Migration plan (orphan `plugins/zkm-eml/TODO.md`; existing central sections).
5. Decide topology + prefix convention + Option 3 trigger spec.

## Discussion

### Agenda 1 — Map the three options' costs

🏗️ **Archie:** Concrete state: all 6 plugin repos exist on GitHub (`zommuter/zkm-{eml,ner,notmuch,pdf,photo,scan}`). Central `TODO.md` is 347 lines, 25 sections, mixing (a) core-only, (b) plugin-only, and (c) cross-cutting items (E-prefix γ schema is the clearest example — amendments land in core *and* extractors in zkm-ner). Option 1 (status quo) keeps cross-cutting items naturally co-located. Options 2 and 3 force a split decision per item.

✂️ **Petra:** N=2 audit on per-plugin TODO.md. Right now N=1 (only zkm-eml has one, and that file pre-dates the polyrepo split — a historical artefact, not a chosen convention). If we adopt Option 2, we'd be writing 5 new TODO.md files speculatively; none currently has plugin-scoped items unique to it that aren't already in central. Real N=2 fail.

😈 **Riku:** Drift-aversion lens (established profile pattern). Option 2 introduces exactly this: a plugin-scoped item could live in either central or per-plugin, and the answer to "where do I look for plugin X's open work?" becomes ambiguous unless a hard rule routes it. Without a rule, drift is guaranteed.

⚙️ **Sage:** Option 3 cost surfacing — /meeting-skill emits action items as `- [ ] description — covered by <file>` markdown lines. Switching to GH Issues requires: (a) `format.md` change defining issue-ref syntax; (b) `gh issue create` calls from the skill; (c) `gh` allowlist additions in settings.json; (d) back-link from issue body to meeting note. Mechanically achievable in ~1 session for the skill side. Compatible with central TODO.md as the *tactical* ledger — GH Issues would host larger items only.

🏗️ **Archie:** Outside contributors: zero contributors today on these repos. Option 1 optimises for the actual reader (the user + future-self). Option 3 optimises for a hypothetical contributor that may never appear. Defer until the contributor materialises — N=2-future fails today.

😈 **Riku:** Counter-pressure on Option 1: central TODO.md works *now* because the user is the only writer. As plugin versions advance independently (auto-tag hook + OIDC pending), discoverability from inside a plugin clone degrades. But this is a future trigger, not a today trigger.

✂️ **Petra:** Synthesis: extend the existing lever (central TODO.md + informal prefix convention N/A/E/S) rather than introduce a new mechanism. Option 3 reserved for "when a plugin gets its first outside contributor" — that's the trigger, bundled with the /meeting-skill change.

**Decision 1 (user):** Hybrid — adopt Option 1+ now (central remains the ledger; formalise prefix routing) AND define the explicit trigger condition for switching to Option 3. User also added a forward-flag for the meeting-skill itself (see Agenda 5).

### Agenda 2 — Migration plan

🏗️ **Archie:** Two artefacts: (1) `plugins/zkm-eml/TODO.md` (orphan — 8 unchecked, 13 checked, pre-dates polyrepo split). Merge 8 unchecked into central under new `## zkm-eml backlog (M-prefix)` section; delete the orphan file. (2) Existing central plugin-scoped sections (N-/A-/E-/Session-prefixes): leave as-is — they work, no migration cost, decision applies going forward only.

✂️ **Petra:** Deletion is fine — the 8 items get a new home, the 13 checked items are historical noise visible in git log. Don't create `TODO.archived.md` as a second copy.

😈 **Riku:** git history *is* the archive. Deleting `plugins/zkm-eml/TODO.md` after merging unchecked items is the clean move.

### Agenda 3 — Prefix convention

🏗️ **Archie:** Document current informal convention in `CLAUDE.md`:
- `N` → zkm-ner (NER pipeline)
- `A` → zkm-eml auto-trigger (mbsync hook)
- `E` → γ schema (cross-cutting core + zkm-ner)
- `S` → SIGUSR1/status (core)
- `M` (new) → zkm-eml backlog migrated from orphan TODO.md
- no prefix → core / cross-cutting

Rule: when a plugin gets ≥3 unchecked items at once that aren't already in a numbered series, give it a single-letter prefix and add the mapping to CLAUDE.md.

⚙️ **Sage:** Light enough to document — single CLAUDE.md paragraph.

### Agenda 4 — Option 3 trigger condition

😈 **Riku:** Trigger must be unambiguous. Recommend: first merged outside PR OR first public GH Issue on any plugin repo. Either fires across ALL plugins (not just the one that triggered it) — prevents split-topology drift. Threshold = 1 (cost of switching is small once the meeting-skill changes are designed).

✂️ **Petra:** Defer the actual /meeting-skill changes until trigger fires. The gh-issue-emission helper is not cheaply extensible (cross-repo + allowlist + format.md), so deferral is justified per scope-tolerance exception clause.

### Agenda 5 — Meeting-skill backlog forward-flag (user addition)

⚙️ **Sage:** User forward-flagged that the /meeting-skill itself should eventually:
- **(F1)** Query `gh issue list --state open` for the current repo AND any sub-repos (walk `plugins/*/.git` + detect their GitHub remotes) when auditing orphan action items.
- **(F2)** Define "sensibly associated repos" — first pass: sub-repos with a remote in the same `<user>/*` GitHub namespace.
- **(F3)** Once the skill can *read* GH Issues for audit, *writing* issues as action items is a small additional step — folds into the Option 3 trigger work.

Action: add a one-line forward-flag to `~/src/dotclaude-skills/` backlog referencing this meeting note.

**Decision 2 (user):** Confirmed all four: merge + delete orphan; M-prefix for zkm-eml items; trigger = first outside PR OR GH Issue (whole-topology switch); meeting-skill forward-flag in dotclaude-skills.

## Decisions

- **Topology: Option 1+ (central `TODO.md` as single ledger, formalised prefix routing).** All plugin-scoped items live in `~/src/zkm/TODO.md` under prefix-namespaced subsections. Out of scope: per-plugin `TODO.md` files; multi-ledger dual tracking.
- **Prefix convention documented in `CLAUDE.md`.** Mappings: `N` (zkm-ner), `A` (zkm-eml auto-trigger), `E` (γ schema, cross-cutting), `S` (SIGUSR1/status, core), `M` (zkm-eml backlog items, new), no prefix = core/cross-cutting. Rule: ≥3 unchecked items at once for a plugin → assign a prefix. Out of scope: enforced linting; tooling.
- **Migration: orphan `plugins/zkm-eml/TODO.md` merged into central + deleted.** 8 unchecked items move to `## zkm-eml backlog (M-prefix)` in central. Checked items archived in git history only. Out of scope: `TODO.archived.md`.
- **Option 3 trigger: whole-topology switch on first outside PR OR first public GH Issue on any plugin repo.** Fires across all plugins simultaneously to prevent split-topology drift. /meeting-skill changes bundled into that future session. Out of scope: per-plugin selective migration.
- **Meeting-skill forward-flag recorded in `~/src/dotclaude-skills/`.** F1–F3: GH-issue audit in orphan check, sub-repo discovery, GH-issue emission. Out of scope: design or implementation this session.

## Action items

- [x] **TOP-1.** `~/src/zkm/TODO.md` — add new `## zkm-eml backlog (M-prefix)` section with M1–M8 from orphan file.
- [x] **TOP-2.** `plugins/zkm-eml/TODO.md` — delete (merged into central); commit in zkm-eml repo.
- [x] **TOP-3.** `~/src/zkm/CLAUDE.md` — add "TODO prefix convention" paragraph with N/A/E/S/M table, ≥3-items rule, and Option 3 trigger spec (with link to this note).
- [x] **TOP-4.** `~/src/dotclaude-skills/` — append forward-flag line (F1–F3) referencing this meeting note.
- [x] **TOP-5.** `~/src/zkm/docs/meeting-notes/meeting-style.md` — add entry for this note under "## Past meetings".
