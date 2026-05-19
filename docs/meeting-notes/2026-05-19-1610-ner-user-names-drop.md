# 2026-05-19 — Drop zkm-ner `user_names` greeting filter (no replacement)

**Started:** 2026-05-19 16:10
**Session:** c20080a4-0b97-42ac-b70d-865339f429f6
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🧬 Nora (IE/NER typology — onboarded), 📬 Pim (PIM engineering — onboarded)
**Topic:** Does the v0.14.0 `user_names` greeting-phrase filter make sense as designed, or should it be redesigned / dropped?

## Agenda
1. Factual baseline: what does the filter actually scrub vs. what the user believes it scrubs?
2. Is name-keyed greeting-phrase post-filtering the right layer, or is the root cause NER mis-bracketing?
3. Decision: drop / keep / replace — and the evidence that should gate it.

## Discussion

### Agenda 1 — Factual baseline

Archie anchored the behaviour in code. `drop_salutation_blocklist(entities, extra=user_salutations)` (`textfilter.py:141-151`) drops an entity **only when its entire normalised value** (`e.value.strip().lower()`) is in `_SALUTATION_BLOCKLIST | extra`. `build_user_salutations()` (`textfilter.py:89-111`) is a strict cross-product `f"{prefix} {name}"` over `_GREETING_PREFIXES` × configured names — every generated phrase is multi-token. With the live config `user_names: [Tobias, Kienzler, Zommuter]` the set is `{"hallo tobias", "herr kienzler", "dear zommuter", …}`. A bare entity value `"tobias"` is therefore **never** matched. The literal premise "scrubs any Tobias and Kienzler" is **not** what the code does — it only deletes an entity whose value is *itself* a mis-bracketed greeting+name super-span (e.g. `"Hallo Tobias"`).

Nora: that super-span is a **bracketing error**, not a valid entity. The 2026-05-15 design note records the motivation — `"Hallo Tobias"` ×1930 in the live store — i.e. the span detector systematically over-extended the greeting onto the name. Pim: greeting lines are *position-as-signal*; the production-correct fix is a positional pre-strip before NER, not a name-keyed denylist. Riku flagged that (a) the user's stated premise is factually not the code's behaviour, and (b) the shipped mechanism is narrow/tested/zero-regression, so a rewrite needs the own-name-vs-other-person split as gating evidence.

### Agenda 2 — Right layer?

Nora mapped this onto the 2026-05-10 4-class pollution taxonomy ("do not blend fix layers; stoplist beats fuzzy cleanup for closed-set garbage"). Archie noted any pre-strip would extend the existing `strip_markdown_artefacts()` pre-strip lever, not introduce a new mechanism. Petra framed three options (drop / keep / positional pre-strip) and N=2-cleared the pre-strip (both `convert()` and `scrub()` consume the chain; every user hits the mis-bracket).

### Agenda 3 — The 80-20 reframe (user-driven, decisive)

The user rejected the escalation: *"1930 'Hallo Tobias' is still just **one** wrong entity… consider the 80-20 rule… this feels like a wasteful rabbithole, prove me wrong."*

The personas conceded:
- **Archie:** the γ dedup key is `(scope, type, value)` (`2026-05-12-1500`). 1930 occurrences of `"Hallo Tobias"` collapse to **one** deduplicated record. The whole pollution is a *closed handful* of distinct values, not 1930 problems. "1930" was always an occurrence count.
- **Nora:** concedes against her own framing — under dedup this is **not** a new shape; it collapses into the taxonomy's closed-set-garbage bucket whose prescribed fix is the *static stoplist*, not a pre-strip. Pre-strip is for open sets; this is closed.
- **Pim:** the recovery argument evaporates — the name a pre-strip would "recover" from "Hallo Tobias," is the **recipient (the user)**, already out of scope as a self-entity. Pre-strip payoff here ≈ zero.
- **Riku:** vindicates the original "minimum evidence" gate — dedup cardinality *is* that evidence and points at do-the-least. The only honest counter would be if the set were open/growing; dedup shows it is closed.
- **Petra:** the 80-20 cut: remove `user_names` scaffolding; build nothing; the residual closed handful is one-line-fixable via the **already-existing** `_STOPLIST` / `drop_stoplist` (`textfilter.py:136-138`) if it ever annoys — a low-stakes, reversible, deferred call.

