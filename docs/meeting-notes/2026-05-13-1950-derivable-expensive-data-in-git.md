# 2026-05-13 — Derivable-but-expensive data in git

**Started:** 2026-05-13 19:50
**Session:** b90da6c3-6c55-4dc0-921c-26a107981319
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🗄️ Cassi (cache/sync lens — derived-data persistence, build-cache patterns, eviction policies, multi-machine sync) (new)
**Topic:** What's the right persistence strategy for `.zkm-state/extraction-cache`, `.zkm-index/embeddings.npz`, and similar "expensive to re-derive but technically reproducible" data — and is this question even live yet?

## Concrete state (measured 2026-05-13 19:50)

Live store at `~/knowledge/`, all gitignored:

| Path | Size | Files | Re-derive cost | Backup-worthy? |
|---|---|---|---|---|
| `.zkm-state/extraction-cache/ner/` | 1.1 GB | 112,765 | ~25 min NER (CPU + spaCy) | **yes** — primary cost |
| `.zkm-state/extraction-cache/ner_verifier/` | 15 MB | 3,826 | trivial; N9d closed | maybe |
| `.zkm-state/amendments/ner/` | 0 B | 0 | n/a — applied immediately | no — transient |
| `.zkm-state/running/` | <1 KB | (ephemeral) | n/a — process lifecycle | no |
| `.zkm-state/zkm-eml.json` | 149 B | 1 | trivial — watermark | yes (tiny) |
| `.zkm-state/ner-pilot-review-*.jsonl` | ~80 MB | 6 | n/a — historical | no |
| `.zkm-state/ner-verifier-pilot-cached-*.jsonl` | ~8 MB | 2 | n/a — historical | no |
| `.zkm-state/gliner-ab-*.jsonl` | ~95 KB | 4 | n/a — historical | no |
| `.zkm-state/hook-zkm-eml.log` | 64 KB | 1 | n/a — observability | no |
| `.zkm-index/bm25.pkl` | 279 MB | 1 | few min CPU | borderline |
| `.zkm-index/embeddings.npz` | 308 MB | 1 | ~25 min GPU | **yes** — second primary cost |
| `.zkm-index/embeddings-meta.json` | <1 KB | 1 | trivial | yes (tiny) |
| `.zkm-index/expansion-cache.json` | 27 KB | 1 | per-query | no |
| `.zkm-index/last-commit` | 41 B | 1 | trivial | yes (tiny) |

Cumulative "expensive to re-derive" budget today: **~50 min** (NER 25 min + embed 25 min). Growing linearly with corpus + extractor count — easily reaches the 5+ h range once N9g-pre is corpus-wide, future content plugins (zkm-receipt, OCR) land, and any future verifier/alias-resolution stage ships.

`store.py:_GITIGNORE` today:
```
.env
.zkm-index/
.embeddings/      # dead — verified, only reference in code
.zkm-state/
*.swp
.DS_Store
.git-lock-push.lock
```

## Agenda

1. Is multi-machine sync the live concern, or is something else driving this?
2. Per-artefact analysis: extraction-cache (sharded 1.1 GB) vs embeddings.npz (308 MB blob) vs BM25 (cheap rebuild) — does the right answer differ?
3. Map the 4 options against the concrete numbers (gitignored / git-tracked / annex|LFS / remote cache).
4. Decide: do nothing now + define the trigger, or pick an option to ship.

## Discussion

### Agenda 1 — What's driving the question?

🏗️ **Archie:** TODO entry text names "first multi-machine sync" as the trigger. Today's reality: store lives on `zomni` only. Fievel hosts bare-mirror git remotes for *plugin source repos*, not the knowledge store. There is no `~/knowledge/` clone anywhere else. `zkm clone` / `zkm push` / `zkm pull` exist (Phase 2 session 4) and dispatch annex/LFS — the *plumbing* is ready, the *use case* has not landed.

✂️ **Petra:** N=2 audit on concrete demand. N=0 today. Closest near-term consumer is the future WebUI (Phase 3, FastAPI) — runs on the same host as the store. No remote read-replica on the roadmap. Speculative.

😈 **Riku:** Counter — "first multi-machine sync" is the kind of event that surprises you. If you `git clone` `~/knowledge/` to a second box tomorrow morning, the `gitignored` decision baked into `store.py:_GITIGNORE` determines whether you wait 25 min for NER or get an instantly-usable corpus. Asymmetric cost (one bad afternoon vs. cheap pre-emption). And a second sync vector: *disk loss / restore from backup*. Same shape — derived data has to come back somehow.

