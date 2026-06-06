# 2026-06-06 — SB6: plugin CLI semantics (add/remove wording, removal UX, registry)

**Started:** 2026-06-06 16:11
**Session:** 3dfaba25-0645-4bb6-8d75-ed77f75f6df8
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity)
**Topic:** Now that hybrid discovery (entry-points + filesystem) shipped in SB1–SB5, settle `zkm plugin add/remove` semantics — wording, remove-refusal on wheel-installed plugins, and documented install path.

## Surfaced discoveries
- [2026-06-01 zkm] Plugin venv-injection gap dissolved for installed wheels (SB2/SB4).
- [2026-06-03 zkm] Verb-first canonical grammar; `zkm plugin add` shelling out to uv/pip was explicitly rejected in Session B (D5) as package-manager reimplementation.

## Agenda
1. `zkm plugin add` semantics & wording — dev-only (symlink/clone) with clarified help, vs extend to wrap uv.
2. `zkm plugin remove` on entry-point/wheel plugins — the destructive-rmtree hazard; refuse vs redirect vs shell-out.
3. Documentation — where the canonical `uv tool install zkm --with zkm-<name>` path lives.

## Discussion

### 1. `add` semantics & wording
🏗️ Archie: `add_plugin()` is the dev workflow — local→symlink, git→clone, both populate the filesystem-scan origin. Released path is `uv tool install zkm --with zkm-<name>` (entry-point origin), which `add` never touches. Help text "Install a plugin..." overpromises — implies the canonical install path. 😈 Riku: misleading help = support-cost trap; help never mentions entry-point path. Collision with a shadowed wheel is already non-silent (SB3). ✂️ Petra: N=2 for `add` = local dev symlink + git clone-to-hack; item is pure wording. D5 stays closed (`add` ≠ uv wrapper). Zommuter: help text + pointer line (post-success echo).

### 2. `remove` on wheel-origin plugins
🏗️ Archie: live correctness bug — `remove_plugin()` calls `find_plugin` (now union-aware post-SB1); for a wheel plugin, `plugin.path` is the package dir in zkm's uv-tool site-packages. The `shutil.rmtree(plugin.path)` else-branch would delete the package out of site-packages → dangling uv metadata, half-uninstalled, recoverable only via `--reinstall`. Pre-SB1 this was safe (find_plugin only saw filesystem plugins). 😈 Riku: must be unreachable; three shapes: (a) pure refusal, (b) refuse+redirect, (c) shell out. ✂️ Petra: (c) = D5-in-reverse, rejected by symmetry. (b) > (a) at near-zero cost. Shadow subtlety: filesystem plugin shadows wheel → find_plugin returns filesystem one → `remove` peels dev layer correctly; guard fires only when resolved origin is `entry-point`. Riku: origin reliably set on every plugin (`convert.py:109,141`). Zommuter: re-install message (not `uv tool uninstall` which no-ops for `--with` deps).

### 3. Documentation
🏗️ Archie: D1/D2 name `uv tool install --with` but it appears nowhere user-facing except the Session B note. ✂️ Petra: help strings + refusal message cover the 90% case; prose only if a live doc surface exists. Audit: three stale surfaces found — `CLAUDE.md:55,64,66`, `README.md` plugins section, `docs/plugin-spec.md:5`. 😈 Riku: also record the remove-refusal invariant in `CLAUDE.md` so the rmtree hazard isn't reintroduced. Leave `docs/install.md` (about installing zkm itself).

## Decisions
- **D1 — `add` is dev-only, clarified.** Rewrote `cmd_plugin_add` docstring to "Add a local or git plugin for development (symlink / clone). For released plugins: uv tool install zkm --with zkm-<name>"; added one-line echo after successful add. `add_plugin()` body unchanged. *Out of scope:* `add` wrapping uv (Session B D5 stays closed); renaming the command.
- **D2 — `remove` refuses on wheel origin.** `remove_plugin()` (`convert.py:203`) guards on `plugin.origin == "entry-point"` before the rmtree/unlink; raises `ValueError` with a message pointing to `uv tool install zkm --with <other-plugins>`. `cmd_plugin_remove` catches `(LookupError, ValueError)`. Closes the `shutil.rmtree(site-packages/<pkg>)` hazard. Filesystem/symlink plugins remove as before; symlink-shadows-wheel removes the symlink and un-shadows the wheel. *Out of scope:* shelling out to uv, mutating site-packages.
- **D3 — Correct stale docs.** Updated `CLAUDE.md` §Plugin system (dual-origin model, dev-wins shadow, remove-refusal invariant), `README.md` §3 and dev-plugin section (released `uv tool install --with` path), `docs/plugin-spec.md:5` (dual install paths). *Out of scope:* `docs/install.md`, new doc pages.

## Action items
All items resolved in-session; no TODO entries needed.
- [x] SB6a: `src/zkm/cli.py` — `cmd_plugin_add` help reworded + post-success echo. Contract: --help mentions both paths; add prints the uv pointer.
- [x] SB6b: `src/zkm/convert.py` + `cli.py` — `remove_plugin()` refuses `origin == "entry-point"` with redirect; `cmd_plugin_remove` catches `ValueError`. 2 new contract tests in `tests/test_plugin.py`; 528 tests pass.
- [x] SB6c: `CLAUDE.md`, `README.md`, `docs/plugin-spec.md` — stale "filesystem-only discovery + add-as-canonical-install" language corrected; remove-refusal invariant documented in `CLAUDE.md`.