## Decisions

- **Remove the v0.14.0 `user_names` mechanism entirely** from zkm-ner: the `user_names` config key (`plugin.yaml` + `ner:` section consumption), `build_user_salutations()` and `_GREETING_PREFIXES`, the `extra=`/`user_salutations` threading through `extract.py` / `convert.py` (convert + scrub paths), the `user_names_hash` parameter in `version.py:model_version()`, and the associated v0.14.0 tests in `test_convert.py` / `test_scrub.py` / `test_textfilter.py`.
- **The static `_SALUTATION_BLOCKLIST` stays.** Only the dynamic user-name extension is removed; existing generic sign-off filtering is unchanged.
- **Build no replacement.** Explicitly **out of scope:** the positional greeting-prefix pre-strip (Nora/Pim's "correct layer") — its recovered token is the user-as-recipient, which is already excluded, so its value on this residue is ≈ zero.
- **Residual closed handful of greeting super-span values (`"Hallo Tobias"`, `"Guten Tag Herr Kienzler"`, `"Hello Tobias"`, …) is accepted as-is.** Documented escape hatch (not an action item): if they ever degrade entity pages / search, add each literal to the existing `_STOPLIST` — one line per value, no new mechanism. This is the taxonomy-prescribed closed-set-garbage path.
- **Cache invalidation:** removing the filter changes `extract()` output (the super-spans return), so the textfilter cache token must bump (e.g. `v6 → v7`) and the `user_names_hash` cache-key component is removed with it. No forced re-scrub is mandated — existing entries remain a usable baseline; recomputation happens naturally on the next convert/scrub.
- **Version:** feature removal / behaviour change → **minor** bump under loose-0.x (`0.14.0 → 0.15.0`), tagged `v0.15.0` in the same commit, `uv publish` after (per `CLAUDE.md`). Note Session B gate — plugin wheels are 0.0.1 stubs until entry-point discovery; the bump-and-tag applies to the repo regardless.
- **User store follow-up (not a repo change):** remove the `ner: { user_names: [...] }` block from the private `<store>/zkm-config.yaml`. Harmless if left (the key becomes inert once the consuming code is gone) but should be cleaned for clarity.

## Action items

- [ ] **Remove `user_names` mechanism from zkm-ner** — delete config-key consumption (`plugin.yaml`, `convert.py` both convert + scrub paths), `build_user_salutations()` + `_GREETING_PREFIXES` + `drop_salutation_blocklist(extra=)` kwarg (`textfilter.py`), `user_salutations` threading (`extract.py`), `user_names_hash` (`version.py`). Keep static `_SALUTATION_BLOCKLIST`. Future test: a configured-name greeting super-span (`"Hallo Tobias"`) is **retained** by `extract()` (no longer filtered); static sign-offs (`"best regards"`) still filtered. (`docs/meeting-notes/2026-05-19-1610-ner-user-names-drop.md`)
- [ ] **Bump textfilter cache token (`v6 → v7`) and drop the `user_names_hash` cache-key component** in `version.py`; verify `model_version()` no longer takes `user_names_hash`. Future test: `model_version()` signature has no `user_names_hash`; token string is `textfilter-v7`-based. (same note)
- [ ] **Version bump zkm-ner `0.14.0 → 0.15.0` + tag `v0.15.0` in the same commit + `uv publish`** (loose-0.x: feature removal = minor). Sync `PLUGIN_VERSION` in `convert.py` and `plugin.yaml` if they carry a literal. (same note)
- [ ] **User store follow-up:** remove `ner: { user_names: [...] }` from private `<store>/zkm-config.yaml` (clarity only; inert once code is gone — not tracked as a repo deliverable). (same note)

Out of scope (explicitly not action items): positional greeting-prefix pre-strip; proactive `_STOPLIST` additions for the residual super-spans (deferred escape hatch only).
