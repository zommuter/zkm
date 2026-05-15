# 2026-05-15 — Runtime user-identity config for zkm-ner

**Started:** 2026-05-15 11:08
**Session:** ce916403-3457-4946-9a20-3dc3d5d1aedd
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Add a `user_names` config key to zkm-ner so users can extend the greeting-salutation stoplist at runtime without editing source.

## Context

zkm-ner's `_SALUTATION_BLOCKLIST` (`textfilter.py:42-64`) uses placeholder names ("maxine", "mustermann") per the published-generic decision (`2026-05-12-0844-publish-plugins.md`). Real users therefore get zero filtering benefit for greetings containing their actual name. The top remaining FPs in the live store were `'Hallo Tobias' ×1930`, `'Guten Tag Herr Kienzler' ×444`, `'Hello Tobias' ×392` (TODO.md final-state notes).

Action item A11 from the publish-plugins meeting requested a runtime config knob so users inject their names in their private store config. TODO.md:167 spec: "spec a `ZKM_NER_USER_NAMES` env var (or per-store config entry)".

## Plan

Two design decisions resolved via AskUserQuestion before implementation:

1. **Config mechanism:** YAML `ner:` key (`user_names` list) in `<store>/zkm-config.yaml` — NOT an env var. The M2 config refactor (`2026-05-14-1232-m2-per-store-yaml-config.md`) deliberately removed env vars from the regular-config path; `StoreConfig.for_plugin("ner")` already delivers declared `plugin.yaml` keys to `convert(store, config)`.

2. **Semantics:** name-list + templated greetings. User lists name forms (`["Tobias", "Kienzler"]`); plugin cross-products a closed `_GREETING_PREFIXES` frozenset × names → lowercase blocked phrases (e.g. `"hallo tobias"`, `"guten tag herr kienzler"`). Bare names are never in the output so `Tobias Kienzler ×11270` PERSON survives intact.

**Cache invalidation:** `user_names` changes `extract()` output, requiring two invalidation layers:
- `textfilter-v5` → `textfilter-v6` in `version.py` (one-time code-change invalidation)
- `hashlib.sha256(repr(sorted(user_sal)).encode()).hexdigest()[:8]` folded into `model_version(model_name, user_names_hash=...)` for per-user / per-edit invalidation. `scrub()` re-filters frontmatter directly and doesn't use `model_version` — no change needed there.

**Bundled drift fix:** `plugin.yaml:version` and `convert.py:PLUGIN_VERSION` were stale at `0.1.0` vs authoritative `pyproject.toml` `0.13.0`. Synced to `0.14.0` in the same commit (single-source-of-truth).

## Implementation findings

- 9 files changed, 263 insertions(+), 23 deletions(-)
- `_GREETING_PREFIXES` frozenset (20 entries): hallo, hello, hi, hey, dear, lieber/liebe/liebes, guten tag/morgen/abend, herr, frau, hallo herr/frau, guten tag herr/frau, sehr geehrter herr, sehr geehrte frau, lieber herr, liebe frau.
- `build_user_salutations()` accepts `list[str]` or `str` (comma/newline split); normalises internal whitespace; empty/None → `frozenset()`.
- `drop_salutation_blocklist(entities, extra=frozenset())` — backward-compatible default; blocked = static list | extra.
- `extract()` gained `user_salutations: frozenset[str] | None = None` kwarg (built once in `convert()`/`scrub()`, not per-document).
- Existing test mock signatures updated: `user_salutations=None` added to `counting_extract` and `scoped_extract` in `test_convert.py`.
- 266 zkm-ner tests pass (up from 249); 457 core tests pass — unaffected.
- `autotag` hook ran and tagged `v0.14.0` in the commit.

## Decisions

- `user_names` is a YAML list key in the `ner:` plugin config section. Env var path explicitly rejected (M2-inconsistent). Published plugin default remains `[]` (no built-in personal names).
- Greeting-phrase generation is deterministic cross-product (closed prefix set × user names) — no fuzzy matching, no bare-name blocking.
- Cache key: `textfilter-v6` token (one-time) + `usernames:<hash8>` suffix when list is non-empty (per-edit); `scrub()` unaffected (reads frontmatter directly).
- `plugin.yaml` version and `PLUGIN_VERSION` in `convert.py` synced from stale `0.1.0` to `0.14.0` as a bundled drift fix.
- Out of scope: honorific/gender inference beyond the static prefix set; per-file gazetteer YAML; env-var path; touching `_STOPLIST` / `_COMMONNOUN_STOPLIST`.

## Action items

- [x] All implementation complete in this session (zkm-ner v0.14.0, tag `v0.14.0`).
- [ ] **User follow-up:** add `ner: { user_names: [Tobias, Kienzler, "Tobias Kienzler"] }` (or preferred forms) to `<store>/zkm-config.yaml`, then run `zkm scrub ner` to retroactively remove the remaining greeting-FPs from the live store. Run `zkm convert ner` for ongoing filtering on new mail.
