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

- [x] **5-keyword cap kills German half**: raised cap from 5 to 12 in `_parse_keywords` — aya's 6 EN + 6 DE output now fully survives; covered by `test_parse_keywords_caps_at_twelve` and `test_parse_keywords_aya_bilingual_six_plus_six` on 2026-05-07
- [x] **`Section 1 — Search terms` leaks as keyword when no trailing colon**: made trailing colon optional in section-label regex (`^Section\s*\d+\s*[—–\-]+\s*[^:]+:?\s*`) — covered by `test_parse_keywords_section_header_no_colon` on 2026-05-07
- [x] **Stale expansion cache on model switch**: cache key now includes model name (`_PROMPT_HASH + model + question`) so switching `ZKM_LLM_EXPAND_MODEL` auto-invalidates; existing bad entries in `~/knowledge/.zkm-index/expansion-cache.json` become unreachable (different key) — covered by `test_expand_query_cache_misses_on_different_model` on 2026-05-07. One-off clear still needed for the pre-fix bad entries: `rm ~/knowledge/.zkm-index/expansion-cache.json`
- [x] **Stale cache survives parser fixes**: added `_PARSER_VERSION = "v2"` constant folded into cache key; cache file now uses `{"_parser_version": "v2", "entries": {...}}` envelope; `_load_cache` discards and rewrites the file on version mismatch — future parser changes only need to bump `_PARSER_VERSION`; covered by `test_expand_query_cache_misses_on_parser_version_bump` and `test_expand_query_legacy_cache_format_ignored` on 2026-05-07

## Query quality (post-MVP backlog)

- [x] **Field-test on real store** — all 5 steps passed on 55125-doc store: hybrid beats BM25-only for DE queries (1→5 hits for "Stromrechnung"), DE→EN cross-lingual 43/50 ✓, EN→DE 1/50 (corpus is ~95% DE), semantic steps 4+5 work; one finding filed below — verified by user on 2026-05-07
- [x] **Rigorous cross-lingual anchors in field test** — replaced grep-count approach with disjoint-vocabulary pairs (O2 bills DE-only, Google Cloud/Cloudflare/AWS invoices EN-only); baselines exactly 0, --expand yields 11 EN and 3 DE hits; documented that shared proper-noun pairs (Hotel Katharinenhof) contaminate the test — verified live on 2026-05-07
- [x] **LLM conflates generic "Rechnung" docs with "Stromrechnung"** — confirmed corpus gap: no electricity utility bills in store (only one electricity-meter email from 2012); this is expected behaviour, not a retrieval bug; updated field-test step 5 queries to use O2/hotel which have real corpus coverage — confirmed 2026-05-07
- [x] Separate expansion model from answer model — `ZKM_LLM_EXPAND_MODEL` / `ZKM_LLM_EXPAND_ENDPOINT` / `ZKM_LLM_EXPAND_KEY`; `_resolve_expand_config` falls back to main LLM config; `zkm doctor` shows expand endpoint when it differs — covered by tests (203 zkm tests passing) on 2026-05-07
- [x] Surface expansion terms to the user (`zkm query --show-expansion`) for transparency and debugging — `--show-expansion` flag on both `zkm search` and `zkm query`; keywords + hyp_text plumbed through `SearchTrace`; 3 new tests (206 passing) — 2026-05-07
- [x] **Expansion timeout on cold model** — `_probe_model_loaded` checks llama-swap `/running` before the POST; if cold, timeout extends from 30s → 180s (configurable `ZKM_LLM_EXPAND_COLD_TIMEOUT`) with a stderr notice; expansion failure now returns typed reason (`"timeout" | "endpoint_error" | "parse_error"`); `zkm query` and `zkm search --expand` exit 2 on failure by default; `--allow-fallback` opts into silent BM25 fallback; `zkm doctor` always shows expand model load state — covered by 13 new tests (225 zkm tests passing) on 2026-05-07
- [x] **LLM hallucinates when corpus lacks the queried document type** — fixed via (c) + (a): system prompt now instructs the LLM to judge relevance first and say so when sources are off-topic; `zkm query` emits a stderr "top-hit relevance is low" warning when `hits[0].score` is below a per-backend floor (`ZKM_QUERY_LOW_BM25_THRESHOLD=1.0`, `ZKM_QUERY_LOW_DENSE_THRESHOLD=0.5`); field-test step 5b live-verified: "Stromrechnung" probe correctly refused (named O2 bills / meter-reading email, no invented figure); counter-test "O2 Herbst 2014" answered 14,98 EUR with citations — covered by `test_llm_stream_system_prompt_instructs_relevance_check` and `test_zkm_query_warns_on_low_relevance_score` (228 tests passing); live-tested on 55125-doc store on 2026-05-07
- [x] **`zkm query` sources list is unordered** — numbered Sources block `[1] path…` matches LLM's inline `[N]` citations; system prompt updated to request `[N]` style consistently — covered by tests/test_query_recall.py on 2026-05-07
- [x] Doc chunking (any long .md, not just emails/threads) — see `docs/meeting-notes/2026-05-08-doc-chunking.md`; decision: core feature, embed-side char-window chunker, file-level RRF — covered by session 8 (259 tests passing) on 2026-05-08

