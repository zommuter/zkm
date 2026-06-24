# 2026-06-24 — Storage tiers, restore-completeness & the sync model

**Started:** 2026-06-24 13:50
**Session:** 6c06eb4b-d3cf-4947-9ae2-49f8bb2e2db6
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🗄️ Cassi (sync-vs-backup / derived-data persistence — re-onboarded), 🔩 Gil (git object-model / annex plumbing — re-onboarded)
**Topic:** For each artifact class in `~/knowledge`, decide its storage tier (true-git / annex / synced-derived / regenerate); then the sync model (`zkm push`) that makes "clone + annex get + sync = usable zkm, no regeneration" true.

> Held immediately after the recreate-lean surgery (id:5636), using its fresh data (pack 464 MB + annex 23 GB, on BTRFS). Resolves id:3a7d, id:7e21, id:6c4f.

## Surfaced context
- Profile (pre-emption-eligible, high): **lever-first** — prefers extending the planned `zkm push`/`zkm fetch` orchestrator over a new sync tool; accepts migration cost for the right end-state.
- Inbox `routed:12fc`: unified `zkm fetch` orchestrator design — the fetch twin of this push lever.
- Tangential orphans (left open): id:0566, id:fa5a (zkm-ner tombstones).

## Agenda
1. The tiering framework + the restore-completeness rule.
2. Per-artifact-class tier assignment (contested: CAS-json sidecars, `.amendments.json`).
3. The sync model (`zkm push`): git + annex content + derived sync; the location-registration trap; `.npz` rsync caveat.
4. The optional `zkm verify --rederive` health-check: build now or defer.

## The four tiers
- **T1 true-git** — small diffable text; restore = `git clone`.
- **T2 annex** — large immutable binary; restore = `git annex get`.
- **T3 synced-derived** — large derived data; restore = sync from a target.
- **T4 regenerate** — only genuinely-cheap rebuilds (never >2h); restore = recompute.

Rule (Cassi): **T4 must be earned** — default to T1/T2/T3; anything ">2h re-derive" can never be T4.

## Discussion

