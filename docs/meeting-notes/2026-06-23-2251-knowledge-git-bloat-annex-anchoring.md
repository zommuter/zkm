# 2026-06-23 — Taming the ~/knowledge .git slowdown

**Started:** 2026-06-23 22:51
**Session:** 25b63444-67d8-46b2-8da9-927653113616
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🔩 Gil (git object-model / annex plumbing — re-onboarded), 🗄️ Cassi (sync-vs-backup / derived-data persistence — re-onboarded)
**Topic:** ~/knowledge/.git has grown to 24 GiB (52 GiB working tree); decide how to stop the growth and whether/how to reclaim the bloat — a cross-cutting concern between the zkm tool repo (which owns the store contract) and the store itself.

> **Mode note:** cross-cutting meeting (`/meeting --cross`). `<root>` for write-back = `~/src/zkm` (the tool repo owns the store layout, `.gitattributes` template, and git-add scoping). The store surgery itself is a one-off op, not a tracked zkm feature.

## Diagnosis (measured, not assumed)

- `.git` = **24 GiB**, working tree = **52 GiB**, only **753 commits**, but **1.24M objects** in **20.36 GiB of packs**. A *binary-content-in-history* problem, not a commit-count problem.
- Top blobs are WhatsApp media under `chat/whatsapp/<chat>/originals/_objects/<aa>/<rest>` (60–195 MB each) plus raw `inbox/whatsapp/msgstore.db` (91 MB) and `.crypt15` (88 MB).
- **Root cause confirmed by `git check-attr`:**
  - `originals/foo` → `annex.largefiles: anything` ✓ (root-level originals ARE annexed)
  - `chat/whatsapp/x/originals/_objects/ab/cd` → `unspecified` ✗ (nested per-plugin CAS originals NOT annexed)
  - `inbox/whatsapp/msgstore.db` → `unspecified` ✗
  The `.gitattributes` rule `originals/** annex.largefiles=anything` is anchored at the repo root, so it never matches the nested `*/originals/_objects/` paths the CAS layer (`zkm.cas.write_object(store, subdir, src)` → `<subdir>/_objects/`) actually writes. Those binaries were committed as plain git blobs → 20 GiB pack bloat. Source of the bug: `src/zkm/store.py:20-21`.
- `inbox/whatsapp/msgstore.db{,.crypt15}` are now in `.gitignore` — added *after* commit, so the blobs persist in history. (Manual `git add` during an earlier zkm-whatsapp pilot, per Tobias — not a plugin-scope regression.)
- **Annex value check:** `git annex info` shows the only repository holding bytes is `zkm-zomni [here]`. No off-disk annex copy — `web`/`bittorrent` are empty default special remotes. The git remote `fievel:knowledge.git` holds the *bloated pack*, not annex content. So annex currently buys almost nothing (no second copy, no dedup-across-clones) while adding smudge/clean complexity.
- `borg`/`restic` are **not installed**; no backup timer covers `~/knowledge` (only `proton-backup` + `claude-sessions-backup` exist). `docs/restore.md` only *names* them as examples. So today's only copies of originals = this disk + the bloated fievel pack.
- inbox/ is heavily tracked (67k files) — intentional: date-sharded navigation symlinks + `.origin.json` sidecars pointing into CAS. The binaries belong in CAS `_objects/`, annexed.

## Agenda
1. Where do binary originals belong long-term?
2. Reclaim the 20 GiB (history rewrite) or just stop the bleeding?
3. What lands in zkm *core* (so fresh stores never bloat) vs. one-off surgery, and in what order?

## Discussion — Agenda 1: where do originals belong

🏗️ **Archie:** `docs/object-storage.md` intent is explicit: CAS `_objects/<aa>/<rest>` gives a *stable in-tree path* "regardless of which backend (annex / lfs / none)". Bytes were always meant to be externalised by the backend — symlinks+sidecars in git, bytes in annex. The bug is purely that the glob doesn't match nested CAS dirs. Smallest correct fix matches `_objects/` wherever it appears.

🔩 **Gil:** Use `**/_objects/**` — `_objects/` is the plugin-agnostic CAS sentinel. And fixing the glob only changes the *future*; already-committed blobs stay in every historical pack until you rewrite history. `git gc` won't help (reachable from 753 commits). "Fix the glob" and "reclaim 20 GiB" are two separate operations.

