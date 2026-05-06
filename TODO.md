# zkm — Phase 1 TODO

See `CLAUDE.md` for architecture overview. See `docs/phase1-design.md` for library choices and open questions.

## Query quality

- [x] **Bilingual stemming** (`index.py`) — Unicode-aware tokenizer + en+de Snowball stemming; "meetings"↔"meeting", "Rechnungen"↔"Rechnung" now match — 80/80 tests passing 2026-05-06
- [x] **LLM query expansion** (`expand.py`, `query.py`) — `expand_query()` generates 3-5 keyword variants + hypothetical answer paragraph (RAG-Fusion + Query2Doc lite); multi-BM25 runs merged via RRF; cached in `.zkm-index/expansion-cache.json`; graceful fallback — 80/80 tests passing 2026-05-06
- [x] **`--no-expand` flag** on `zkm query`; fix double-search bug in `cmd_query` — 2026-05-06
- [x] **German temporal phrases** (`query.py`) — _temporal_filter now covers accusative/dative/genitive variants: "letzten Monat", "letzte Woche", "vergangenen Monat", "kürzlich", "neulich", etc. — 9 new tests, 89/89 passing 2026-05-06
- [x] **Current date in LLM system prompt** (`query.py`) — prepend "Today's date: YYYY-MM-DD." so model has temporal anchor; regression test added — 89/89 passing 2026-05-06
- [x] **Hybrid BM25 + dense retrieval** (`embed.py`, `query.py`, `index.py`) — OpenAI-compatible `/v1/embeddings` (no torch), `EmbedStore` (numpy, incremental), `search_hybrid`, `search_with_expansion` fuses BM25-RRF + dense via RRF; `--no-dense` flag; graceful fallback — 116/116 tests passing 2026-05-06
- [ ] **Field-test on real store** with bge-m3 via llama-swap; collect concrete retrieval failures before deciding next step
- [ ] Separate expansion model from answer model — `ZKM_LLM_EXPAND_MODEL` / `ZKM_LLM_EXPAND_ENDPOINT` so a fast small model (0.8B) handles keyword extraction while a large model (35B) handles the answer
- [ ] Surface expansion terms to the user (`zkm query --show-expansion`) for transparency and debugging
- [ ] Doc chunking for long emails/threads (current: first 2000 chars per doc, single embedding)

## Scaffold
- [x] `pyproject.toml` — uv + hatchling, Click + rank-bm25 + python-frontmatter + httpx, entry point `zkm`
- [x] `src/zkm/` — package skeleton (`cli.py`, `store.py`, `convert.py`, `index.py`, `query.py`)
- [x] `zkm init` (`store.py`) — replaces `zkm-init.sh`; binary backend auto-detect; idempotent
- [x] `tests/test_init.py` — smoke tests for `init_store()`
- [x] `docs/phase1-design.md` — design decisions and open questions

## `zkm plugin` (`convert.py`)
- [x] `zkm plugin add <path-or-url>` — local symlink or `git clone`; validates `plugin.yaml`
- [x] `zkm plugin list` — reads `plugins/*/plugin.yaml`, prints name / version / path
- [x] `zkm plugin remove <name>` — unlinks symlink or `rm -rf`
- [ ] `.env` key prompting for missing required config on `plugin add`

## Sample plugin: `zkm-notes` (`examples/zkm-notes/`)
- [x] `plugin.yaml` — declares `notes` subdir, `NOTES_SOURCE_DIR` config
- [x] `convert.py` — sha256 dedup, frontmatter preservation, mtime-based dates
- [x] `README.md` — usage + plugin-author design notes
- [x] End-to-end tests in `tests/test_plugin.py`

## Plugin spec + conventions
- [x] `docs/messaging-spec.md` — cross-plugin frontmatter + store layout for conversation sources — 2026-05-05
- [x] `docs/plugin-spec.md` — drift fixes (dotenv claim, original_path → original, processor_version) — 2026-05-05
- [x] `zkm-notes` — emits `processor`, `processor_version`, `original` fields — covered by test_notes_convert_writes_processor_fields on 2026-05-05
- [x] `zkm convert --reprocess` / `--reprocess-all` — re-derive already-ingested files — covered by test_reprocess_* on 2026-05-05
- [x] `docs/messaging-spec.md` — role-tagged participants schema ({address, name?, role}), canonical role vocabulary, direction derivation pattern, thread-index flat-dedup note — 2026-05-05

## First production plugin: `zkm-eml` (separate repo, `~/src/zkm-eml/`)
- [x] Repo init + `CLAUDE.md` + `plugin.yaml` — 2026-05-05
- [x] `parse.py` — stdlib `email` → structured message dict — 18 tests passing 2026-05-05
- [x] `threading.py` — References chain → thread_id — 18 tests passing 2026-05-05
- [x] `render.py` — body selection (plaintext preferred, HTML → markdownify fallback) — 2026-05-05
- [x] `frontmatter.py` — write per messaging-spec.md — 2026-05-05
- [x] `thread_index.py` — regenerate `mail/threads/<id>.md` for touched threads — 2026-05-05
- [x] End-to-end `convert.py` + `tests/` — 18/18 passing, ruff clean 2026-05-05
- [x] `README.md` — mbsync setup + `zkm plugin add` walkthrough — 2026-05-05

## Deferred: `zkm-imap` (live IMAP fetch)
- mbsync is preferred for now; zkm-imap is a thin future wrapper if needed

