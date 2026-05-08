# 2026-05-08 — Tagging cadence & retroactive semver

**Started:** 2026-05-08 23:18
**Session:** 6c0884ea-6a1c-478a-83f7-455adeacb7ce
**Attendees:** Archie (architect), Riku (devil's advocate), Petra (productivity)
**Topic:** Decide tagging cadence across zkm core + plugin repos, and whether/how to retroactively tag existing history.

## Agenda

1. What event triggers a tag?
2. How do we interpret SemVer at `v0.x`?
3. Retroactive scope — which repos, how granular?
4. Cross-repo tag naming and coupling

## Discussion

### Item 1 — Tag trigger

**Archie:** Four cadence options grounded in how this repo actually moves: per-session-boundary, per-closed-TODO-group, per-externally-visible-contract-change, or status-quo manual.

**Riku:** Name the consumer first. With no installer, changelog generator, or rollback workflow, tags are bookmarks. Realistic consumer: bisecting bugs across pyproject version bumps in zkm-eml. One version bump happened without any tag — we can't `git bisect` across it.

**Petra:** N=2 consumer check: (a) `git describe` during debug, (b) potential `uv tool install --tag vX.Y.Z` for stable installs. Separate "tag rule" from "bump rule" — don't conflate.

**Archie (response to Riku):** The minimum discipline that solves the bisect problem is anchoring the version bump commit with a tag at the moment the pyproject changes. Mechanical, no judgement.

**Riku:** Agree. Two distinct asks on the table: (a) anchor existing bumps retroactively, (b) bump more often going forward. Don't conflate.

**Decision:** **Bump-and-tag rule.** Every commit that changes the `version` field in `pyproject.toml` is tagged `vX.Y.Z` in the same commit. Mechanical; no judgement at tag time.

---

### Item 2 — Bump rule at v0.x

**Archie:** Three interpretations:
- **Loose-0.x:** patch=bugfix; minor=anything else (feature, refactor, deps). Frequent, low decision-cost.
- **Strict pre-1.0:** patch=bugfix; minor=visible API/contract change only. Risks repeating the "forgot to bump" problem.
- **Always-minor:** never use patch at v0.x; every commit-worth-tagging bumps minor.

**Riku:** Strict is exactly the problem we have — the "was this a contract change?" judgement is what stopped bumping. Loose collapses the decision. Always-minor is mechanical but reads weird at v0.32. Counter-argument to always-minor: bump-and-tag already provides mechanicalism; the granularity question is separate.

**Petra:** Pre-1.0 semantics are deliberately permissive. Loose-0.x matches the changelog reader's intent: "minor = meaningful thing happened." Decision-cost wins over theoretical purity.

**Concrete examples for future reference:**
- "fix encoding mojibake" → `patch` (0.6.0 → 0.6.1)
- "add charset-normalizer + ftfy deps + fixtures" → `minor` (0.6.1 → 0.7.0)
- "add `--show-expansion` CLI flag" → `minor` in both loose and strict
- "internal refactor originals.py 481→294 lines" → `minor` under loose, `patch` under strict

**Decision:** **Loose-0.x.** patch = bugfix; minor = anything else (feature, dep, refactor, behavior). Major stays at 0 until 1.0 is explicitly declared.

---

### Item 3 — Retroactive scope

**Archie:** Inventory:
- `~/src/zkm/` core: pyproject `0.2.0`, tag `v0.2.0` already exists — no backfill needed.
- `~/src/zkm/plugins/zkm-eml/`: 32 commits, pyproject `0.6.0`, no tags. Git history reveals pyproject was touched in 4 commits: v0.1.0 at `9d06d1a`, then directly to v0.6.0 at `aa9520f` — no intermediate pyproject commits for v0.2–v0.5. **Backfill produces 2 tags, not 5 as initially estimated.**
- `plugins/zkm-photo/`, `zkm-pdf/`, `zkm-scan/`, `zkm-notmuch/`: 1 commit each, pyproject `0.1.0`. Retroactive = HEAD tag.

**Riku:** Risk (c) from the agenda — "pyproject value may not match current behavior if changes happened post-bump" — is confirmed for zkm-eml's intermediate versions: v0.2–v0.5 were apparently bumped in pyproject without separate commits, then overwritten. Nothing to tag retroactively. Tag `v0.1.0` at the real 0.1 commit and `v0.6.0` at HEAD. Correct and complete.

**Petra:** Revised total: 6 tags (zkm-eml v0.1.0 + v0.6.0, four other plugins v0.1.0 each). Simpler than projected.

**Decision:** **Bump-history backfill, revised.** 6 retroactive tags total:
- `zkm-eml`: `v0.1.0` at `9d06d1a`, `v0.6.0` at HEAD (`daf9ab4`)
- `zkm-photo`, `zkm-pdf`, `zkm-scan`, `zkm-notmuch`: `v0.1.0` at HEAD of each

---

### Item 4 — Tag naming and cross-repo coupling

**Archie:** Sub-questions: (a) should core's `~/src/zkm/` use a prefixed namespace given it also ships `zkm-notes`? (b) should plugin repos use plain `vX.Y.Z` or prefixed `zkm-eml-vX.Y.Z`? (c) should plugins declare `zkm>=X,<Y` dependency ranges?

**Riku:** Prefixed names (`zkm-eml-vX.Y.Z`) solve a problem that doesn't exist — no meta-view tool, no consumer that combines tags across repos. Standard Python convention is plain `vX.Y.Z` per repo. Don't invent a convention.

**Petra:** N=2 on prefixed names: only one hypothetical consumer (non-existent aggregation tool). Reject.

**Archie:** `zkm-notes` ships from `examples/` in the core repo and is never separately installed. Naming ambiguity is theoretical. Single core namespace fine.

**Riku (coupling):** Tight coupling fails N=2. Status-quo "no coupling" is wrong in principle (core API does change). Standard answer: loose coupling via `zkm>=X,<Y` in plugin pyproject. But separable from this meeting's tagging decisions.

**Petra:** Defer coupling to a focused session; it's independent of tagging.

**Decision:**
- **Plain `vX.Y.Z` per repo.** No prefixes anywhere.
- **Single namespace in core.** `zkm-notes` follows core's tags (ships from same repo, never independently versioned).
- **Core↔plugin coupling deferred** to a separate TODO item.

---

## Decisions

1. **Bump-and-tag rule.** Every commit that changes `version` in `pyproject.toml` is tagged `vX.Y.Z` in the same commit. Out of scope: release-pipeline automation, GitHub releases, changelog generation.
2. **Loose-0.x bump rule.** patch=bugfix; minor=anything else. Major stays 0 until 1.0 declared. Out of scope: strict SemVer 1.0+ rules.
3. **Retroactive backfill (6 tags).** zkm-eml: `v0.1.0` at `9d06d1a`, `v0.6.0` at HEAD. Four other plugins: `v0.1.0` at HEAD. Out of scope: archaeology of intermediate versions not committed to pyproject.
4. **Tag naming: plain `vX.Y.Z` per repo.** Single namespace in core (zkm-notes not separately versioned). Out of scope: prefixed schemes.
5. **Core↔plugin coupling deferred** (loose `zkm>=X,<Y` requires-clauses in plugin pyprojects — separate session).

## Action items

- [ ] Tag HEAD (`daf9ab4`) of `~/src/zkm/plugins/zkm-eml/` as `v0.6.0`; tag `9d06d1a` as `v0.1.0`. Push to fievel. Contract: `git -C plugins/zkm-eml tag --sort=version:refname` lists `v0.1.0` and `v0.6.0`.
- [ ] Tag HEAD of `plugins/zkm-photo/`, `zkm-pdf/`, `zkm-scan/`, `zkm-notmuch/` as `v0.1.0`. Push to fievel. Contract: each repo has exactly one tag `v0.1.0`.
- [ ] Document bump-and-tag + loose-0.x in `~/src/zkm/CLAUDE.md` "Versioning" section. Contract: convention visible to any session picking up the project.
- [ ] File TODO item for backfilling `zkm>=X,<Y` requires-clauses across all plugin pyprojects. Separate session.
