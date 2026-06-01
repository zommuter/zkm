# 2026-06-01 — zkm test: plugin conformance-validator

**Started:** 2026-06-01 16:16
**Session:** 88abcf70-1ac4-4c95-a467-ef9cf7eb084d
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Design and implement `zkm test <plugin>` as a spec conformance validator.

## Context

TODO item `aa77` (from `docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md`, Amendment session) deferred `zkm test <plugin>` with two open questions: (1) conformance-validator vs bare test-runner interpretation, and (2) advisory vs gating exit behaviour.

Both were resolved interactively: conformance-validator interpretation (the runner role is already covered by per-plugin pytest, per Petra's lever-first ruling); layered static + dynamic checks; gate by default with `--advisory` to soften.

## Plan

**Exploration findings:**
- No frontmatter validator existed anywhere in core — only `name:` is checked at manifest load.
- `convert._load_plugin_module` + `inspect.signature` available for interface checks.
- `python-frontmatter` already a dep (used in `convert._find_managed_files`).
- zkm-eml's `tests/fixtures/corpus/*.eml` + `scripts/generate_corpus.py` exist as the roundtrip harness the command "builds on" — connecting via a `conformance.config.source_dir` convention in `plugin.yaml`.

**Design decisions (via AskUserQuestion):**
1. **Layered checks:** Layer 1 static (manifest + interface) always runs. Layer 2 dynamic (run `convert()` against fixtures) runs only if plugin declares `conformance.config` in `plugin.yaml`.
2. **Gate by default:** hard exit-1 on FAIL findings; `--advisory` flag downgrades to warnings + exit-0.

**Key design:** `run_dynamic` calls `_load_plugin_module` + `mod.convert()` directly (bypasses `run_convert` / `find_plugin`) so conformance tests work regardless of `ZKM_PLUGINS_DIR` configuration.

## Implementation findings

- **`python-frontmatter` parses YAML `date:` fields to Python `datetime` objects**, not strings — the validator must handle both types (`isinstance(date_val, datetime)` → check `tzinfo is None`; raw string → check for `T` + tz marker).
- `run_convert` was unsuitable for the dynamic tier because it re-invokes `find_plugin(name)`, which fails when the plugin is loaded via `load_plugin_manifest` from an arbitrary path (e.g., test fixture dirs). Direct module invocation avoids the round-trip through the plugin registry.
- Fixture plugins in `tests/fixtures/plugins/` use `load_plugin_manifest` directly in tests (not `find_plugin`) to support intentionally-invalid `name:` fields without match failures.

## Decisions

- `src/zkm/conformance.py` (new) — `FRONTMATTER_REQUIRED` is now the single source of truth for required frontmatter fields; `validate_frontmatter()` is a reusable helper for any future caller.
- `Plugin` dataclass gains a `conformance: dict` field; `load_plugin_manifest` reads `plugin.yaml`'s optional `conformance:` block.
- `zkm test <plugin>` has no store/git/RunSession guards — it operates on a temporary store and reads no user data.
- Exit codes: `0` pass, `1` FAIL findings or plugin-not-found. `--advisory` always exits 0.
- Dynamic tier skipped (advisory notice to stderr) if `conformance.config` is absent. Only `zkm-eml` declares it initially.
- Out of scope: `creates_dirs` write-containment enforcement (needs filesystem sandboxing), CI loop over all plugins, messaging `kind:` hard-declared gate.

## Action items

- [x] `src/zkm/conformance.py` — new module (static + dynamic checks, `validate_frontmatter`, `FRONTMATTER_REQUIRED`) <!-- id:32a0 -->
- [x] `src/zkm/convert.py` — `conformance` field on `Plugin` dataclass + `load_plugin_manifest`
- [x] `src/zkm/cli.py` — `cmd_test` command
- [x] `tests/test_conformance.py` + `tests/fixtures/plugins/{good,bad_manifest,bad_signature,bad_frontmatter,no_fixtures}/` — 21 tests, all green
- [x] `plugins/zkm-eml/plugin.yaml` — added `conformance.config.source_dir: tests/fixtures/corpus`
- [x] `docs/plugin-spec.md` — documented `conformance:` block + `## Conformance (zkm test)` section
- [x] `TODO.md` — closed `aa77`
