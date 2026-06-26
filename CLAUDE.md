# zkm — ze knowledge manager

Personal knowledge management CLI. Converts heterogeneous sources into a git-tracked markdown tree, indexes with BM25 + dense hybrid search, queries with optional LLM augmentation.

**Tool repo** (`~/src/zkm/`). Knowledge store lives separately at `$ZKM_STORE` (default: `~/knowledge/`).

See `ARCHITECTURE.md` for design decisions with rationale and rejected alternatives.
See `ROADMAP.md` for the executor-facing task queue; `TODO.md` is the broader ledger.

## Commands

```bash
uv sync                      # dev environment (Python 3.11+, uv-managed)
uv run pytest                # full test suite (hermetic — no network, no real store)
uv run pytest -k <expr>      # one test / one roadmap item's done-check
uv run ruff check <changed files>  # lint (E, F, I, UP; line-length 100).
                             # NOTE: the repo has pre-existing ruff debt in old
                             # files — keep files YOU touch clean; do not mass-fix.
uv run zkm --help            # CLI entry point (zkm = zkm.cli:main)
```

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
├── entity-model.md     # NER, entity pages, WebUI design (Phase 3+)
└── ner.md              # NER pipeline, quality controls, cache, scope
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

See `docs/install.md` for global PATH install (required for the mbsync auto-trigger hook).
See `docs/restore.md` for disaster-recovery procedure (re-derive caches after full disk loss).
See `docs/concurrent-runs.md` for the concurrent-run guard (`ZKM_BYPASS_RUN_GUARD=1` bypass, exit-75 convention, mbsync-hook implication).

## Plugin system

Each converter is a separate repo. Two install paths:

