# zkm — Phase 2 TODO

See `CLAUDE.md` for architecture overview. See `docs/phase2-plan.md` for sequencing.
Completed Phase 1 tasks archived in `docs/phase1-done.md`.

## Phase 2 session 6 — hybrid search quality

- [x] Widen dense candidate pool from `top_k*3` to `max(top_k*20, 200)` — clears literal-match saturation so cross-lingual hits enter RRF fusion — covered by tests/test_query_recall.py on 2026-05-07
- [x] Add `SearchTrace` dataclass; three silent BM25-only fallbacks now set a `dense_skipped_reason`; CLI emits stderr warning on skip — covered by tests/test_query_recall.py on 2026-05-07
- [x] Add `--expand` flag to `zkm search` (opt-in LLM expansion for cross-lingual recall; `zkm query` keeps expansion default-on) — covered by tests/test_query_recall.py on 2026-05-07
- [x] New `zkm doctor` subcommand: md/bm25/embed doc counts, stale-index detection, embed + LLM endpoint probes — manually verified on real store 2026-05-07
- [x] Updated `docs/field-test-bge-m3.md`: realistic step 3 (--expand required on literal-heavy corpora), diagnostic checklist — 2026-05-07
- [x] Fix `expand.py` parser bugs: `_parse_keywords` handles inline comma/quote-separated and section-header formats; `_parse_hypothetical_text` handles `Section 2` marker without blank line and strips label prefix; bilingual prompt + `_PROMPT_HASH` cache invalidation — covered by tests/test_expand.py (20 tests) on 2026-05-07
- [x] Bilingual expand model audit — live-tested all configured models + aya-expanse-8b + Apertus-8B against the exact _EXPANSION_PROMPT; finding: aya-expanse-8b is the only local model that reliably emits EN+DE keywords for both DE and EN questions; tightened _EXPANSION_PROMPT ("3 EN then 3 DE phrases, translate into the OTHER language"), made _parse_keywords cross Section-2-marker blank lines (aya markdown format), skip **Language:** sub-headers, strip <|END_OF_TURN_TOKEN|>; added aya-expanse-8b to /etc/llama-swap/config.yaml; updated docs/field-test-bge-m3.md with live-test model table + bilingual probe — covered by tests/test_expand.py (21 tests) on 2026-05-07

## Phase 2 session 7 — aya expansion bugs (3 blockers found in live test)

- [ ] **5-keyword cap kills German half**: aya produces 6 EN + 6 DE phrases; `keywords[:5]` cap is hit after the first 5 English ones, no German keywords survive. Fix: raise cap to ≥8, or enforce per-language balance (keep up to 3 per detected language before capping)
- [ ] **`Section 1 — Search terms` leaks as keyword when no trailing colon**: aya sometimes emits `Section 1 — Search terms\n` (no `:`) — the section-label regex `^Section\s*\d+\s*[—–\-]+\s*[^:]+:\s*` requires a colon so it doesn't strip it; the `—` gets eaten by the punctuation strip leaving `'Section 1  Search terms'` as a keyword. Fix: make the colon optional in the regex
- [ ] **Stale expansion cache**: entries for "Rechnung" and similar queries were written when aya was echoing the instruction text (`kws=['one per line','no blank lines','no bullets']`). Must be cleared before field-testing. Fix: `rm ~/knowledge/.zkm-index/expansion-cache.json` as a one-off; longer term consider a per-model cache key so model swaps auto-invalidate

## Query quality (post-MVP backlog)

- [ ] **Field-test on real store** — run through updated `docs/field-test-bge-m3.md` sequence: steps 3+4 with `--expand`, step 5 end-to-end query; collect remaining retrieval failures (blocked on session 7 fixes above)
- [x] Separate expansion model from answer model — `ZKM_LLM_EXPAND_MODEL` / `ZKM_LLM_EXPAND_ENDPOINT` / `ZKM_LLM_EXPAND_KEY`; `_resolve_expand_config` falls back to main LLM config; `zkm doctor` shows expand endpoint when it differs — covered by tests (203 zkm tests passing) on 2026-05-07
- [x] Surface expansion terms to the user (`zkm query --show-expansion`) for transparency and debugging — `--show-expansion` flag on both `zkm search` and `zkm query`; keywords + hyp_text plumbed through `SearchTrace`; 3 new tests (206 passing) — 2026-05-07
- [ ] Doc chunking for long emails/threads (current: first 2000 chars per doc, single embedding)

## Phase 2 session 1 — zkm-eml hot-fix

- [x] `originals.py:_merge_inbox_sidecar` + `_merge_cas_sidecar` — change producer dedup key from rendered `.md` path to producer's source-content `sha256` (`raw_sha256` for messages). Source content is stable across runs; rendered paths are not — 2026-05-07
- [x] `thread_index.py:41` — replace bare `except Exception: continue` with narrow `except (OSError, yaml.YAMLError)` + `logger.warning(...)`. A load failure must never silently become a `_1.md` duplicate — 2026-05-07
- [x] Regression tests in zkm-eml: `test_inbox_sidecar_stable_under_message_path_drift`, `test_cas_sidecar_dedup_by_sha256` — assert `producers[]` length stable under path drift — 2026-05-07

