# 2026-07-12 — D2 unified `zkm push` (id:998b) — delta scope + stale-premise correction

**Started:** 2026-07-12 10:30
**Session:** bf173b03-042e-4095-bd33-5155a0f39c74
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🗄️ Cassi (sync-vs-backup — re-onboarded), 🔩 Gil (git-annex plumbing — re-onboarded)
**Topic:** Implement D2 (storage-tiers note): unified `zkm push`. Much already existed — scope the *delta*, and re-check two premises that D3 / `zkm fetch` had invalidated.

## Surfaced context (code state, verified 2026-07-12)
- `push_store()` (`store.py:184`) already did: git push; annex → `git annex sync [--content]`; lfs → `lfs push --all`. `zkm push [remote] [--content]` wired at `cli.py:144`.
- `pull_store()` (`store.py:204`) is the remote-content twin.
- `zkm fetch` (`cli.py:430`) is the **external-source ingestion** orchestrator (runs `core.fetch.sources[].command`, then converts) — NOT the pull-twin. D2's "shared remote registry with `zkm fetch`" premise was mistaken.
- D3 shipped (`store.py:36-39`): `embeddings.npz` annexed; `bm25.pkl` T4 gitignored/regenerate. D2's "best-effort per-remote **index** sync" leg had nothing left to carry.

## Agenda
1. Delta: what does D2 still need beyond today's `push_store`?
2. `annex sync --content` (current) vs `annex copy --to` (D2 text) — is the push verb already safe?
3. The index-sync leg — does it survive D3?
4. `--fast-seed` — build now or defer?
5. "shared remote registry with `zkm fetch`" — needed, or do git remotes suffice?

## Discussion

**Agenda 1–3.** 🔩 Gil / 🗄️ Cassi: `annex sync --content` is *bidirectional* — a plain `zkm push` can silently fetch+merge remote refs and content back into your branch (the sync-vs-backup conflation). D2's `git annex copy --to` is push-only with correct location tracking, but doesn't move git refs. 😈 Riku: `git push` (or an annex ref-push) *fails loudly* on divergence — desired. ✂️ Petra: D3 already shipped, so the "best-effort index-sync leg" has no file to transfer; 🔩 Gil: adding it would duplicate the annex copy and race D3's post-index `drop --force` hook → not just empty but actively wrong today. Escape hatch (Riku): the leg returns only if a non-annex, non-cheap artifact ever lands in `.zkm-index/`.

Implementation subtlety (Gil): `git annex copy --to` records location in the **local** `git-annex` branch; the remote only learns it holds the content once that branch is pushed. So the annex push needs a ref-push that includes the `git-annex` branch — `git annex sync --no-pull --no-content <remote>` is the annex-blessed one-directional ref push (strips `sync`'s bidirectional-merge + content behaviour, keeps git-annex-branch awareness).

**Agenda 4 (`--fast-seed`).** 😈 Riku / 🗄️ Cassi: observe-before-preventing — the cold seed happened once, manually (N=1, the 23 GB seed on 2026-06-24), with none forecast; routine `copy --to` is already fast (transfers only what the remote lacks); the atomic rsync+fsck safety machinery guards a door nobody opens. 🏗️ Archie: it's a *flag on push*, so deferring costs nothing structurally — it slots in additively when a second cold seed actually looms.

**Agenda 5 (registry + content default).** 🔩 Gil: D2's "shared registry with `zkm fetch`" premise is wrong — `zkm fetch` is external-source ingestion; the real push twin is `zkm pull`, and push/pull already share **git remotes** (`zkm remote add/list`, `store.py:162`). No new registry; the N=2 that would justify one fails. Content-default (Riku): `copy --to` only transfers what the remote lacks, so a no-op content push is cheap → content-by-default matches "durability push" semantics.

## Decisions

- **D1 — `zkm push` = one-directional durability push.** Replaced the `annex sync --content` branch in `push_store()`: content via `git annex copy --to <remote>`, then refs via `git annex sync --no-pull --no-content <remote>` (git-annex-branch aware, one-directional, fails loudly on divergence). NO separate index-sync leg — `embeddings.npz` rides the annex copy (D3), `bm25.pkl` regenerates. *Out of scope:* the index-sync leg (returns only if a non-annex, non-cheap artifact lands in `.zkm-index/`); `lfs`/`none` branches unchanged in spirit.
- **D2 — defer `--fast-seed`.** Not built. Additive flag; trigger = a second cold seed actually looms. *Out of scope:* the rsync-objects + remote-fsck-register mode.
- **D3 — content-by-default; git remotes are the registry.** `zkm push` moves annex content by default; `--no-content` gives a fast refs-only push. No new remote registry — git remotes are it. Stale-premise correction: the push twin is `zkm pull`, not `zkm fetch`.

## Implementation findings
- Delta was tiny, as predicted: one `push_store()` branch rewrite + one `_resolve_push_remote()` helper + CLI flag flip (`--content` opt-in → `--no-content` opt-out) + tests.
- `git annex copy --to` needs an explicit target; added `_resolve_push_remote()` (tracking remote → `origin` → raise a clear "pass a remote or --no-content" error).
- `tests/test_store_commands.py`: updated annex dispatch assertions to the new 2-call sequence; added default-content, `--no-content`-no-remote, default-remote-resolution, and unresolvable-remote-raises cases.
- Verification: `uv run pytest -q` → **628 passed**. `store.py` ruff-clean.

## Action items
- [x] **Implement D2 delta** — `push_store()` one-directional durability push (`copy --to` + `sync --no-pull --no-content`), content-by-default, `--no-content` CLI flag, `_resolve_push_remote()` helper, tests. `store.py` / `cli.py` / `tests/test_store_commands.py`. Contract: annex content push emits `[copy --to R]` then `[sync --no-pull --no-content R]`; `--no-content` emits refs-only; unresolvable remote raises `ValueError`. See this note. <!-- id:998b -->
- [ ] **Manual live durability smoke** (non-hermetic follow-up): `zkm push <fievel-remote>` against real `~/knowledge` annex, then `git annex whereis` on the remote confirms content + location tracking landed. Not a unit test. See this note. <!-- id:5f86 -->

## Decision provenance
D1, D2, D3 all ratified by Tobias via AskUserQuestion (recommended option each time): "copy --to, no index leg" / "Defer, additive flag" / "Content by default, add --no-content".