🗄️ **Cassi:** The four options aren't symmetric:
- **(a) gitignored + re-run** = *Bazel local-cache* default — derive on first use, recompute on cache miss.
- **(b) git-tracked** = what *Nix store* would do if it lived in your monorepo, but Nix uses content-addressing to make tracked caches tolerable.
- **(c) annex/LFS** = "fat blob storage" — fine for one big file (embeddings.npz), terrible for 112k small files (LFS pointer overhead per file, annex tree churn).
- **(d) remote cache** = *sccache/ccache/Bazel remote* — separate from VCS, populated on write, fetched on miss.
The pattern that fits *sharded small files* is (d), not (b)/(c).

😈 **Riku:** Petra's N=0 stands, Cassi's pattern-fit also true. Reconcile: *which option* is well-posed even today (extraction-cache shape decides it). *When to ship* is not (no consumer yet). Decide principle now, defer build.

✂️ **Petra:** Accept. Principle-first. Also: `.embeddings/` entry in gitignore looks dead (replaced by `.zkm-index/embeddings.npz`). Verify and clean up. Class 1 micro-task hiding in this meeting.

🏗️ **Archie:** Confirmed dead — only reference is `store.py:12` (the gitignore template itself). Note for action items.

**Tobias (amendment):** Riku is precisely right; backup is the key issue even for single-machine usage. A 25-min NER + ~25-min embed + future stages adds up — don't redo 5+ h of compute because the SSD flared. Reframe scope from "multi-machine sync" to **disaster recovery on a single machine**. Welcomes Cassi. On the four options: (a) assumes we know what's missing without a full rescan? (b) easiest to use. (c) valid concern about over-using annex/LFS. (d) introduces a remote-dependency we'd rather not have.

### Agenda 1.5 — Backup vs. sync are different problems (reframing)

🗄️ **Cassi:** Critical separation the TODO conflated:
- **VCS gitignore** decides what `zkm clone` / `git pull` ships across machines.
- **Filesystem backup tools** (borg, restic, rsnapshot, ZFS snapshots) operate independently — `.gitignore` does NOT exclude files from backup.

The right question for SSD-flare DR is "is my backup tool covering `~/knowledge/` including the gitignored caches", not "should we track caches in git." Build-cache analogy: **ccache** lives in `~/.cache/ccache/` — never in VCS, always in backup. **Nix store** at `/nix/store/` — never in VCS, always in backup. **Bazel disk-cache** at `~/.cache/bazel/` — same pattern. The industry-standard answer for cheap-but-bulky derived data is *filesystem-level persistence, VCS-level exclusion*.

🏗️ **Archie:** Concrete: a single `borg`/`restic` job on `~/knowledge/` covers extraction-cache + embeddings.npz today *if it doesn't explicitly exclude hidden dirs*. Neither tool reads `.gitignore` by default.

😈 **Riku:** Trust-but-verify: ask current backup posture. If `~/` is on borg → done, no zkm changes. If no backup → the fix is borg/restic, not VCS. If backup excludes hidden dirs → fix the exclude list.

✂️ **Petra:** That collapses (b), (c), (d) to "address the wrong problem." Option (a) stays — augment with a *documented restore note* (`docs/restore.md`): "extraction-cache and embeddings are not in git; restore from filesystem backup OR run `zkm convert ner && zkm index` to re-derive (~50 min as of 2026-05-13)."

🗄️ **Cassi:** Answer to Tobias's "does (a) know what's missing without a full rescan": **yes by design**. Every extractor walks the md tree and consults `ExtractionCache.get(body_sha256, model, version) → None` on miss. No manifest needed; absence is detected lazily during next convert run. Cost of detection = cost of one full convert pass (~25 min for NER). Acceptable for DR; not acceptable for "I want to know in 10 seconds if my cache is intact". A fast integrity check is a *separate* feature: a `zkm verify` command that walks the md tree and counts cache misses without re-extracting. Two-line implementation against the existing `ExtractionCache` API.

😈 **Riku:** Don't ship `zkm verify` speculatively — N=2 fails. Mention as follow-up trigger.

**Tobias (decision):** Backup discussion belongs in `~/src/zomni/` (system-config repo) — not zkm. Keep `zkm verify` here as a backlog item with no live trigger yet.

### Agenda 2/3/4 — Convergence

🏗️ **Archie:** Decision tree collapses cleanly:
- **VCS side (zkm):** option (a) stays. Extraction-cache and embeddings.npz remain gitignored. `zkm clone` to a hypothetical second machine re-derives on first convert/index run. No infra change in zkm.
- **DR side (zomni):** punt the entire question — filesystem-level backup is the right layer.
- **Cleanup:** remove dead `.embeddings/` line; ~88 MB of historical pilot JSONLs in `.zkm-state/` are deletable noise.