## Phase 2.5 — next plugins (decided 2026-05-08-next-plugins.md, 2026-05-08-information-flow.md)

Order: pre-flight specs → zkm.amendments lib → photo → pdf → scan → notmuch → (scoping) → whatsapp.
WhatsApp requires three core additions before its own session; see session 15.

Pre-flight sessions (9a–9d) must land before any plugin session starts.

- [x] Session 9a (pre-flight): add "MUST be no-op on unowned inbox items" rule to `docs/plugin-spec.md` (~1 paragraph); contract: plugin run against foreign-only inbox returns `[]` exit 0 — covered by docs updates on 2026-05-08
- [x] Session 9b (pre-flight): add paragraph to `docs/object-storage.md` confirming multi-producer-plugin sidecars are normal (e.g. photo + scan against same CAS object) — covered by docs updates on 2026-05-08
- [x] Session 9c (pre-flight): write the amendment contract section in `docs/plugin-spec.md`. Per-field merge rules: `tags` set-union; `entities` set-union with role-tagged dedup; scalars last-write-wins-with-`emitted_by`-attribution; structured lists need explicit merge keys. Amendment record schema: `{key: {message_id|sha256|path: ...}, fields: {...}, emitted_by: <plugin-name>, emitted_at: <iso8601>}`. Round-trip test: zkm-eml writes md with `tags:[]`; amendment with `tags:[bill]` lands; merged md shows `tags:[bill]` with attribution sidecar entry — covered by docs updates on 2026-05-08
- [x] Session 9d (pre-flight): design note for extraction-cache in `docs/object-storage.md`. Cache shape (per-CAS-object, multi-stage, per-extractor), planned merge with `producers[]` sidecar. **No implementation** — deferred until first content-plugin (zkm-receipt) lands in Phase 3 and N=2 evidence is concrete — covered by docs updates on 2026-05-08
- [x] Session 10 (core lib): `src/zkm/amendments.py` — read amendment records, key-resolve against md tree by `message_id`/`sha256`/path, merge per field rules, write back, track attribution sidecar. ~200 LOC + tests. Must land before session 14 — covered by tests/test_amendments.py (26 tests, 285 total) on 2026-05-08
- [x] Session 11: `zkm-photo` repo (`~/src/zkm-photo/`) — EXIF date→`date`; EXIF GPS→`location` decimal degrees (no reverse-geocode); camera model→`camera` scalar; sha256+CAS dedup; markdown image link in body. Uses only `zkm.atomic|cas|sidecar|inbox|hashing`. `creates_dirs: [photos, originals/photos]`. Idempotent (second run → 0 new files). 11 tests passing (incl. multi-producer sidecar cross-plugin test) — 2026-05-08. Note: `camera` goes to `camera:` scalar (not `tags:[]`) to preserve the amendment placeholder contract; `tags:[]` is left empty for future amenders.
- [x] Session 12: `zkm-pdf` (text-only) — emit md when text extraction ≥ N chars; silently skip scanned-only PDFs (leaves them for zkm-scan); test confirms skip. `PDF_MIN_TEXT_CHARS=100` default (flagged as provisional heuristic; to revisit at Session 13 design with `.zkm-state/zkm-pdf-skipped.jsonl` data). Two input paths: inbox/ PDFs (from zkm-eml, reuses existing CAS) + optional `PDF_SOURCE_DIR`. 12 tests passing — 2026-05-08
- [x] Session 13: `zkm-scan` (OCR, tesseract) — per-doc md; `progress` reporter; cancellable per plugin-spec cancellation contract. Processes images (JPEG, PNG, TIFF, BMP, GIF, WEBP) and scanned PDFs via pytesseract + pdf2image; SCAN_SOURCE_DIR + inbox fan-out; owned-by check for eml/photo/scan; per-doc md in scans/; sha256 dedup; SCAN_LANG + SCAN_MIN_TEXT_CHARS config knobs. 13 tests passing — 2026-05-08
- [x] Session 14: `zkm-notmuch` plugin (`plugins/zkm-notmuch/`) — first amender. Reads tags via `notmuch dump --format=batch-tag` (subprocess; no Python binding required). Normalises message IDs to `<id>` form to match zkm-eml `raw_message_id` frontmatter. Emits amendment records via `zkm.amendments` (set-union merge into `tags`). Applies queue immediately; pending records left for re-run after `zkm-eml`. `NOTMUCH_CONFIG` and `NOTMUCH_TAGS_EXCLUDE` config knobs. 16 tests passing — 2026-05-08
- [ ] Session 15 (scoping, not implementation): meeting on zkm-whatsapp core gaps — (a) non-git source state / `zkm.state` helper, (b) per-store YAML config replacing long env-var lists, (c) stable-ID synthesis contract; deliverable: `docs/meeting-notes/YYYY-MM-DD-whatsapp-scope.md`

