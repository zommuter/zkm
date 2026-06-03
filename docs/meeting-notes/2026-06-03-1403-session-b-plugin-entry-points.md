# 2026-06-03 — Session B: plugin discovery via entry-point groups

**Started:** 2026-06-03 14:03
**Session:** 8695160c-7c46-40a1-8f19-731f80c56af7
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity)
**Topic:** Replace filesystem-only plugin discovery with `[project.entry-points."zkm.plugins"]` so pip-installed plugin wheels are discovered, while keeping the dev symlink workflow.

## Surfaced discoveries
- [2026-06-01 zkm] Plugin venv-injection gap: only eml self-injects `.venv/site-packages`; pdf/scan/vcard import deps at module top-level and fail when loaded into core venv. Entry-point/real-wheel install may dissolve this for installed plugins.
- [2026-05-13 zkm] Central TODO + polyrepo; 6 plugin names reserved as 0.0.1 stubs awaiting real wheels (this session replaces stubs).

## Agenda
1. Discovery model — entry-points-only vs hybrid (entry-points + retained filesystem scan for dev).
2. Metadata home — keep `plugin.yaml` (loaded via package resources) vs move metadata into Python.
3. Dependency isolation — does real-wheel install dissolve the venv-injection hack, and what happens to dev symlinks?
4. Migration + CLI semantics — stubs→real wheels; what `zkm plugin add/list/remove` mean post-entry-points.

## Discussion

### 1. Discovery model
Archie: today filesystem-only (`convert.py:84-104`); pip wheels in site-packages are invisible. Entry-points = `[project.entry-points."zkm.plugins"]`, enumerated via `importlib.metadata.entry_points(group=...)`. Riku: entry-points-only breaks the dev loop (dev plugins are gitignored symlinks, not pip-installed). Petra: hybrid passes N=2 (released-wheel users + dev tree). Symlink must win so unreleased changes override an installed baseline.
**Decision:** Hybrid union — entry-points + filesystem scan, dedup by name, **dev symlink wins**. `zkm plugin list` shows source (entry-point vs path) and flags shadowed duplicates. `find_plugin()` stays a thin filter over the union (3 call sites untouched).

### 2. Metadata home
Archie: entry point only gives name→module; `Plugin` (`convert.py:50-76`) carries creates_dirs/config_keys/conformance/kind from plugin.yaml. Option A keep plugin.yaml as package data; Option B move into Python. Riku: Option B breaks `conformance.py`'s static (no-import) read of the `conformance:`/`config:` blocks and reintroduces the venv-dep problem; forces `plugin list` to import every plugin. Petra: B is a rewrite with no new capability; out of scope = plugin.yaml schema changes.
**Decision:** **Keep plugin.yaml** (Option A). Ship `plugin.yaml` + `convert.py` as package data in each wheel; resolve path via `importlib.resources.files(<pkg>)`. `load_plugin_manifest()`/`_load_plugin_module()` accept a package-resolved path; dev-symlink path unchanged. **Real bulk of work:** repackage each flat plugin repo (`plugins/zkm-eml/convert.py` at root) into an importable `zkm_<name>` package so `eml = "zkm_eml"` entry point resolves.

### 3. Dependency isolation (scope boundary with the backlog meeting)
Archie: `_load_plugin_module` (`convert.py:405-416`) loads `convert.py` into core venv; eml self-injects its `.venv/site-packages` (`convert.py:14-19`), pdf/scan/vcard don't and crash. Installed wheels resolve deps for free (pip-installed into core venv). Riku: dev-symlink path (kept by decision 1) still broken. Petra: Session B = discovery; don't fold a loader rewrite in. Archie: cheap non-rewrite = lift eml's injection into core `_load_plugin_module` (backlog option d, ~6 lines), validated by conformance.py's existing `_inject_plugin_venv`.
**Decision:** Installed-wheel deps resolve for free (state it). **Lift eml's `.venv` self-injection into core's `_load_plugin_module`** so all dev-symlink plugins get it uniformly. Heavier isolation (subprocess, editable-install-only) **stays in the separate 'Plugin dependency loading' meeting** — out of scope here.

### 4. Migration sequencing + CLI semantics
Archie: released install path is NOT plain `pip install` — zkm is a sealed uv-tool env; clean path is `uv tool install zkm --with zkm-<name>` (entry-point + deps resolved). Riku: filesystem-dropped plugin is discovered but deps NOT in zkm's venv — the two discovery origins are not deps-equivalent. Petra: wrapping pip/uv inside `zkm plugin add` = reimplementing an env manager (the line not to cross). Sequencing: core discovery lands first (backward-compatible), then per-plugin repackage. Pilot eml (most complex) before the other five.
**Decisions:**
- **Migration scope this session:** core hybrid discovery + lift-injection + **pilot eml only** end-to-end (repackage → entry-point → real wheel replacing stub). Remaining 5 (ner, pdf, photo, scan, notmuch) = follow-up rollout. Blast radius = 2 repos.
- **CLI semantics (add/remove wording, remove-refusal, documented install path) DEFERRED** to a follow-up once the entry-point path is used in anger. `zkm plugin add/remove` stay as-is (filesystem clone/symlink) for now.
- **In scope still:** `zkm plugin list` shows origin (entry-point vs filesystem path) + flags shadowed duplicates — the minimal safety feature that makes hybrid discovery non-silent (decision 1). NOT part of the deferred redesign.