🗄️ **Cassi:** Challenge the backend itself. Annex has one copy, this disk, no special remote — worst of both worlds (pays smudge/clean + symlink cost, none of annex's distributed-copy benefit). If bytes are immutable + backed up, simplest model: gitignore CAS `_objects/` (backend "none"), let filesystem backup own bytes, `.git` collapses to the markdown tree.

😈 **Riku:** "none + backup" trades away a real capability: CAS objects are *not re-derivable* (`restore.md` re-derives caches/index, never originals). A second-machine `git clone` would get dangling symlinks. Conscious trade, not a glob-dodge side effect. Min evidence to decide: do you ever clone `~/knowledge` to a 2nd machine expecting originals via git?

✂️ **Petra:** N=2 on keeping annex: zero consumers rely on distributed-copy semantics today. Annex unwarranted *as used*. Argues for "none". But is ripping out annex in-scope, or do we just fix the glob and defer annex-vs-none? Don't balloon "stop the bloat" into "re-architect storage."

🔩 **Gil:** The reclaim surgery is the same regardless of backend — backend choice only sets the one `.gitattributes`/`.gitignore` line. Decouple: decide future backend now, rewrite mechanics are identical.

🗄️ **Cassi:** Fork: **(A) annex-everywhere** (fix glob, keep annex, add a real special remote), **(B) none + backup** (gitignore `_objects/`, drop annex), **(C) git-lfs** (drop — no server).

🏗️ **Archie:** B is strictly simpler; `none` is already first-class. A only wins if cross-machine git-native originals matter — only Tobias can answer.

**Tobias:** "When did we add borg to the mix and why? 2 sounds most sensible, and later we should fix the repo (maybe recreating it from scratch is easier than rewriting?)"

🗄️ **Cassi (correction):** We never added borg — it's not installed, no backup timer over `~/knowledge`. `restore.md` only names it as an example. So originals exist only on this disk + the bloated fievel pack. That kills option B — "none + backup" would lean on a backup that doesn't exist.

### Decision 1 (ratified)
**Backend = annex-everywhere (A).** Fix the CAS glob so nested originals are annexed. Durability tail folded into Agenda 3 (add a real 2nd annex copy — annex without a second remote is single-copy theatre). git-lfs and none+backup rejected.

## Discussion — Agenda 2: reclaim — rewrite vs recreate

🔩 **Gil:** Three mechanics: **(A) `git filter-repo --invert-paths --path-glob '**/_objects/**'`** — strips fat blobs from every commit but preserves the commit graph; re-annex current originals; reclaims 20 GiB; SHAs change → force-push + re-clone; correct for a temporal-index tool. **(B) Recreate from scratch** — fresh init + annex + single baseline commit + archive old; dead simple, but permanently discards 753 commits (zkm's "git = temporal index" thesis, Phase 4). **(C) BFG** — drop, filter-repo is better.

😈 **Riku:** Under B the loss is *future* (Phase 4 unbuilt) so immediate cost low, but irreversible. Min evidence for B: "I don't care about pre-today history and never will."

🗄️ **Cassi:** Hybrid: recreate lean, but *retire don't destroy* the old repo (`git bundle` / keep as `knowledge-archive.git`). B's simplicity for the live repo; deep history survives in cold storage, fat blobs nobody clones.

🏗️ **Archie:** Seam: recreate still re-annexes current originals (= A's tail) and the new baseline tree must equal today's HEAD minus bad blobs. filter-repo gives that by construction; recreate makes you reconstruct it. A = automatic, B = understandable.

✂️ **Petra:** One-off store op either way; only prevention lands in the tool repo. Vote: recreate-lean + archive-old — no `--invert-paths` glob-debugging on a 1.24M-object repo.

🔩 **Gil:** Checklist caveat: `git annex init` + fix `.gitattributes` BEFORE the first `git add` of originals; verify `git check-attr` on a nested `_objects/` path returns `anything` before the baseline commit.

**Tobias:** "archive on zomni actually (later move to external HDD), let's drop history for now and consider the filter-repo later and then either rebase the new history or just git graft/replace the ancestry. Yes I don't really know whether the history is worth keeping at all..."

🔩 **Gil:** Graft instinct neutralises the irreversibility: the archive bundle preserves the whole old graph; later run filter-repo *on the archive* offline, then `git replace --graft <new-baseline> <old-cleaned-HEAD>` (or rebase) to reattach deep history beneath today's baseline. "Drop now" = detach-and-shelve, not destroy.

### Decision 2 (ratified)
**Drop history now; fresh-init a lean repo with a single baseline commit of today's tree.** Archive the old bloated repo as a `git bundle` on **zomni** (→ external HDD later). Keep the graft/rebase path open. filter-repo on the live repo deferred.

## Discussion — Agenda 3: prevention in core + sequencing

🏗️ **Archie:** Root cause is in the *tool*: `src/zkm/store.py:20-21` emits `originals/**` for both annex+lfs, but CAS writes nested `<subdir>/_objects/`. **Every** `zkm init` store has this latent bug. Fix: retarget both templates to `**/_objects/**` (keep `originals/**`), + a RED test. Relay-managed repo → clean `[ROUTINE]` item. Sequencing: fix + verify core template BEFORE the store surgery, else surgery rebuilds the bug.

🔩 **Gil:** (1) Patch the live `~/knowledge/.gitattributes` now — zero-risk, stops new originals bloating before surgery. (2) The `msgstore.db` leak is a raw inbox drop, a different path from CAS.

✂️ **Petra:** No default gitignore enumeration of inbox binary extensions (whack-a-mole; inbox is open-ended). Principled fix = git-add scoping audit. N=2 on a bloat-guard: one incident ≠ two — defer the guard.

😈 **Riku:** We have a *confirmed* 24 GiB failure, not speculation — but a hard pre-commit hook is overkill. Proportionate = a read-only warning in `zkm verify`/`doctor` when a committed blob >N MB isn't an annex/lfs pointer. Reporter not guard; respects observe-before-preventing; lower priority than the template fix.

🏗️ **Archie:** Template fix is load-bearing; everything else secondary. Sequencing: core fix + verify, THEN surgery (recreated repo must use the corrected `.gitattributes`).

🗄️ **Cassi:** Fold in D1's durability tail: after recreate the store is single-copy until `git annex copy --to <remote>` gives annex a real second home. Fixing bloat without fixing "one disk = total loss" leaves the worse risk standing.

**Tobias:** "Patch live .gitattributes now, Establish 2nd annex copy, zkm verify un-annexed-blob warning, on 2 I think I added that msgstore.db in a previous zkm-whatsapp pilot"

✂️ **Petra (drop the audit):** WhatsApp git-add audit is moot — `msgstore.db` was a manual add during a pilot, already gitignored, and the surgery's fresh baseline purges it. No systemic action.

## Decisions

- **D1 — Backend = annex-everywhere.** Keep git-annex; fix the CAS glob so nested `_objects/` originals are annexed. Rejected: "none + filesystem backup" (no borg/restic installed; no backup timer → single-copy) and git-lfs (no server). *Out of scope:* removing/replacing the annex backend; re-architecting storage.
- **D2 — Reclaim by drop-history recreate, not live rewrite.** Fresh `git init` + correct annex/`.gitattributes` + single baseline commit of today's tree. Archive old bloated repo as a `git bundle` on zomni (→ external HDD later). filter-repo on the live repo deferred; re-stitch via `git replace --graft`/rebase if history later proves worthwhile. *Out of scope:* preserving live commit history now; running filter-repo this session.
- **D3 — Core fix is load-bearing; prevention scoped tight.** Fix `src/zkm/store.py:20-21` templates (`originals/** → **/_objects/**` for annex + lfs, keep `originals/**`) + RED test, as a relay `[ROUTINE]` item. Sequencing: core fix + verify BEFORE surgery. Follow-ups: patch live `.gitattributes` now; 2nd annex copy after recreate; deferred low-priority `zkm verify` warning. *Out of scope:* hard pre-commit guard; default gitignore of inbox binary extensions; WhatsApp git-add audit.

## Action items

- [x] **(core — DONE this session)** Fixed `.gitattributes` templates in `src/zkm/store.py:20-21` (added `**/_objects/**` for annex + lfs, kept `originals/**`). RED→GREEN tests `tests/test_init.py::test_gitattributes_{annexes,lfs_covers}_nested_cas_objects` (git `check-attr`, hermetic). Full suite 597 green. <!-- id:dbf2 -->
- [ ] **(store, one-off — NOT a tool feature)** Surgery on `~/knowledge`, *after* id:dbf2 lands: (1) `git bundle` current repo → archive on zomni (later external HDD); retain `fievel:knowledge.git` as `knowledge-archive.git`; (2) fresh `git init` + `git annex init` + corrected `.gitattributes`; (3) verify `git check-attr` on a nested `_objects/` path = `anything` BEFORE adding; (4) re-annex current originals + single baseline commit of today's tree; (5) force-replace fievel origin. <!-- id:5636 -->
- [ ] **(store, after recreate)** Establish a real 2nd annex copy: `git annex copy --to <fievel-annex-remote | external-HDD>` so the store isn't single-copy. <!-- id:0b37 -->
- [ ] **(core, defer/low)** `zkm verify`/`doctor`: read-only warning when a committed blob >N MB is not an annex/lfs pointer. Reporter, not guard. Gated: build on a 2nd un-annexed-blob incident (observe-before-preventing). <!-- id:5f61 -->
- [x] **(store, done this session)** Patched live `~/knowledge/.gitattributes` to add `**/_objects/**` — stops new originals bloating the existing repo before surgery.
