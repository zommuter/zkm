# 2026-05-14 — M2: per-store YAML config (retire `.env`)

**Started:** 2026-05-14 12:32
**Session:** 795ab1df-5a0a-4809-b573-bce0fea5ac83
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Replace the ad-hoc `.env` + `.zkm-config` pair with a single `zkm-config.yaml` + `.zkm-secrets.yaml` per-store config pair that supports structured values and is shared across core and all plugins.

## Context

M2 was promoted from the zkm-eml backlog (migrated from `plugins/zkm-eml/TODO.md` on 2026-05-13). The pain points driving it:

1. **CSV-overloaded keys** — `EML_FOLDERS_EXCLUDE` (7-item list), `NOTMUCH_TAGS_EXCLUDE` (8+ items) are comma-joined strings in `.env`. No quoting, no nesting.
2. **Two-file drift** — `.zkm-config` holds `binary_backend`; `.env` holds plugin config + core LLM credentials. Separate parsers, separate locations, separate mental models.
3. **Session 15 prerequisite** — WhatsApp scoping needs per-account sub-structure that flat `KEY=VALUE` cannot express.

Chosen dispatch: **Class 2** — direction was clear from TODO text and prior meetings; no multi-persona debate needed. Two topology/migration questions were answered by the user before drafting the plan.

## Plan

See `/home/tobias/.claude/plans/velvety-nibbling-blossom.md` for the full approved plan. Summary:

**Architecture decisions:**
- **Topology**: `<store>/zkm-config.yaml` (non-secrets, committed) + `<store>/.zkm-secrets.yaml` (chmod 0600, gitignored). Retires both `.env` and `.zkm-config`. No per-plugin files.
- **Secret boundary**: `secret: true` field in `plugin.yaml` (already in plugin-spec.md:40); `_SECRET_RE` regex as fallback. Core LLM/embed keys declared in `src/zkm/config.py:_CORE_SCHEMA`.
- **Migration**: hard cutover — no read-both fallback. `zkm config migrate [--apply]` is the one-shot migrator; `.env` is renamed to `.env.migrated`, not deleted. Dry-run default (mirrors `zkm scrub` pattern).
- **Fail-loud guard**: `load_config()` raises `ClickException` if `.env` is present and contains non-secret keys.
- **`os.environ` scope**: retained for runtime toggles only (`ZKM_BYPASS_*`, `ZKM_REPROCESS`, `ZKM_STORE`); regular config no longer consults `os.environ`.

**Key findings from exploration:**
- Current `.env` has no plugin credentials — zkm-eml reads `~/mail` (local), all other plugins take filesystem paths/switches. Credentials in actual use today: `ZKM_LLM_KEY`, `ZKM_EMBED_KEY`, `ZKM_LLM_EXPAND_KEY` (core only).
- `EML_SLUG_ASCII` at `naming.py:11` is the one plugin var read directly from `os.environ` outside the schema flow — must be added to `plugin.yaml` and routed through config dict.
- `convert.py:274-296` is the single chokepoint for source-of-truth merging — small surface to refactor.
- `yaml.safe_load` pattern already used at `convert.py:63,126` and `patterns.py:194` (gazetteer); reuse is clean.

**YAML schema (approved):**

```yaml
# zkm-config.yaml
core:
  binary_backend: none
  llm: { endpoint: "http://localhost:8080/v1", model: gemma4-e4b }
  embed: { chunk_chars: 2000, chunk_overlap: 200 }
  expand: { timeout: 30.0, cold_timeout: 180.0 }
  query: { low_dense_threshold: 0.5, low_bm25_threshold: 1.0, max_doc_chars: 500 }

eml:
  source_dir: ~/mail
  folders_exclude: [Trash, Junk, Spam, "[Gmail]/Trash"]   # was CSV
  keep_originals: true
  owner_addresses: []
  attachment_inbox: true
  quote_strip: true
  slug_ascii: false

# ner, pdf, photo, scan, notmuch follow same snake_case pattern

# .zkm-secrets.yaml (chmod 0600, gitignored)
core:
  llm: { key: sk-... }
  embed: { key: sk-... }
  expand: { key: sk-... }
```