## Phase 2 housekeeping — repo reorg (decided 2026-05-08-repo-reorg.md)

- [x] **Reorg**: `mv ~/src/zkm-{eml,pdf,photo,scan} ~/src/zkm/plugins/`; deleted dangling symlinks `plugins/zkm-zkm-{eml,photo}`; fievel: `mkdir ~/src/zkm-plugins && mv ~/src/zkm-{eml,photo}.git ~/src/zkm-plugins/` + `git init --bare` for pdf + scan; updated local remote URLs; pushed to verify. 285 tests passing — completed 2026-05-08
- [ ] **`add_plugin()` double-prefix** (`src/zkm/convert.py:119`): drop the `f"zkm-{name}"` prefix when the manifest name already starts with `zkm-`. Contract: `zkm plugin add ./examples/zkm-notes` produces `plugins/zkm-notes` (name `notes`); adding a plugin with name `zkm-eml` produces `plugins/zkm-eml`, not `plugins/zkm-zkm-eml`.
- [ ] **`add_plugin()` self-link guard** (`src/zkm/convert.py:119`): when the resolved source path is already inside `plugins_dir()`, return a friendly "already installed in place" message instead of creating a symlink. Contract: `zkm plugin add ./plugins/zkm-eml` prints "Plugin 'zkm-eml' is already in the plugins directory" and exits 0 without creating `plugins/zkm-zkm-eml → ./plugins/zkm-eml`.

## Phase 2 session 8 — doc chunking (core)

