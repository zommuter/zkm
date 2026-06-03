# 2026-06-03 — Verb-order decision: keep verb-first

**Started:** 2026-06-03 15:47
**Session:** 5a985dd3-c165-4ae4-aa30-fab65a3b4095
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Decide whether plugin-scoped commands stay verb-first (`zkm convert <plugin>`) or switch to plugin-first (`zkm <plugin> convert`), deferred from 2026-05-11-1401.

## Context

The 2026-05-11 plugin-name-prefix meeting (see `2026-05-11-1401-plugin-name-prefix.md`) narrowed the open question to verb order only and deferred it explicitly. The TODO item read: `zkm convert <plugin>` vs `zkm <plugin> convert` / `zkm <plugin> run`; the latter matches git-plugin style and disambiguates status display.

## Plan

Explored `cli.py` and `convert.py` before deciding.

**Key finding:** The original status-display motivation is already resolved. `cli.py:972` renders the CMD column as `convert(eml)` via `f"{cmd_base}({args[0]})"` — the plugin name appears next to the verb. No ambiguity remains.

**Plugin-first (`zkm <plugin> convert`) cost analysis:**
- Plugin names are runtime-only (`convert.py:114` `list_plugins()` scans entry-points + filesystem at invoke time; `convert.py:151` `find_plugin()` is called inside command bodies). They cannot be statically declared as Click subcommands at module-import time.
- A `zkm <plugin> convert` grammar would require a custom lazy `click.Group` subclass overriding `list_commands()`/`get_command()`.
- It creates two grammars: `zkm eml convert` but `zkm index` / `zkm search` / `zkm status` stay flat. Namespace-collision risk if a plugin is ever named `index`, `search`, etc.
- Every `["convert", …]` / `["scrub", …]` / `["test", …]` test arg list, the mbsync hook (`plugins/zkm-eml/hooks/post-commit:7`), and all docs would require editing.

**Verb-first (status quo) cost:** zero.

## Decisions

- **Verb-first is canonical:** `zkm convert <plugin>`, `zkm scrub <plugin>`, `zkm test <plugin>`. Plugin name is a runtime positional arg; verbs are a static closed set of three.
- **No lazy `MultiCommand`**, no plugin-first reorg.
- **Convention documented** in `docs/plugin-spec.md` under the Naming convention paragraph.
- **TODO item closed.**

Out of scope: `cli.py`/`convert.py` code change, test edits, mbsync-hook change, CMD-column change (already correct).

## Action items

- [x] Add verb-order convention note to `docs/plugin-spec.md` — done.
- [x] Mark `TODO.md:118` `- [x]` with rationale — done.
