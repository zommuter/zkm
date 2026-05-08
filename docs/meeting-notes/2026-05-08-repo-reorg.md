# 2026-05-08 — zkm repo reorganization

**Attendees:** Tobias (product owner), Archie (architect), Riku (devil's advocate), Petra (productivity)
**Topic:** `~/src` is filling with `zkm-*` directories. Consolidate them under `~/src/zkm/`, decide whether the core moves into a subdir or plugins live in a `.gitignore`d dir, and decide whether to rename `zkm` → `zkm-core`.

## Agenda
1. Where do plugin clones live locally? (gitignored under `~/src/zkm/plugins/` vs. a new parent dir)
2. Does the `zkm` core package move into a subdirectory, or stay at the root?
3. Do we rename the `zkm` repo to `zkm-core`?
4. What about fievel's bare repos and the existing remotes — move/rename or just relink locally?

## Current state (Archie's pre-read)

Local (`~/src/`):
- `zkm/` — core, remotes: `github=github.com:zommuter/zkm.git`, `origin=fievel:src/zkm.git`
- `zkm-eml/` — remote: `origin=fievel:src/zkm-eml.git`
- `zkm-photo/` — remote: `origin=fievel:src/zkm-photo.git`
- `zkm-pdf/` — no remote configured
- `zkm-scan/` — no remote configured

Fievel (`~/src/`):
- bare: `zkm.git`, `zkm-eml.git`, `zkm-photo.git`
- non-bare: `zkm/` (separate working copy — do not touch)

Already-built infrastructure:
- `plugins/` at the project root is already `.gitignore`d
- `zkm plugin add ./examples/zkm-notes` drops a symlink into `plugins/`
- Plugin discovery: `list_plugins()` iterates `plugins/*/plugin.yaml`
- `$ZKM_PLUGINS_DIR` overrides the discovery path

## Discussion

### Round 1 — local placement of plugin source repos

**Archie:** The `plugins/` directory at the root of `~/src/zkm/` is already gitignored and is the canonical home for installed plugins via `zkm plugin add`. The natural extension: put plugin git checkouts *directly* in `plugins/` rather than symlinking from `~/src/zkm-eml/`. Each plugin's `.git/` comes along; its remote URL doesn't change.

**Petra:** N=2 passes trivially — five plugin repos already (eml, pdf, photo, scan, bundled notes). The convention scales: when notmuch and whatsapp land, they go in the same place.

**Riku:** Three risks: (1) nested git repos — VS Code/IntelliJ/`git status` handle this fine via inner `.git/` boundary; (2) `zkm plugin add <path>` semantics — need to verify before mv; (3) don't conflate `examples/zkm-notes` (tracked bundled sample) with `plugins/*` (gitignored installs).

**Archie (after reading `src/zkm/convert.py`):** Three relevant facts from the code:
1. `list_plugins()` (line 78) is path-based — it iterates `plugins/*`, reads `plugin.yaml`. Directory name irrelevant to dispatch.
2. `add_plugin()` (line 100) is a one-shot convenience. We can bypass it by just `mv`ing the repos in.
3. Pre-existing quirk at line 119: local installs do `dest = pdir / f"zkm-{name}"`. If the manifest name is already `zkm-eml`, you get `plugins/zkm-zkm-eml`. That's why `ls plugins/` shows `zkm-zkm-eml → ~/src/zkm-eml` today.

**Archie:** Moving dev checkouts into `plugins/` does **not** interfere — discovery finds them via `plugin.yaml`. But we must delete the dangling install-symlinks (`plugins/zkm-zkm-eml`, `plugins/zkm-zkm-photo`) after the mv, or discovery warns at line 92.

**Riku:** If anyone reflexively runs `zkm plugin add ./plugins/zkm-eml` after the move, it would create `plugins/zkm-zkm-eml → ./plugins/zkm-eml` (harmless self-link). Filed as a TODO fix; not a blocker here.

**Petra:** `f"zkm-{name}"` double-prefix fix is out of scope for this reorg. File separately.

**Convergence:** Move `~/src/zkm-{eml,pdf,photo,scan}/` → `~/src/zkm/plugins/zkm-{eml,pdf,photo,scan}/`. Delete `plugins/zkm-zkm-eml` and `plugins/zkm-zkm-photo`. Keep `plugins/zkm-notes` (bundled sample symlink).

### Round 2 — does the core package move into a subdirectory?

**Archie:** Core is already at root (`pyproject.toml`, `src/zkm/`, `tests/`). Adding more gitignored dirs to `plugins/` doesn't change anything structurally.

**Petra:** N=2 for `core/` subdir fails — no consumer benefits. Breaks pyproject.toml path, every CI invocation, every shell history, the `~/.claude/projects/-home-tobias-src-zkm/` memory dir.

**Riku:** Core-in-subdir only fits a vendored monorepo. Round 1 rejected that model — plugins keep independent git repos.

**Convergence:** Core stays at `~/src/zkm/` root.

### Round 3 — rename `zkm` → `zkm-core`?

**Archie:** Rename hits six identifiers: package import (`from zkm.*`), CLI entry point (`zkm`), GitHub repo, fievel bare repo, local dir, memory dir. Cascading impact.

**Petra:** N=2 fails. No concrete consumer. The CLI is `zkm` — users don't interact with plugins at the CLI level in a way that causes confusion.

**Riku:** Rename would be justified only if adopting a `zkm.core` / `zkm.plugins.*` namespace package. Plugins load via `importlib.util.spec_from_file_location` (`convert.py:367`), not via namespace. No architectural backing.

**Convergence:** No rename. `zkm` stays `zkm`.

### Round 4 — fievel bare repos and remotes

**Archie:** Fievel state: bare `zkm.git`, `zkm-eml.git`, `zkm-photo.git`. No bare repos for zkm-pdf or zkm-scan. Options: (A) do nothing on fievel; (B) mirror local namespace at `fievel:src/zkm-plugins/`; (C) create missing bare repos for pdf+scan.

**Petra:** Tobias's stated problem is `~/src` on zomni. Fievel wasn't mentioned. N=2 for option B fails.

**Riku:** Symmetric layout argument: "same conventions on every machine." But remote URL is just a string — nobody feels disoriented. Plus the failure surface doubles if other machines were to clone these repos.

**Tobias decision:** Override — also reorganize fievel. Symmetric mental model wins. Plugin bare repos move into `fievel:src/zkm-plugins/zkm-*.git`. Core stays at `fievel:src/zkm.git`.

### Round 5 — fievel reorganization details

**Archie:** Concrete fievel changes:
- `mv ~/src/zkm-eml.git ~/src/zkm-plugins/zkm-eml.git`
- `mv ~/src/zkm-photo.git ~/src/zkm-plugins/zkm-photo.git`
- `git init --bare ~/src/zkm-plugins/zkm-pdf.git`
- `git init --bare ~/src/zkm-plugins/zkm-scan.git`
- `~/src/zkm.git` stays (core bare repo).
- `~/src/zkm/` (working copy) stays untouched.

**Riku:** Two pre-flight checks: (1) verify fievel's non-bare `~/src/zkm/` vs bare `~/src/zkm.git` before any mv; (2) verify no other machine clones the plugin remotes — only zomni does, but verify.

**Petra:** Sequencing: fievel mv → update local remote URL → first push. Atomic per repo. No pause between the three steps.

**Archie:** Overall order: local zomni `mv` first → fievel mv → update remote URLs → push to verify.

## Decisions

1. **Plugin source repos nest in `~/src/zkm/plugins/`.** `mv ~/src/zkm-{eml,pdf,photo,scan}/ ~/src/zkm/plugins/zkm-{eml,pdf,photo,scan}/`. Each `.git/` survives intact. `plugins/` is already gitignored. Out of scope: `examples/zkm-notes` (stays tracked).
2. **Delete two dangling install-symlinks** `plugins/zkm-zkm-eml`, `plugins/zkm-zkm-photo`. Out of scope: `plugins/zkm-notes → examples/zkm-notes` (stays).
3. **Core stays at `~/src/zkm/` root.** No `core/` subdir.
4. **No rename.** `zkm` stays `zkm` — package, CLI, repo, dir. Revisit only if adopting `zkm.core`/`zkm.plugins.*` namespace package.
5. **Fievel layout mirrors zomni.** `mv fievel:src/zkm-{eml,photo}.git → fievel:src/zkm-plugins/`. `git init --bare fievel:src/zkm-plugins/zkm-{pdf,scan}.git`. `fievel:src/zkm.git` stays (core remote). Out of scope: fievel's non-bare `~/src/zkm/` working copy (do not touch).
6. **Update local remote URLs** on zomni to `fievel:src/zkm-plugins/<name>.git` for all four plugin repos.
7. **Sequence.** Local mv → fievel server-side mv → update local remote URLs → push. Atomic per repo.
8. **Deferred.** Fix `f"zkm-{name}"` double-prefix in `add_plugin()` (`convert.py:119`) and add a "source path already inside `plugins_dir()`" no-op guard. Filed in TODO.md; not part of this session.

## Action items

- [ ] Pre-flight: `ssh fievel "ls -la ~/src/zkm ~/src/zkm.git"` — confirm working-copy vs bare-repo distinction.
- [ ] Local mv: `mv ~/src/zkm-{eml,pdf,photo,scan} ~/src/zkm/plugins/`. Verify `.git/config` survives.
- [ ] Delete dangling symlinks: `rm ~/src/zkm/plugins/zkm-zkm-{eml,photo}`.
- [ ] Sanity check: `uv run zkm plugin list` from `~/src/zkm/` — must list all four plugins, no "skipping" warnings.
- [ ] Fievel: `mkdir -p ~/src/zkm-plugins && mv ~/src/zkm-eml.git ~/src/zkm-plugins/ && mv ~/src/zkm-photo.git ~/src/zkm-plugins/`.
- [ ] Fievel: `git init --bare ~/src/zkm-plugins/zkm-pdf.git && git init --bare ~/src/zkm-plugins/zkm-scan.git`.
- [ ] Local: `git remote set-url origin fievel:src/zkm-plugins/<name>.git` for eml and photo; `git remote add origin fievel:src/zkm-plugins/<name>.git` for pdf and scan.
- [ ] First push: `git push -u origin main` in each plugin repo, sequentially.
- [ ] Smoke test — see Verification section below.
- [ ] Update `CLAUDE.md` "Plugin system" section to document dev-repo-in-plugins/ convention.
- [ ] Update `TODO.md`: (a) add the two `add_plugin()` fixes; (b) add reorg as a tracked housekeeping entry.

## Verification
- `uv run zkm plugin list` from `~/src/zkm/` — lists all four plugins, no "skipping" warnings.
- `git -C ~/src/zkm/plugins/zkm-eml remote -v` — shows `fievel:src/zkm-plugins/zkm-eml.git`. Same for the other three.
- `git -C ~/src/zkm/plugins/zkm-eml fetch origin && git push origin main` — round-trip works.
- `uv run pytest tests/` from `~/src/zkm/` — full core test suite passes.
