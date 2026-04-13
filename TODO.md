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

## First production plugin: `zkm-imap` (separate repo, after zkm-notes)
- [ ] Repo skeleton (`plugin.yaml` + `convert.py`) per `docs/plugin-spec.md`
- [ ] `convert.py` using stdlib `imaplib`
- [ ] Cursor-based incremental fetch (`UIDVALIDITY` + last UID in `.cursor`)
- [ ] Idempotency via `sha256` dedup

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

## Ops / polish
- [x] `ruff check` clean
- [x] `pytest` passing (17/17)
- [ ] `README.md` — quickstart (install, init, first plugin, search)
- [ ] CI (GitHub Actions) — ruff + pytest on push