## Phase 2 session 2 — embed index fixes

- [x] `embed.py:save_embed_store` — make checkpoint write atomic (write to tmp path + `os.replace`) so an interrupted embedding run cannot corrupt the NPZ file — covered by `test_save_embed_store_atomic_under_interrupt` (test_embed.py) on 2026-05-07

## Phase 2 session 3 — core library

See `docs/object-storage.md` for the spec contract.

- [x] `src/zkm/atomic.py` — `write_atomic(path, content)` (tmp + rename) — covered by tests/test_atomic.py on 2026-05-07
- [x] `src/zkm/hashing.py` — `sha256_file(path)`, `git_blob_sha1(path)` — covered by tests/test_hashing.py on 2026-05-07
- [x] `src/zkm/cas.py` — `write_object(store, subdir, path_or_bytes) -> Path`, idempotent, returns `<subdir>/_objects/<aa>/<rest>` — covered by tests/test_cas.py on 2026-05-07
- [x] `src/zkm/sidecar.py` — read / `merge_producer` / rebuild `.origin.json` per spec v1; atomic write; producer dedup on `sha256`; sort by `message` — covered by tests/test_sidecar.py on 2026-05-07
- [x] `src/zkm/inbox.py` — `symlink_with_sidecar(cas_object, link_dir, producer)` implementing one-canonical-symlink-per-CAS-object — covered by tests/test_inbox.py on 2026-05-07

## Phase 2 session 4 — plugin migration

(Only after session 3 core library is complete and field-tested.)

- [x] `examples/zkm-notes/convert.py` — adopt `zkm.atomic.write_atomic` (currently writes non-atomically, contradicts plugin-spec.md) — covered by tests (164 zkm tests passing) on 2026-05-07
- [x] `zkm-eml` — replace in-plugin atomic/CAS/sidecar/symlink helpers with imports from core; delete the copied implementations in `originals.py` — covered by tests (103 zkm-eml tests passing, originals.py 481→294 lines) on 2026-05-07
- [x] All existing plugin tests still pass; `zkm-eml/originals.py` shrinks — 103 passed, 294 lines on 2026-05-07

## Phase 2 session 5 — hygiene commands

(Only after one week of session 4 in real use, per `docs/phase2-plan.md`.)

- [ ] `zkm rm <path>` — remove a managed `.md`; decrement sidecar `producers[]`; if last producer, remove the inbox symlink; if CAS object now unreferenced, remove it. Dry-run by default; `--apply` to commit.
- [ ] `zkm gc` — scan all sidecars; CAS objects with empty/missing producers are reported (dry-run) or removed (`--apply`)

## `zkm store` — git-like store management

The store is a git repo; zkm should expose a thin wrapper that handles
git-annex / git-lfs automatically so the user doesn't have to think about it.

- [x] `zkm remote add <name> <url>` — `git remote add` on the store — covered by tests/test_store_commands.py on 2026-05-07
- [x] `zkm remote list` — list store remotes — covered by tests/test_store_commands.py on 2026-05-07
- [x] `zkm clone <url> [path]` — clone a store; auto-detect annex/lfs from `.zkm-config` and re-initialise — covered by tests/test_store_commands.py on 2026-05-07
- [x] `zkm push [remote]` — push store commits; if annex: `git annex sync --content <remote>`; if lfs: `git lfs push --all <remote>`; else plain `git push` — covered by tests/test_store_commands.py on 2026-05-07
- [x] `zkm pull [remote]` — pull/rebase store commits; if annex: `git annex sync <remote>`; if lfs: `git lfs pull`; else plain `git pull --rebase` — covered by tests/test_store_commands.py on 2026-05-07
- [x] `--content` flag for `zkm push/pull` with annex: sync actual file content to/from remote (default: metadata only) — covered by tests/test_store_commands.py on 2026-05-07

Design note: these commands read `.zkm-config` to know the backend and dispatch accordingly. The user never has to type `git annex` directly.

## Incremental processing (backlog)

- [ ] **mbsync post-commit hook** — mbsync writes to a git repo; a post-commit hook there could trigger `zkm convert zkm-eml` automatically after each sync, removing the need for manual or cron-based invocation.
- [x] **zkm-eml: git-commit watermark** — state file `<store>/.zkm-state/zkm-eml.json` keyed by source repo path; `iter_messages_since` fast-enumerates via `git diff`; full-scan fallback when watermark absent/unreachable or source not a git repo — covered by tests (111 zkm-eml tests passing) on 2026-05-07
- [x] **zkm index: git-commit watermark** — watermark at `<store>/.zkm-index/last-commit`; `build_index` fast path via `git diff --name-status`; `--full` flag for forced rescan; `write_watermark` called from `cmd_index` after `save_index` — covered by tests (193 zkm tests passing) on 2026-05-07

## Encoding / text quality (backlog)

- [ ] **Text file encoding issues** — emails and other plugin outputs can carry mis-decoded bodies (Latin-1 read as UTF-8, mojibake umlauts, BOM headers, mixed encodings within a single message). Audit `zkm-eml` decode paths and add a normalization pass (detect-and-transcode or at minimum chardet fallback). Add test fixtures with known-bad encodings. Surfaces downstream as broken stemming and tokenization for accented characters.
