# 2026-05-11 — Plugin name convention: drop `zkm-` prefix

**Started:** 2026-05-11 14:01
**Session:** 5fb4115f-8393-45f5-a808-98fa896fafa5
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), Zommuter (user)
**Topic:** Normalise plugin manifest `name:` fields — drop the redundant `zkm-` prefix; decide backwards-compat, live-store migration scope, and the linked verb-order question.

## Past meetings audit

- 2026-05-11-0946 (NER next after N9b): all N9c-1..8 done; N9c-9, N9d, N9e correctly in backlog; N10/N11/CLAUDE.md bundled and deferred; status observation TODO present; meeting-style.md updated. **No orphans.**

## Agenda

1. Current state: 4/7 plugins already bare, 3 (eml/pdf/photo) prefixed — pick target convention.
2. Backwards-compat: `find_plugin()` exact-match vs strip-on-input.
3. Live-store migration: `source: zkm-eml` in ~29k existing md files.
4. Plugin directory names and verb order — fold in or defer?

## Discussion

### Item 1 — Target convention

**🏗️ Archie:** Verified all 7 `plugin.yaml` files. Split tracked history: prefixed plugins are pre-Phase 2.5 (eml/pdf/photo); bare ones came later. Convergence was by accident, not policy. `find_plugin()` does exact match on `p.name` — so `zkm convert zkm-eml` works, `zkm convert eml` does not; `zkm convert ner` works, `zkm convert zkm-ner` does not. Inconsistent.

**😈 Riku:** Two options: (a) bare everywhere, (b) prefixed everywhere. User framing ("shouldn't be there") rules out (b).

**✂️ Petra:** Bare wins every axis: shorter CLI, no redundancy with dir name, 4/7 already there — migration cost minimal (3 files flip).

**User:** Investigate first, "and don't forget to update the mbsync hook!"

### Investigation results

Live sidecar spot-check (`*.origin.json`): already bare (`"plugin": "eml"`). No churn needed on sidecars.

Frontmatter `source:` in live store: prefixed (`source: zkm-eml` in ~29k mail md files). Wired via `frontmatter.py:12` constant `PLUGIN_NAME = "zkm-eml"` and `thread_index.py:127` literal. **Late finding:** pdf and photo PLUGIN_NAME constants were already bare (`"pdf"`, `"photo"`) — store has bare values for those. Only eml has prefixed source field in the store.

mbsync hook (`plugins/zkm-eml/hooks/post-commit:7`): `zkm convert zkm-eml && zkm index --no-embed` — user-flagged.

Test assertions: `test_convert.py:34` hardcoded `"zkm-eml"`. `test_runstate.py:45,50` literal `args=["zkm-eml"]`. Test fixtures in `test_devcheck.py` and `test_scrub.py` wrote `name: zkm-{name}` in plugin.yaml — must go bare.

No production code branches on `source:` field — verified via grep of `query.py`, `index.py`.

### Item 2 — `find_plugin()` backwards-compat

**User:** "let's have zkm auto-remove an accidental `zkm-` prefix on plugin names for backward compatibility."

**🏗️ Archie:** Two variants — (i) strip-on-miss, (ii) always-strip. User framing ("the prefix shouldn't be there") makes always-strip an asset — it closes the door on plugins legitimately named `zkm-anything`.

**✂️ Petra:** (ii). One line: `name = name.removeprefix("zkm-")` before lookup.

**😈 Riku:** Accepted as a hard convention going forward; document in plugin-spec.md.

### Item 3 — Live-store migration

**🏗️ Archie:** Options: (α) manifest-only (deepens inconsistency), (β) manifest + code constants, leave store files as historical data, (γ) full migration pass on 29k files.

**✂️ Petra:** β. Store inconsistency is paper-cut; new writes converge; no runtime reader filters on `source:` field.

**😈 Riku:** Initial sidecar concern withdrawn after grep confirmed no readers.

**User:** β.

### Item 4 — Dir names and verb order

**User:** "Manifest names only, never rename the plugin directories since *there* the `zkm-` prefix makes sense as repo for upstream consistency."

Verb-order deferred to its own meeting (TODO item stays open).

## Decisions

1. **Bare manifest names.** `plugin.yaml` `name:` field is the bare CLI handle — no `zkm-` prefix. Three manifests changed: eml/pdf/photo. Directory names (`plugins/zkm-*`) unchanged — namespace serves upstream repo-level consistency.
2. **β live-store migration.** Code constants + manifests changed. Existing `source: zkm-eml` in ~29k mail md files left as historical data — no migration pass. pdf/photo source fields were already bare.
3. **`find_plugin()` always-strips `zkm-` prefix** from input (`name.removeprefix("zkm-")`). Closes the door on legitimately-prefixed plugin names as a hard convention. Documented in `docs/plugin-spec.md`.
4. **mbsync hook updated** (`hooks/post-commit:7`): `zkm convert eml`.
5. **Verb-order deferred.** Linked TODO stays open; this meeting narrowed it to verb-order only.

**Out of scope:** plugin dir renames, fievel mirror renames, verb-order decision, store-wide `source:` field rewrite, `plugin.yaml` ↔ `pyproject.toml` version drift (pre-existing).

## Action items

- [x] `plugins/zkm-eml/plugin.yaml` — `name: zkm-eml` → `name: eml`; desc prose updated; `pyproject.toml` 0.6.1→0.7.0; tagged `v0.7.0`
- [x] `plugins/zkm-eml/src/zkm_eml/frontmatter.py:12` — `PLUGIN_NAME = "eml"`
- [x] `plugins/zkm-eml/src/zkm_eml/thread_index.py:127` — `"source": "eml"`
- [x] `plugins/zkm-eml/hooks/post-commit:7` — `zkm convert eml && zkm index --no-embed`
- [x] `plugins/zkm-eml/tests/test_convert.py:34` — assert `"eml"`
- [x] `plugins/zkm-eml/README.md` + `CLAUDE.md` — usage examples updated
- [x] `plugins/zkm-pdf/plugin.yaml` — `name: pdf`; `pyproject.toml` 0.1.1→0.2.0; tagged `v0.2.0`
- [x] `plugins/zkm-photo/plugin.yaml` — `name: photo`; `pyproject.toml` 0.1.1→0.2.0; tagged `v0.2.0`; README updated
- [x] `plugins/zkm-notmuch/plugin.yaml` description prose updated
- [x] `src/zkm/convert.py:98-99` — `find_plugin()` strips `zkm-` prefix; `pyproject.toml` 0.3.0→0.4.0; tagged `v0.4.0`
- [x] `docs/plugin-spec.md` — naming convention paragraph added
- [x] `tests/test_plugin.py` — `test_find_plugin_accepts_zkm_prefix` added
- [x] `tests/test_devcheck.py` + `tests/test_scrub.py` — fixture plugin.yaml updated to bare names
- [x] `tests/test_runstate.py` — `args=["eml"]`; `src/zkm/runstate.py` docstring updated
- [x] All 5 repos pushed to fievel
- [ ] Update `docs/meeting-notes/meeting-style.md` Past meetings index (this item)
- [ ] Close "Meeting: plugin name convention + verb order" in TODO.md; reopen verb-order as standalone meeting item