🗄️ **Cassi** named the four tiers and the earn-T4 rule. 🏗️ **Archie** set the uncontested assignments: markdown/text → T1 (today's surgery), CAS binaries → T2, `.origin.json` → T1.

🔩 **Gil** on CAS-json sidecars (`_objects/<hash>.json`): annexed today only because `**/_objects/**` matches by *path* not type; ~395 B and mutable `producers[]` (grows when a new message references the same attachment) → a bad annex fit twice (tiny + mutable→key churn). Move to T1 via `**/_objects/**.json annex.largefiles=nothing`; accept mixed git+annex in `_objects/`.

😈 **Riku** challenged `.amendments.json` → T1 on commit-churn grounds (changes every amender run). 🗄️ **Cassi**: the per-producer `producer_sets` are only regenerable by re-running every amender, NER included (>2h) → cannot be T4; small text → T1; the churn rides the existing frontmatter-commit cadence (frontmatter already commits per amender run). ✂️ **Petra**: ~46k `.amendments.json` are already grandfathered-tracked despite the ignore — mandate *consistency* (un-ignore + track all, never half-state). 🏗️ **Archie**: the extraction cache (Phase 2.5) faces the same fork — set the rule now, assign when built. 😈 **Riku** conceded given the consistency mandate (un-ignoring 46k is a conscious policy reversal, not a side effect).

**Agenda 3 (sync model).** 🏗️ **Archie**: lever-first + roadmap → one command, `zkm push` = git push + annex content + index sync. 🔩 **Gil** named today's live trap: `git annex copy --to` is native + correct but per-object (hours to a Pi for a cold seed); bulk `rsync` + remote `git annex fsck` is minutes but bypasses location tracking (skip the fsck → a later `git annex drop` can delete a local copy trusting a phantom backup). Routine pushes are tiny → native copy; only the one-time cold seed needs rsync. 🗄️ **Cassi**: bake safety in — default native `copy --to`; `--fast-seed` = rsync + remote-fsck-register as ONE atomic op. ✂️ **Petra**: bundle index-rsync only because rsync no-ops when unchanged; the `.npz`-is-a-zip caveat means whole-file resend on change — accept it (batch events). 😈 **Riku**: index-sync must be best-effort/per-remote-configurable, never blocking the durability-critical git+annex push.

**Amendment 3b (Tobias raised: npz-rsyncable? bm25.pkl? annex-T3-with-drop-hook?).** 🗄️ **Cassi**: `bm25.pkl` is cheap to rebuild (TF over markdown, no model) and pickles badly → **T4, not synced**; only embeddings are genuinely T3. 🔩 **Gil**: Tobias's annex-with-drop-hook is *more* lever-first than rsync — annex `embeddings.npz`, a post-`zkm index` hook `git annex drop --force` the superseded key → exactly one version, no pileup → `zkm push`'s `git annex copy` carries it with **no separate index lever**. Cost: whole-file transfer (no delta). 🗄️ **Cassi** raised the competing axis (rsync-delta on uncompressed `.npy` would transfer only appended rows) but 😈 **Riku** demanded evidence on embed.py's write pattern. **Checked live:** `embed.py:211` = `np.savez_compressed` full-rewrite, non-append, unstable row order; `index.py:266` = full pickle rewrite. → rsync-delta gains nothing without rewriting embed.py; whole-file transfer is inherent → annex+drop-hook is strictly better. Riku withdrew.

**Agenda 4 (health-check).** ✂️ **Petra**/😈 **Riku**: observe-before-preventing / N=2 — no drift incident; today's tiering already makes restore complete. Defer; fold the `--rederive` sample-diff idea into the existing id:5f61 (`zkm verify`/`doctor`) stub.

## Decisions

- **D1 — contested classes → T1 git.** CAS-json sidecars → git (`**/_objects/**.json annex.largefiles=nothing`, keep `**/_objects/**`=anything for binaries; mixed dir accepted). `.amendments.json` → git: remove `*.amendments.json` from `.gitignore`, track ALL consistently (incl. ~46k grandfathered). *Out of scope:* re-tiering markdown/binaries/`.origin.json`; extraction-cache tier (rule set — expensive→T1/T3, never T4; assign at build).
- **D2 — unified `zkm push`.** `git push` + `git annex copy --to` (native, jobs+sshcaching, correct tracking) + best-effort per-remote index sync (never blocks git+annex). `zkm push --fast-seed` = atomic rsync-objects + remote-fsck-register (cold seeds only). Shared remote registry with `zkm fetch` (routed:12fc). *Out of scope:* building it this session; non-ssh transports/auth.
- **D3 — embeddings → T3 via annex + drop-old hook; `bm25.pkl` → T4.** Annex `embeddings.npz`; post-`zkm index` hook `git annex drop --force` the superseded key → one version, no pileup → carried by `zkm push`'s annex copy (no separate index lever); compression stays on. `bm25.pkl` never synced; regenerate on restore. *Escape hatch (documented, unbuilt):* uncompressed `.npy` + rsync-delta only if embed.py is made append-stable AND whole-file transfer becomes a measured pain. *Evidence:* embed.py full compressed rewrite, non-append.
- **D4 — defer `zkm verify --rederive`; fold into id:5f61.** Annotate id:5f61 with the `--rederive` sample-diff (re-derive a sample, diff vs stored — drift reporter) as its second capability. *Out of scope:* building any rederive now.

## Action items
- [ ] **(store+core) Implement D1** — `store.py` gitattributes template + live `~/knowledge`: add `**/_objects/**.json annex.largefiles=nothing`; remove `*.amendments.json` from `.gitignore`; migrate existing CAS-json annex→git; ensure all `.amendments.json` consistently tracked. RED: `check-attr` on `_objects/*.json` = `nothing` while `_objects/<binary>` = `anything`. (id:6c4f — decided here) <!-- id:6c4f -->
- [ ] **(core) Implement D2** — `zkm push` (git push + `git annex copy --to` + best-effort per-remote index sync) + `--fast-seed` (atomic rsync-objects + remote-fsck-register); shared remote registry with `zkm fetch` (routed:12fc). <!-- id:998b -->
- [ ] **(core) Implement D3** — annex `embeddings.npz` + post-`zkm index` `git annex drop --force` superseded-key hook; `bm25.pkl` regenerate-on-restore (never synced). Verify exactly one embeddings key after two `zkm index` runs. (id:7e21 — decided here) <!-- id:7e21 -->
- [ ] **(core) Annotate id:5f61** with the `--rederive` sample-diff capability (D4). <!-- id:3a7d -->

## Decision provenance
All four ratified by Tobias via AskUserQuestion (recommended option each time). D3 mechanism settled on live `embed.py`/`index.py` evidence (full compressed/pickle rewrite, non-append).
