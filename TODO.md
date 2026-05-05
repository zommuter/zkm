# zkm — Phase 1 TODO

See `CLAUDE.md` for architecture overview. See `docs/phase1-design.md` for library choices and open questions.

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
- [ ] Walk store for `*.md` (skip `plugins/`, `.zkm-index/`, `originals/`)
- [ ] Parse frontmatter with `python-frontmatter`
- [ ] Build `rank_bm25` index → `$ZKM_STORE/.zkm-index/bm25.pkl`
- [ ] Incremental: skip files unchanged since last index (compare mtime or git hash)

## `zkm search "query"` (`index.py`, `query.py`)
- [ ] Load BM25 index, return top-k hits
- [ ] Render: file path + frontmatter `date` + text snippet
- [ ] `--json` flag for programmatic use
- [ ] `-k / --top-k` (default 10)

## `zkm query "question"` (`query.py`)
- [ ] Call `search()` → top-k context documents
- [ ] Assemble prompt with document snippets
- [ ] POST to `ZKM_LLM_ENDPOINT` (`/v1/chat/completions`) via `httpx`
- [ ] Stream response to stdout
- [ ] Config env vars: `ZKM_LLM_ENDPOINT`, `ZKM_LLM_MODEL`, `ZKM_LLM_KEY`

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
- [ ] `zkm-eml` `originals.py` — implement sidecar write/merge in `symlink_inbox`; switch dedup from one-symlink-per-message-date to one-canonical-symlink-per-CAS + sidecar listing all producers
- [ ] `zkm-eml` `tests/test_attachments.py` — multi-message-same-attachment round-trip: assert single canonical symlink, sidecar schema, producer list

## Ops / polish
- [x] `ruff check` clean
- [x] `pytest` passing (22/22)
- [ ] `README.md` — quickstart (install, init, first plugin, search)
- [ ] CI (GitHub Actions) — ruff + pytest on push