## Implementation findings

*Not yet — design-only at time of writing. Populate after the implementation session.*

## Decisions

- **Single shared YAML, not per-plugin files.** One `zkm-config.yaml` at store root; no `<store>/.zkm/<plugin>.yaml` split. Whatsapp multi-account will fit naturally as `whatsapp.accounts: [...]` within the same file.
- **Hard cutover, no read-both.** Post-migration `.env` presence with non-secret keys is a fatal error. Existing stores run `zkm config migrate --apply` once.
- **Secrets stay separate.** `.zkm-secrets.yaml` mirrors the YAML structure but is never committed. `zkm-config.yaml` itself IS committed (no secrets there).
- **`os.environ` removed from regular-config path.** Only `ZKM_BYPASS_*`, `ZKM_REPROCESS`, and `ZKM_STORE` remain env-var-based.
- **User-level / tool-side config deferred.** `~/.config/zkm/` revisitable if "store backup includes LLM keys" becomes a pain; not addressed today.
- **Schema typing deferred.** YAML parses scalars to Python primitives (bool, int, float); no JSON Schema validation layer yet.
- **`zkm config` UI scope: `migrate`, `show`, `validate` only.** `set`/`unset` deferred.

Out of scope: multi-account YAML shape (Session 15), schema typing, tool-side config, PyPI publishing impact.

## Action items

- [ ] **C1.** `src/zkm/config.py` (new) — `load_config(store) -> StoreConfig`; `StoreConfig.for_plugin(name)`; `StoreConfig.core_value(*path)`; `_assert_env_cutover(store)`; `_CORE_SCHEMA`. Contract: `load_config` raises `ConfigError` (sub-`ClickException`) if `.env` has non-secret keys; YAML load is `yaml.safe_load`; unknown keys emit warnings.
- [ ] **C2.** `tests/test_config.py` (new) — YAML round-trip; secret/non-secret split; precedence; `.env` fail-loud; chmod 0600 enforcement; `migrate` round-trip; `validate` unknown-key + missing-required.
- [ ] **C3.** `src/zkm/convert.py:164-298` — replace `load_env`/`append_env`/`prompt_required_config` with `load_config(store).for_plugin(plugin_name)`; rewrite `prompt_required_config` to write into YAML files.
- [ ] **C4.** `src/zkm/store.py:74,100-166` — `init_store()` writes minimal `zkm-config.yaml`; `read_zkm_config()` thin alias to `load_config(...).core_value("binary_backend")`; add `.zkm-secrets.yaml` to `_GITIGNORE`.
- [ ] **C5.** `src/zkm/query.py:494-555`, `embed.py:64-72,362-370`, `expand.py:214-215` — replace `_get()`-via-env with `cfg.core_value(...)` calls; explicit kwargs stay as highest-precedence override.
- [ ] **C6.** `plugins/zkm-eml/src/zkm_eml/naming.py:11` — drop direct `os.environ["EML_SLUG_ASCII"]`; add `slug_ascii` to `plugin.yaml`; receive via config dict.
- [ ] **C7.** All `plugins/*/plugin.yaml` — rename keys to bare snake_case (`source_dir` not `EML_SOURCE_DIR`); ensure `secret: true` is present where needed (none today — just the field is available).
- [ ] **C8.** `src/zkm/cli.py` — `zkm config` command group: `migrate [--apply]`, `show [--include-secrets]`, `validate`. Dry-run default on migrate.
- [ ] **C9.** `docs/plugin-spec.md` (Config + Secret management sections) — rewrite to describe YAML topology and `for_plugin()` contract.
- [ ] **C10.** `CLAUDE.md`, `docs/install.md`, `README.md` — update `.env`/`.zkm-config` references; document migration step for existing stores.
- [ ] **C11.** Version bump + tag zkm core (M2 is a feature — loose-0.x → minor bump).