## Decisions
- **D1 — Hybrid discovery.** `list_plugins()` = union of `importlib.metadata.entry_points(group="zkm.plugins")` (resolve each to its package dir) + the existing `plugins_dir()` filesystem scan; dedup by plugin `name`; **dev symlink wins** over an installed wheel of the same name. `find_plugin()` stays a thin filter (call sites `convert.py:154,303,355` untouched). *Out of scope:* entry-points-only (breaks dev loop).
- **D2 — Keep `plugin.yaml`.** Metadata stays in `plugin.yaml`, shipped as package data in each wheel, located via `importlib.resources.files(<pkg>)`. `load_plugin_manifest()` / `_load_plugin_module()` accept a package-resolved path; dev-symlink path unchanged. Preserves `conformance.py`'s static (no-import) validation. *Out of scope:* moving metadata into Python; changing the `plugin.yaml` schema.
- **D3 — Dependency isolation.** Installed wheels resolve deps for free (pip/uv into zkm's env). Lift eml's `.venv` self-injection (`convert.py:14-19`) into core's `_load_plugin_module` so all dev-symlink plugins get it uniformly. *Out of scope:* subprocess isolation / editable-install-only — stays in the separate 'Plugin dependency loading' meeting.
- **D4 — Sequencing.** Core discovery change lands first, backward-compatible (filesystem still scanned). Then **pilot eml only**: repackage flat repo → importable `zkm_eml` package, declare entry point, ship plugin.yaml+convert.py as package data, bump+tag+publish real wheel replacing the 0.0.1 stub. Remaining 5 plugins = follow-up rollout. *Out of scope:* repackaging all six this session.
- **D5 — CLI semantics deferred.** Released install path is `uv tool install zkm --with zkm-<name>` (sealed-env reality) — documented, never wrapped by `zkm plugin add`. add/remove wording, remove-refusal-on-wheel, and documented-install live in a follow-up. `zkm plugin list` origin display + shadowed-dup flag remain in this session as discovery-safety. *Out of scope:* `zkm plugin add` shelling out to uv/pip (package-manager reimplementation).

## Action items
- [ ] **SB1 (core).** `src/zkm/convert.py` — hybrid `list_plugins()`: union `entry_points(group="zkm.plugins")` (resolve to package dir + `load_plugin_manifest`) with filesystem scan; dedup by name, dev-symlink wins. `find_plugin` unchanged. Contract test: a fake entry-point-registered plugin is discovered; a same-name symlink shadows it; `find_plugin` returns the symlink one. Session B. <!-- id:e5ae -->
- [ ] **SB2 (core).** `src/zkm/convert.py:405-416` `_load_plugin_module` — lift eml's `.venv/site-packages` self-injection (`plugins/zkm-eml/convert.py:14-19`) into core so every dev-symlink plugin's deps resolve uniformly. Contract test: `zkm convert pdf` from a clean core venv no longer fails on `pypdf` import. <!-- id:19ea -->
- [ ] **SB3 (core).** `zkm plugin list` — show origin (`entry-point` vs filesystem path) + flag shadowed duplicates. Contract test: list output marks a shadowed wheel when a same-name symlink exists. <!-- id:937d -->
- [ ] **SB4 (eml pilot).** `plugins/zkm-eml/` — repackage flat repo into importable `zkm_eml` package; ship `plugin.yaml`+`convert.py` as package data; declare `[project.entry-points."zkm.plugins"]` (`eml = "zkm_eml"`); fix conformance fixture path (`conformance.config.source_dir`); bump+tag+`uv publish` real wheel replacing 0.0.1 stub. Contract: `uv tool install zkm --with zkm-eml` → `zkm convert eml` works; roundtrip corpus test + conformance pass. <!-- id:4d01 -->
- [ ] **SB5 (rollout follow-up).** Repackage + entry-point + publish remaining 5 real wheels (ner, pdf, photo, scan, notmuch) mirroring the eml pilot. Gated on SB4 proving the pattern. <!-- id:42ba -->
- [ ] **SB6 (follow-up meeting/design).** CLI semantics: `zkm plugin add/remove` wording, remove-refusal on pip-installed plugins, documented `uv tool install --with` install path. Trigger: entry-point path used in anger after SB4/SB5. <!-- id:a3fe -->