- [x] Session 8a: `embed.py` — char-window chunker replacing single truncation; `chunk_index` column in `EmbedStore`; store version bump (`_STORE_SCHEMA_VERSION=2`) with rebuild-on-mismatch; env knobs `ZKM_EMBED_CHUNK_CHARS` (default 2000), `ZKM_EMBED_CHUNK_OVERLAP` (default 200); `ZKM_EMBED_MAX_CHARS` deprecated — covered by tests/test_embed.py (31 tests) on 2026-05-08
- [x] Session 8b: `query.py` — `_dense_search` aggregates chunk rows to `max`-per-path before RRF; `_CHUNK_OVERSAMPLE=3` widens topk fetch to handle chunk multiplicity; CLI output unchanged — covered by tests/test_query_recall.py on 2026-05-08
- [x] Session 8c: tests — `test_embed.py` chunk count, overlap, env overrides, legacy deprecation, round-trip, schema rejection, cache reuse + invalidation; `test_query_recall.py` long-document recall (chunk 1 of a doc surfaces via dense), max-per-path aggregation correctness — 259 tests passing on 2026-05-08
- [x] Session 8d: docs — added step 6 to `docs/field-test-bge-m3.md` (long-document recall probe); updated `docs/hybrid-search.md` (removed "first 2000 chars" caveat, added chunk aggregation section + env knob table rows, schema version note) — 2026-05-08

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

- [x] `zkm rm <path>` — remove a managed `.md`; decrement sidecar `producers[]`; if last producer, remove the inbox symlink; if CAS object now unreferenced, remove it. Dry-run by default; `--apply` to commit (with `--no-commit` to skip). Single file only — covered by tests/test_hygiene.py on 2026-05-07
- [x] `zkm gc` — scan all sidecars; CAS objects with empty/missing producers are reported (dry-run) or removed (`--apply`, with `--no-commit` to skip) — covered by tests/test_hygiene.py on 2026-05-07

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

- [x] **zkm-eml: git-commit watermark** — state file `<store>/.zkm-state/zkm-eml.json` keyed by source repo path; `iter_messages_since` fast-enumerates via `git diff`; full-scan fallback when watermark absent/unreachable or source not a git repo — covered by tests (111 zkm-eml tests passing) on 2026-05-07
- [x] **zkm index: git-commit watermark** — watermark at `<store>/.zkm-index/last-commit`; `build_index` fast path via `git diff --name-status`; `--full` flag for forced rescan; `write_watermark` called from `cmd_index` after `save_index` — covered by tests (193 zkm tests passing) on 2026-05-07

## Phase 2 — mbsync auto-trigger (decided 2026-05-08-mbsync-hook.md)

- [x] A1: `src/zkm/devcheck.py` + `cli.py` integration; `tests/test_devcheck.py` — dirty-tree guard (core + invoked plugin), `ZKM_BYPASS_DIRTY_CHECK=1` opts out, non-editable install no-ops. 13 tests passing — 2026-05-08
- [x] A2: `docs/install.md` — documents `uv tool install --editable ~/src/zkm` for `zkm` on PATH; pointer added to `CLAUDE.md` Quick start. 2026-05-08
- [x] A3: `plugins/zkm-eml/hooks/post-commit` + `Makefile` (`install-hook`/`uninstall-hook`); README "Auto-trigger from mbsync" section. 2026-05-08
- [x] A3 fix: renamed `MAIL` → `MAIL_REPO` in Makefile — `$MAIL` is a standard Unix env var inherited by make, overriding `?=` default — verified by user on 2026-05-08
- [x] Python 3.14 pin: added `.python-version`, bumped `requires-python = ">=3.14"` — `uv tool install` was defaulting to 3.11 (requires-python floor) causing needless re-downloads — verified by user on 2026-05-08
- [x] Hook live: `make install-hook` → symlink in `~/mail/.git/hooks/`; empty mail commit triggered convert (27 msgs) + index; journald confirms — verified by user on 2026-05-08
- [x] Hook fix: `zkm index` → `zkm index --no-embed` — bare index was hitting GPU on every sync; embed belongs on separate timer (A5) — verified by user on 2026-05-08
- [ ] A5 (deferred): separate systemd timer for `zkm embed` + `zkm doctor`.
- [ ] from 2026-06-05: review journald evidence for convert-overlap; decide on lock if observed.

## Phase 2 — SIGUSR1 progress + `zkm status` (decided 2026-05-08-1913-sigusr1-status.md)