## `zkm convert <plugin>` (`convert.py`)
- [x] Load `plugin.yaml`, resolve `convert()` entry point via `importlib`
- [x] Load `$ZKM_STORE/.env`, apply defaults, filter to plugin's declared keys
- [x] Invoke `convert(store_path, config)`, capture returned paths
- [x] Auto-commit to the store: `chore(<plugin>): ingest N files`
- [x] `--no-commit` flag to skip auto-commit

## `zkm index` (`index.py`)
- [x] Walk store for `*.md` (skip `plugins/`, `.zkm-index/`, `originals/`) — 2026-05-05
- [x] Parse frontmatter with `python-frontmatter` — 2026-05-05
- [x] Build `rank_bm25` index → `$ZKM_STORE/.zkm-index/bm25.pkl` — 2026-05-05
- [x] Incremental: skip files unchanged since last index (mtime_ns cache) — 2026-05-05

## `zkm search "query"` (`index.py`, `query.py`)
- [x] Load BM25 index, return top-k hits — 2026-05-05
- [x] Render: file path + frontmatter `date` + text snippet — 2026-05-05
- [x] `--json` flag for programmatic use — 2026-05-05
- [x] `-k / --top-k` (default 10) — 2026-05-05

## `zkm query "question"` (`query.py`)
- [x] Call `search()` → top-k context documents — 2026-05-05
- [x] Assemble prompt with document snippets — 2026-05-05
- [x] POST to `ZKM_LLM_ENDPOINT` (`/v1/chat/completions`) via `httpx` — 2026-05-05
- [x] Stream response to stdout — 2026-05-05
- [x] Config env vars: `ZKM_LLM_ENDPOINT`, `ZKM_LLM_MODEL`, `ZKM_LLM_KEY` — 2026-05-05

## `zkm store` — git-like store management (Phase 2)

The store is a git repo; zkm should expose a thin wrapper that handles
git-annex / git-lfs automatically so the user doesn't have to think about it.

- [ ] `zkm remote add <name> <url>` — `git remote add` on the store
- [ ] `zkm remote list` — list store remotes
- [ ] `zkm clone <url> [path]` — clone a store; auto-detect annex/lfs from `.zkm-config` and re-initialise
- [ ] `zkm push [remote]` — push store commits; if annex: `git annex sync --content <remote>`; if lfs: `git lfs push --all <remote>`; else plain `git push`
- [ ] `zkm pull [remote]` — pull/rebase store commits; if annex: `git annex sync <remote>`; if lfs: `git lfs pull`; else plain `git pull --rebase`
- [ ] `--content` flag for `zkm push/pull` with annex: sync actual file content to/from remote (default: metadata only)

Design note: these commands read `.zkm-config` to know the backend and dispatch accordingly. The user never has to type `git annex` directly.

## Plugin cancellation
- [x] `cancel.py` — `CancelController` context manager, `PluginInterrupt`, 30s soft window, ESC watcher — 2026-05-05
- [x] CLI `cmd_convert` — wrapped in CancelController; countdown in tqdm; commits partial work; exit 130 — 2026-05-05
- [x] `plugin-spec.md` — cancellation contract documented (PluginInterrupt, try/finally, atomic writes) — 2026-05-05
- [x] `zkm-eml` convert+reprocess loops wrapped in try/finally for thread index cleanup on cancel — 2026-05-05
- [x] Soft-cancel test: PluginInterrupt leaves partial files on disk, run resumable — 2026-05-05

## Plugin progress indication
- [x] `progress=` kwarg contract in `run_convert` / `run_reprocess` with `inspect.signature` dispatch — 2026-05-05
- [x] tqdm bar on TTY in `cli.py`, `--no-progress` flag — 2026-05-05
- [x] `zkm-notes` and `zkm-eml` updated to accept and call progress — 2026-05-05
- [x] `docs/plugin-spec.md` documents mandatory progress contract — 2026-05-05
- [x] `pytest` passing (22/22) — 2026-05-05

## inbox/ backlinks
- [x] `docs/plugin-spec.md` — "Inbox handoff and origin sidecar" section: schema v1, one-canonical-symlink dedup policy, incremental vs reprocess-all update strategies — 2026-05-05
- [x] `zkm-eml` `originals.py` — implement sidecar write/merge in `symlink_inbox`; one-canonical-symlink-per-CAS + sidecar listing all producers — covered by tests (57/57 passing) on 2026-05-05
- [x] `zkm-eml` `tests/test_attachments.py` — multi-message-same-attachment round-trip: single canonical symlink, sidecar schema, producer list — covered by test_inbox_sidecar_multi_producer on 2026-05-05

## Encoding / text quality (backlog)

- [ ] **Text file encoding issues** — emails and other plugin outputs can carry mis-decoded
  bodies (Latin-1 read as UTF-8, mojibake umlauts, BOM headers, mixed encodings within a single
  message). Audit `zkm-eml` decode paths and add a normalization pass (detect-and-transcode or
  at minimum chardet fallback). Add test fixtures with known-bad encodings. Surfaces downstream
  as broken stemming and tokenization for accented characters.

## Ops / polish
- [x] `ruff check` clean
- [x] `pytest` passing (80/80) — 2026-05-06
- [x] `README.md` — quickstart (install, init, first plugin, search) — 2026-05-05
- [x] CI (GitHub Actions) — ruff + pytest on push — 2026-05-05
