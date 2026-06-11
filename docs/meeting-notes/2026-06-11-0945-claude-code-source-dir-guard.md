# 2026-06-11 — zkm-claude-code: source_dir guard + nonexistent path handling

**Started:** 2026-06-11 09:45
**Session:** c023f980-e567-4ef4-baf2-3be7f0b8440c
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Fix source_dir misconfiguration that caused store subdirs to be scanned instead of ~/.claude/projects

## Context

TODO item: "zkm-claude-code: default source_dir scans store instead of ~/.claude/projects" —
`zkm convert claude-code` without config picked up `chat/whatsapp` and other store subdirs.
Root cause hypothesis in TODO: default not applied, or `_find_project_dirs` running against store path.

## Plan

1. Trace through `run_convert` → confirmed default IS applied correctly: `plugin.yaml` `default: "~/.claude/projects"` flows through `run_convert`'s config_keys loop.
2. Identify the real issue: `_find_project_dirs` had no guard for a non-existent root (FileNotFoundError), and there was no guard against `source_dir` pointing inside the store (the actual misconfiguration vector).
3. Fix both in `plugins/zkm-claude-code/convert.py`.
4. Add 3 new tests to cover the no-config default, nonexistent source, and store-internal rejection.

## Implementation findings

- `_resolve_source({})` correctly returned `~/.claude/projects` expanded — default plumbing was never broken.
- The store-internal guard was missing: if a user accidentally set `source_dir` to the store path (or a subdir like `sessions/`), `_find_project_dirs` would scan it silently.
- `test_convert_multi_project_root` used `store == tmp_path` (pytest fixture identity), so the new guard caught it. Fixed by using `tmp_path_factory.mktemp("source")` for an independent source dir.
- All 34 tests pass.

## Decisions

- `_find_project_dirs` returns `[]` (not an error) when root doesn't exist — matches "no sessions found" semantics.
- `convert()` raises `ValueError` (not a warning) when `source_dir` resolves inside `store_path` — this is always a misconfiguration; fail loud.
- `is_relative_to()` used for the check (Python 3.9+, required is 3.11+).
- Version bumped to 0.1.1 (patch: bug fix only).

## Action items

- [x] Fix shipped and pushed to fievel:src/zkm-plugins/zkm-claude-code.git as v0.1.1 <!-- id:5643 -->
