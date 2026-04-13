# zkm — Phase 1 TODO

See `CLAUDE.md` for architecture overview. See `docs/phase1-design.md` for library choices and open questions.

## Scaffold
- [x] `pyproject.toml` — uv + hatchling, Click + rank-bm25 + python-frontmatter + httpx, entry point `zkm`
- [x] `src/zkm/` — package skeleton (`cli.py`, `store.py`, `convert.py`, `index.py`, `query.py`)
- [x] `zkm init` (`store.py`) — replaces `zkm-init.sh`; binary backend auto-detect; idempotent
- [x] `tests/test_init.py` — smoke tests for `init_store()`
- [x] `docs/phase1-design.md` — design decisions and open questions

## `zkm plugin` (`convert.py`)
- [ ] `zkm plugin add <git-url>` — `git clone` into `plugins/`, validate `plugin.yaml`
- [ ] `zkm plugin list` — read `plugins/*/plugin.yaml`, print name / version / path
- [ ] `zkm plugin remove <name>` — `rm -rf plugins/<dir>`
- [ ] `.env` key prompting for missing required config on `plugin add`

## First plugin: `zkm-imap` (separate repo)
- [ ] Repo skeleton (`plugin.yaml` + `convert.py`) per `docs/plugin-spec.md`
- [ ] `convert.py` using stdlib `imaplib`
- [ ] Cursor-based incremental fetch (`UIDVALIDITY` + last UID in `.cursor`)
- [ ] Idempotency via `sha256` dedup (skip existing files by hash)

## `zkm convert <plugin>` (`convert.py`)
- [ ] Load `plugin.yaml`, resolve `convert()` entry point
- [ ] Load `$ZKM_STORE/.env`, filter to plugin's declared config keys
- [ ] Invoke `convert(store_path, config)`, capture returned paths
- [ ] Auto-commit to the store: `chore(<plugin>): ingest N files`
- [ ] `--no-commit` flag to skip auto-commit

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

## Ops / polish
- [ ] `ruff check` clean (currently: only stub unused-arg warnings, acceptable)
- [ ] `pytest` passing
- [ ] `README.md` — quickstart (install, init, first plugin, search)
- [ ] CI (GitHub Actions) — ruff + pytest on push
