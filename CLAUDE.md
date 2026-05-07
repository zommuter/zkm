# zkm — ze knowledge manager

Personal knowledge management CLI. Converts heterogeneous sources into a git-tracked markdown tree, indexes with BM25, queries with optional LLM augmentation.

**Tool repo** (`~/src/zkm/`). Knowledge store lives separately at `$ZKM_STORE` (default: `~/knowledge/`).

## Architecture

```
Plugins (source → md)  →  Store (md + git)  →  Index (BM25)  →  Query (CLI / web)
```

- No vector DB in Phase 1. BM25 over markdown. Embeddings are Phase 2.
- Git history = temporal index. HEAD = current state, log/diff = evolution. See `docs/temporal-queries.md`.
- LLM enters only at query time, via any OpenAI-compatible API (configurable endpoint).

## Layout

```
src/zkm/
├── cli.py              # Click CLI entry point
├── convert.py          # Plugin registry + converter dispatch
├── index.py            # BM25 indexer
├── query.py            # Search + LLM context assembly
└── store.py            # Store init, git helpers
examples/
└── zkm-notes/          # Bundled sample plugin (plain-text importer)
plugins/                # User-installed plugins (gitignored, cloned/symlinked)
docs/
├── phase1-design.md    # Library choices and open questions for Phase 1
├── temporal-queries.md # Git-as-temporal-index pattern (DiffMem-inspired)
├── plugin-spec.md      # How to write a converter plugin
└── entity-model.md     # NER, entity pages, WebUI design (Phase 3+)
tests/
pyproject.toml          # uv + hatchling, entry point: zkm = "zkm.cli:main"
TODO.md                 # Phase 1 progress checklist
```

### Quick start (development)

```bash
cd ~/src/zkm
uv sync
uv run zkm --help
ZKM_STORE=/tmp/my-kb uv run zkm init
```

## Plugin system

Each converter is a separate repo, installed via `zkm plugin add <git-url>`.

```
plugins/zkm-imap/
├── plugin.yaml         # name, version, creates_dirs, config_schema
├── convert.py          # def convert(store_path, config) -> list[Path]
└── README.md
```

Plugins declare which subdirs they create (e.g., `mail/`) and what config they need. Secrets go in `$ZKM_STORE/.env` (gitignored). Plugin discovery: scan `plugins/*/plugin.yaml`.

**Local install** (during development): `zkm plugin add ./examples/zkm-notes` creates a symlink in `plugins/`. Git URL install uses `git clone`. The installed plugins directory can be overridden with `$ZKM_PLUGINS_DIR`.

See `docs/plugin-spec.md` for the full interface contract. See `examples/zkm-notes/` for a working reference implementation.

## Store layout (minimal skeleton)

`zkm init` creates only:

```
~/knowledge/
├── inbox/              # Drop zone — unsorted items land here
├── notes/              # Manual notes, diary, zettelkasten
├── originals/          # Binary originals (git-annex or git-lfs, user choice)
├── .env                # API tokens, IMAP credentials (gitignored)
├── .zkm-config         # binary_backend=annex|lfs|none
├── .gitignore
└── .gitattributes
```

Plugins create additional dirs on first run (e.g., `mail/`, `messages/whatsapp/`).

## Frontmatter

```yaml
---
source: imap
date: 2026-04-13T14:30:00+02:00
tags: [bill, electricity]
original: originals/scans/2026-04-13_stadtwerke.pdf
sha256: abc123...
---
```

- `source` must match an installed plugin name
- `tags` is the only categorization field. Phase 2 adds `entities` via NER (typed: person, org, place)
- `sha256` of the original file, for dedup
- ISO 8601 dates everywhere. Human-readable filenames, no hashes in filenames.
- DB-derived metadata (auto-tags, NER) **must be written back** to frontmatter. The md is always source of truth.

## Conventions

- Python 3.11+, `uv` for env, ruff for lint, pytest for tests
- Conventional commits
- Minimize dependencies: stdlib > small lib > framework. No LangChain.
- Locale-aware formatting where needed (de_CH default)

## Phases

### Phase 1: MVP
See `TODO.md` for the detailed, checked-off task list.
- [x] `zkm init` — scaffold store + git init (replaced `zkm-init.sh`)
- [x] `zkm plugin add/list/remove` — plugin registry (local symlink + git clone)
- [x] Sample plugin: `examples/zkm-notes/` — plain text/md importer
- [x] `zkm convert <plugin>` — dispatches to plugin's `convert()`, auto-commits
- [x] First production plugin: `zkm-eml` (mbsync .mbox → markdown, separate repo `~/src/zkm-eml/`)
- [x] `zkm index` — BM25 index over all .md files
- [x] `zkm search "query"` — top-k with snippets
- [x] `zkm query "question"` — search + LLM context (OpenAI-compatible endpoint)
- Deferred: `zkm-imap` (live IMAP fetch) — mbsync + zkm-eml preferred for now

### Phase 2: Richer search + sources + store management
See `docs/phase2-plan.md` for full scope and sequencing.
- **Object-storage library** in core: `zkm.atomic`, `zkm.hashing`, `zkm.cas`, `zkm.sidecar`, `zkm.inbox` — single implementation of the spec contract; plugins import rather than reinvent. See `docs/object-storage.md`.
- **Store hygiene commands**: `zkm rm` (decrement producers, remove orphaned symlink + CAS object), `zkm gc` (sweep unreferenced CAS objects)
- [x] **Hybrid BM25 + dense embeddings** — `embed.py`, `docs/hybrid-search.md`; OpenAI-compatible `/v1/embeddings`, numpy EmbedStore, RRF fusion, `--no-dense` flag, graceful fallback — 2026-05-06
- **Store management** (`zkm remote`, `zkm clone`, `zkm push`, `zkm pull`) — git-like commands that dispatch correctly for annex/lfs/none backends. Reads `.zkm-config` to know which backend to use. See TODO.md for full spec.
- Entity extraction (NER → frontmatter `entities`, written back to md) — Phase 3
- More plugins: whatsapp, threema, signal, scan/OCR, photo-sidecar

### Phase 3: Integration + WebUI
See `docs/entity-model.md`.
- FastAPI server with live entity pages (clickable names → aggregated summaries via search)
- Zelegator tool dispatch integration
- Source polling via systemd timers / cron

### Phase 4: Temporal + advanced
See `docs/temporal-queries.md`.
- Temporal queries via git history
- Memory compaction (LLM-summarized entity files)
- Cross-reference graph (backlinks)

## Related

- **DiffMem** — git-as-temporal-index inspiration
- **memsearch** — potential Phase 2 embedding backend (markdown-first, Milvus Lite)
- **Zelegator** — intent router, Phase 3 integration target