- **Released wheel** (end-user): `uv tool install zkm --with zkm-<name>` (entry-point origin; deps resolved by uv into zkm's sealed env). Removing: re-run `uv tool install zkm --with <other-plugins>` omitting the one to drop. `zkm plugin remove` **refuses** on wheel-origin plugins to prevent destructive rmtree into site-packages.
- **Dev/local** (development): `zkm plugin add ./path` (symlink) or `zkm plugin add <git-url>` (clone) — filesystem origin. Removing: `zkm plugin remove <name>`.

```
plugins/zkm-imap/
├── plugin.yaml         # name, version, creates_dirs, config_schema
├── convert.py          # def convert(store_path, config) -> list[Path]
└── README.md
```

Plugins declare which subdirs they create (e.g., `mail/`) and what config they need. Non-secret config lives in `$ZKM_STORE/zkm-config.yaml` (committed); secrets in `$ZKM_STORE/.zkm-secrets.yaml` (gitignored, chmod 0600). **Plugin discovery: union of `importlib.metadata.entry_points(group="zkm.plugins")` + `plugins/*/plugin.yaml` filesystem scan; dedup by name; dev/filesystem wins over installed wheel (shadowing).** A single `plugin.yaml` may declare **multiple** plugins as a `---`-separated multi-document YAML stream (e.g. zkm-stt ships `stt` + `stt-wa`); `load_plugin_manifests()` returns one `Plugin` per doc and both discovery loops iterate all of them (`load_plugin_manifest()` returns the first/primary doc). For dev-symlink plugins whose `.venv` was built for a now-stale interpreter (e.g. system Python bump), `_inject_plugin_venv` auto-rebuilds it via `uv sync --frozen -p <running>` on first load; opt out with `ZKM_NO_PLUGIN_AUTOSYNC=1`.

**Local install** (during development): `zkm plugin add ./examples/zkm-notes` creates a symlink in `plugins/`. Git URL install uses `git clone`. The installed plugins directory can be overridden with `$ZKM_PLUGINS_DIR`.

**Dev plugin repos** (e.g., `zkm-eml`, `zkm-photo`) live directly under `plugins/<repo-name>/` as full independent git repos. They are gitignored from the parent repo. Discovery finds them via `plugin.yaml` with no symlink needed — don't run `zkm plugin add` against a path already inside `plugins/` (creates a redundant `zkm-<name> → ./plugins/<name>` self-link).

**New-plugin dispatch convention** (decided 2026-06-11, see `docs/meeting-notes/2026-06-11-0835-parallel-agent-workflow-new-plugin-repos.md`):
1. **Remote-first before dispatch-or-done.** A new plugin repo may start as a local-only `git init` skeleton, but MUST have its remote created and `git push -u origin main` landed *before* either (a) parallel agents are dispatched against it, or (b) any of its TODO items is marked `[x]`. Remote creation (bare repo on fievel via SSH, or GitHub repo creation) is a human-confirmed step in the main session — never inside a dispatched child agent.
2. **Skeleton-first baseline barrier.** The skeleton stage (e.g. SOC1 `git init` + initial commit) is a hard barrier before any parallel fan-out. `git worktree add` requires an existing baseline commit; fan-out only after the first commit exists.
3. **D6.4 worktree-per-item applies verbatim** thereafter: Workflow tool, each parser-agent in its own worktree+branch off the baseline, commits in-worktree, returns `{branch, diary_fragment, todo_item_id, done_summary, contract_met}`, main merges `--no-ff` and pushes. See `docs/meeting-notes/2026-06-04-1048-subagent-parallel-class1.md` for the full D6.4 contract.

**Plugin-done gate** (decided 2026-06-11): Before any plugin-scoped TODO item is marked `[x]`, the main session verifies the plugin's HEAD is pushed to its upstream:
```bash
git -C plugins/<name> rev-parse HEAD
git -C plugins/<name> rev-parse @{u}   # must resolve + must equal HEAD
```
Fails closed: no upstream configured, or HEAD ahead of upstream → item stays open. Uses `@{u}` (tracking upstream), so it is remote-name-agnostic (works for fievel `origin` and github remotes alike). Universal for ALL plugin-scoped item closes, established repos included.

See `docs/plugin-spec.md` for the full interface contract. See `examples/zkm-notes/` for a working reference implementation.

## Store layout (minimal skeleton)

`zkm init` creates only:

```
~/knowledge/
├── inbox/              # Drop zone — unsorted items land here
├── notes/              # Manual notes, diary, zettelkasten
├── originals/          # Binary originals (git-annex or git-lfs, user choice)
├── zkm-config.yaml     # non-secret store + plugin config (committed)
├── .zkm-secrets.yaml   # API tokens, credentials (chmod 0600, gitignored)
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

## Versioning

Follows the global bump-and-tag + loose-0.x rule (see `~/.claude/CLAUDE.md`).

Repos in this polyrepo (each tags `vX.Y.Z` independently):
- `~/src/zkm/` — core
- `plugins/zkm-eml/` — own git repo
- `plugins/zkm-photo/`, `zkm-pdf/`, `zkm-scan/`, `zkm-notmuch/`, `zkm-ner/` — own repos
- `plugins/zkm-vcard/`, `plugins/zkm-calendar/` — own repos (decided 2026-06-01)
- `plugins/zkm-claude-ai/` — own repo (decided 2026-06-06)
- `examples/zkm-notes/` — not independently versioned; follows core tags

**Bump trigger:** every pyproject `version` change → tag in same commit. Never bump silently. After each bump-and-tag commit, run `uv publish` in the affected repo to release the wheel. Plugin PyPI releases are gated on Session B (entry-point discovery — plugin stubs are at 0.0.1 until then).

## TODO prefix convention

Central `TODO.md` is the single ledger for all plugin-scoped and cross-cutting work (decided 2026-05-13, see `docs/meeting-notes/2026-05-13-1915-per-plugin-todo-topology.md`). Plugin-scoped items use a single-letter prefix:

| Prefix | Plugin / scope |
|--------|---------------|
| `N` | zkm-ner (NER pipeline) |
| `A` | zkm-eml auto-trigger (mbsync hook) |
| `E` | γ schema (cross-cutting core + zkm-ner) |
| `S` | SIGUSR1/status (core runstate) |
| `M` | zkm-eml backlog (general) |
| `V` | zkm-vcard (contacts plugin) |
| `C` | zkm-calendar (calendar plugin) |
| `W` | zkm-whatsapp (chat plugin) |
| — | core / cross-cutting (no prefix) |

**Rule:** when a plugin accumulates ≥3 unchecked items at once that aren't already in a numbered series, assign a single-letter prefix and add it to this table.

**GH Issues = additional inbox channel (not a migration):** public GitHub Issues on a
plugin repo are an *extra input*, not a replacement ledger. The canonical source of truth
stays the central `TODO.md` (+ per-repo `ROADMAP.md` for executor specs). When a repo has
Issues enabled:
- Relay/meeting passes additionally run `gh issue list` across those repos.
- Each open issue is triaged — answer/close it, or route it into `TODO.md` (W-prefix etc.)
  with a link back to the issue. The issue is a pointer; the ledger is the truth.
- **No automatic topology flip.** A real migration to "GH Issues for larger items + central
  TODO.md for tactical" is reconsidered only if *sustained* outside contribution actually
  materializes (e.g. several merged outside PRs) — a deliberate decision then, never an
  automatic trigger on the first stranger's issue. (Superseded the old auto-migration
  trigger 2026-06-26: it hinged a whole-topology flip across all plugins on a single weak
  signal.)

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
- Entity extraction (NER amender plugin, Phase 2.5) — see `docs/ner.md`
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

## Gotchas (hard-won; do not rediscover)

- **`plugins/` is normally EMPTY in a fresh clone/worktree** — the ~9 plugin
  repos are independent git repos that live there only on the dev machine. The
  core test suite (529+ tests) MUST pass with no plugins present; never write a
  core test that imports or shells out to a plugin repo.
- **Dirty-tree guard** (`zkm.devcheck.assert_clean`): state-modifying commands
  refuse to run when the zkm source repo (or the invoked plugin's repo) has
  uncommitted tracked changes. Tests bypass it via an autouse conftest fixture
  setting `ZKM_BYPASS_DIRTY_CHECK=1`; manual dev runs need the same env var.
- **Concurrent-run guard** exits with code **75** (`EX_TEMPFAIL`) when a
  conflicting `convert`/`scrub`/`index` is already running (PID files under
  `<store>/.zkm-state/running/`). Bypass: `ZKM_BYPASS_RUN_GUARD=1`. See
  `docs/concurrent-runs.md`. Exit 75 is the repo-wide "temporary, retry later"
  convention — reuse it for new refuse-to-start guards.
- **Amender scoping** (id:63bb, 2026-06-11): `zkm convert <plugin>` passes
  `created: list[Path]` to amenders whose `convert()` declares the param
  (capability-probed via `inspect.signature`, same pattern as `progress`).
  Explicit `zkm convert ner` (created=None) still full-sweeps. Don't break the
  capability probe — plugins without the param must keep working.
- **Amendment merge modes** (`zkm.amendments`, schema 2): two emit paths.
  `emit()` is **additive** (set-union, never removes). `emit_set()` is
  **declarative** — its `fields` are a producer's full current asserted set for
  a key; core diffs prior-vs-new (per-producer `producer_sets` in the
  `<md>.amendments.json` sidecar) and drops a value only when it ref-counts to
  zero across ALL producers (a value any producer still asserts is kept). An
  empty set retracts only that producer's own claims (never bulk-retract); the
  diff is scoped to keys reported this run; legacy schema-1 sidecars bootstrap
  gracefully (no migration). The sidecar read-modify-write is fcntl-locked.
  Retraction preview: `apply_queue(store, dry_run=True)` / `plan_retractions(store)`.
  Only `tags` is a set field; scalars stay last-write-wins. Design:
  `docs/meeting-notes/2026-06-18-1944-f103-tag-removal-core-semantic.md` (id:25ec).
  Stage 2 (zkm-notmuch declarative emit = f103) is a SEPARATE repo/session.
- **Heavy imports are deferred** inside CLI functions (`tqdm`, `httpx`, plugin
  modules) to keep `zkm --help` fast. Follow that pattern in new commands.
- **`git add` is scoped** to the plugin's `creates_dirs` + created files during
  auto-commit — never widen to `-A` for plugin converts (Syncthing deposits
  source files into `inbox/` sub-dirs that must not be staged).
- **Tests are hermetic**: `tmp_path` stores via the `store` fixture
  (`init_store(backend="none")`), no network, no `~/knowledge`. Fixture corpus
  in `tests/fixtures/corpus/` (committed; regen procedure in its README).
- **OS / tooling**: Manjaro — `pamac`, never `pacman -S`. Python via `uv` only
  (`uv sync`, `uv run`); never bare pip into system Python.

## Related

- **DiffMem** — git-as-temporal-index inspiration
- **memsearch** — potential Phase 2 embedding backend (markdown-first, Milvus Lite)
- **Zelegator** — intent router, Phase 3 integration target

## Relay contract <!-- relay-executor contract v4 -->

This repo is managed by a reviewer/executor relay. Load `/relay executor` before
working on any item, then follow its rules exactly.