Scope: `convert` and `index` (BM25 + embed phases) only. `query`, `clone`, `push`, `pull` explicitly out. Daemon/supervisor model deferred (N<2 background callers). Host-wide multi-store registry, historical run log, `--kill`, `--watch`, live-tail all deferred.

- [x] **S1.** `src/zkm/runstate.py` (new): `RunSession` context manager — PID file lifecycle (`<store>/.zkm-state/running/<pid>.json`, atomic write via tmp+rename) + SIGUSR1 handler (forces immediate file write + dd-style stderr line). Fibonacci backoff via `_should_write(count)` helper. Schema: `{command, pid, started_at, args, phase, current, total, message, last_updated}`. 15 tests passing — 2026-05-08
- [x] **S2.** Wire `RunSession` into `cmd_convert` (`src/zkm/cli.py`). PID file appears at start, updated via `session.tick()` alongside tqdm (tqdm guards `if not show_progress`), unlinked on exit. progress callback always passed to run_convert/run_reprocess — 2026-05-08
- [x] **S3.** Wire `RunSession` into `cmd_index` (`src/zkm/cli.py`). Single session spans BM25 + embed phases; `phase` flips `"bm25"` → `"embed"` via `session.set_phase("embed")`. With `--no-embed`, stays in `"bm25"` phase only. progress callback always passed — 2026-05-08
- [x] **S4.** New `cmd_status` subcommand (`src/zkm/cli.py`). Lists `<store>/.zkm-state/running/*.json`, drops stale PIDs (stderr notice), sends SIGUSR1 to live ones, sleeps 50ms, re-reads, prints human table (`pid`, `cmd`, `phase`, `started`, `progress`, `message`). `--json` flag emits JSON array. Empty store prints "no running zkm processes" — 2026-05-08
- [x] **S5.** Updated `docs/plugin-spec.md` cancellation section: SIGUSR1 reserved by core; plugins must not install their own SIGUSR1 handler — 2026-05-08
- [x] **S6.** TODO.md updated with verification checklist (see below) — 2026-05-08
- [x] **S7+S8.** Updated `docs/meeting-notes/meeting-style.md` "Past meetings" index: added mbsync-hook + sigusr1-status entries — 2026-05-08

**Verification checklist** (313 tests passing, 2026-05-08):
1. `zkm convert zkm-eml` in terminal A → `zkm status` in terminal B shows one row with fresh `last_updated`.
2. `kill -USR1 <pid>` directly → dd-style line on convert's stderr.
3. `zkm index` → `phase` toggles `bm25` → `embed`; `zkm index --no-embed` stays at `bm25`.
4. SIGKILL the process → next `zkm status` drops stale file with stderr notice.
5. `zkm status --json | jq` → valid JSON array.

## Plugin backlog — conversation / AI session sources

- [ ] **`zkm-claude-code`** — import Claude Code session transcripts (`.claude/projects/*/transcripts/*.json` or similar). Key fields: session ID, timestamp, project path, messages. Stable ID: session ID + message index. Source state: git-commit watermark on transcript dir or mtime-based. Scope and trigger path need a scoping session before implementation.
- [ ] **`zkm-claude-ai`** — import claude.ai conversation exports (JSON or markdown). Same stable-ID and amendment concerns as zkm-claude-code; likely shares core parsing logic.
- [ ] **Other AI provider sessions** (ChatGPT exports, Gemini, etc.) — deferred until zkm-claude-code lands and the session-import pattern is proven. N=2 for a shared `zkm.session` helper module requires at least two providers implemented.

## Encoding / text quality (backlog)

- [ ] **Text file encoding issues** — emails and other plugin outputs can carry mis-decoded bodies (Latin-1 read as UTF-8, mojibake umlauts, BOM headers, mixed encodings within a single message). Audit `zkm-eml` decode paths and add a normalization pass (detect-and-transcode or at minimum chardet fallback). Add test fixtures with known-bad encodings. Surfaces downstream as broken stemming and tokenization for accented characters.