✂️ **Petra:** Three concrete zkm-side artefacts: `docs/restore.md`, `.gitignore` cleanup, `zkm verify` backlog entry.

🗄️ **Cassi:** Plus the out-of-scope handoff: open a scoping in `~/src/zomni/` for filesystem-backup coverage of `~/knowledge/` (including hidden dirs).

😈 **Riku:** Final trigger spec for revisiting:
- *First multi-machine sync*: real second host wants `zkm clone` → re-open. "Re-derive on first run" will either be fine (close) or painful (and (b)-style git-tracking of `embeddings.npz` via LFS becomes the candidate — but only that one file).
- *Cache corruption incident*: any user observation of silently-corrupted cache → build `zkm verify`.
- *Re-derive budget breaches ~2 h*: cumulative re-derive cost past ~2 h → re-open and reconsider (b)/(c) for the most expensive single artefact.

## Decisions

- **VCS option (a) confirmed.** `.zkm-state/` and `.zkm-index/` stay gitignored. Single-machine DR is solved by filesystem backup, not VCS. Multi-machine sync re-derives on first run. *Out of scope:* tracking caches in git, annex, LFS, or any remote cache.
- **Backup is out of zkm scope.** Coverage of `~/knowledge/` (including hidden dirs) is owned by `~/src/zomni/`. *Out of scope here:* picking a backup tool, configuring snapshots, retention policies.
- **`zkm verify` is documented backlog, not built.** Trigger: cache-corruption incident OR demand for sub-second integrity check. Implementation: ~2 lines against existing `ExtractionCache.get()` API plus a md-tree walk. *Out of scope:* speculative build.
- **`docs/restore.md` ships now.** One-pager: "if the SSD flares, restore `~/knowledge/` from filesystem backup; the markdown tree + git history are sufficient to re-derive caches via `zkm convert <every-amender>` + `zkm index`; current re-derive budget ~50 min; growing." Cross-linked from `CLAUDE.md`. *Out of scope:* per-extractor restore recipes (too low-level).
- **`.gitignore` cleanup ships now.** Drop dead `.embeddings/` line from `store.py:_GITIGNORE`. Test asserts the entry is absent and `.zkm-index/` is still present.
- **Three explicit re-open triggers.** Multi-machine clone request | cache-corruption incident | re-derive budget exceeds 2 h. Any one fires this meeting again with concrete data. *Out of scope:* time-based revisiting; this is event-triggered only.

## Action items

- [ ] **D1.** `~/src/zkm/docs/restore.md` (new) — one-pager: backup-first restore procedure; `zkm convert <amender>` + `zkm index` as fallback; current re-derive estimate ~50 min (NER + embed); link to `~/src/zomni/` backup config when that lands. Cross-link from `CLAUDE.md` § Architecture (between "Layout" and "Plugin system" feels natural). Contract: a future-Tobias post-disaster reads this file first and recovers without re-discovering the procedure.
- [ ] **D2.** `~/src/zkm/src/zkm/store.py:12` — drop `.embeddings/` from `_GITIGNORE`. Add regression test in `tests/test_store.py` asserting `_GITIGNORE` does NOT contain `.embeddings/` and DOES contain `.zkm-index/`. Contract: a test would fail if the dead entry returns.
- [ ] **D3.** `~/src/zkm/TODO.md` — close the existing "Meeting: derivable-but-expensive data in git" item with [x]; add two new entries: (a) "`zkm verify` backlog" with the corruption-incident-OR-fast-integrity-demand trigger; (b) "Re-open derivable-data meeting" trigger spec (multi-machine clone OR re-derive budget >2 h). Both cite this meeting note path.
- [ ] **D4.** `~/src/zomni/` — open a separate planning item (or call `/meeting` there) for filesystem backup coverage of `~/knowledge/` including `.zkm-state/` and `.zkm-index/`. Out of zkm scope. Contract: at minimum a documented backup tool + coverage check.
- [ ] **D5.** `~/src/zkm/docs/meeting-notes/meeting-style.md` — append this meeting under `## Past meetings` index.
- [ ] **D6.** Optional cleanup: `rm ~/knowledge/.zkm-state/ner-pilot-review-*.jsonl` (~80 MB historical) and `gliner-ab-*.jsonl` if pilots are closed. User judgment call; mention in `docs/restore.md` so future-self doesn't treat them as load-bearing.
