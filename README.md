# zkm — ze knowledge manager

> "I'm overwhelmed by the flood of AI generated knowledge managers, so let's create yet another one."

Obviously heavy WIP, don't expect miracles.

## What the "ze"?

Could be any of:

- a bad pun on German/French accented "the"
- an abbreviated "Zettel(kasten)"
- Zommuter's knowledge manager
- "Zero knowledge manager" — irony in case it doesn't work

Also feel free to pronounce `zkm` simply "ze-kem".

---

## Quickstart

### 1. Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <this-repo> ~/src/zkm
cd ~/src/zkm
uv sync
uv run zkm --version
```

For a system-wide install:

```bash
uv tool install .
zkm --version
```

### 2. Initialise the knowledge store

```bash
export ZKM_STORE=~/knowledge      # default if unset
zkm init
```

`zkm init` creates `~/knowledge/` with `inbox/`, `notes/`, `originals/`, a
git repo, `zkm-config.yaml` for committed config, and a gitignored
`.zkm-secrets.yaml` for credentials.

### 3. Install a plugin

Plugins convert sources into markdown. Install the bundled example or any
git-hosted plugin:

```bash
# bundled plain-text/markdown importer (development)
zkm plugin add ./examples/zkm-notes

# or a git-hosted plugin
zkm plugin add https://github.com/yourname/zkm-myplugin
```

List installed plugins:

```bash
zkm plugin list
```

### 4. Convert (ingest)

```bash
# plain notes importer: set the source directory in zkm-config.yaml
cat >> $ZKM_STORE/zkm-config.yaml <<EOF
notes:
  source_dir: $HOME/Documents/notes
EOF

zkm convert notes
```

The command walks the source, writes frontmatter-tagged markdown into the
store, and auto-commits. Re-running is safe — files are deduped by sha256.

Use `--reprocess` to re-derive files whose `processor_version` differs from
the current plugin version, or `--reprocess-all` to re-derive everything.

### 5. Index

Build (or refresh) the BM25 search index:

```bash
zkm index
```

The index lives in `$ZKM_STORE/.zkm-index/bm25.pkl` (gitignored). Re-running
is incremental — only files whose mtime changed are re-tokenised.

### 6. Search

```bash
zkm search "electricity bill"
zkm search "apple" --top-k 5
zkm search "recipe" --json
```

Output: ranked hits with score, date, and a text snippet.

### 7. Query (LLM-augmented)

Point zkm at any OpenAI-compatible endpoint via `$ZKM_STORE/zkm-config.yaml`
(non-secret) and `$ZKM_STORE/.zkm-secrets.yaml` (gitignored, chmod 0600):

```yaml
# zkm-config.yaml
core:
  llm:
    endpoint: http://localhost:11434   # Ollama
    model: llama3
```

```yaml
# .zkm-secrets.yaml
core:
  llm:
    key: sk-...
```

Then:

```bash
zkm query "what bills are due this month?"
```

Migrating from an existing `.env`? Run `zkm config migrate --apply` once.

The answer streams to stdout with a sources list at the end.

---

## Architecture

```
Plugins (source → md)  →  Store (md + git)  →  Index (BM25)  →  Query (CLI)
```

- **No vector DB in Phase 1.** BM25 over markdown. Embeddings are Phase 2.
- **Git history = temporal index.** HEAD = current state; log/diff = evolution.
- **LLM at query time only**, via any OpenAI-compatible API.

See `docs/` for design notes, plugin spec, and future-phase plans.

## Plugins

| Plugin | Description |
|--------|-------------|
| [zkm-eml](https://github.com/zommuter/zkm-eml) | Convert Maildir / `.eml` files to markdown with thread modeling and attachment extraction |
| [zkm-ner](https://github.com/zommuter/zkm-ner) | Amender: extract named entities (persons, orgs, locations, contacts) into frontmatter |
| [zkm-notmuch](https://github.com/zommuter/zkm-notmuch) | Amender: merge notmuch Xapian tags into mail-message frontmatter |
| [zkm-pdf](https://github.com/zommuter/zkm-pdf) | Import text-extractable PDFs into the knowledge store |
| [zkm-photo](https://github.com/zommuter/zkm-photo) | Import JPEG photos with EXIF metadata into the knowledge store |
| [zkm-scan](https://github.com/zommuter/zkm-scan) | OCR scanned images and PDFs (tesseract) into the knowledge store |

To install a plugin, clone it into `plugins/` inside your zkm checkout (it is auto-discovered):

```bash
git clone https://github.com/zommuter/zkm-eml.git plugins/zkm-eml
```

> **Note:** PyPI names are reserved (`pip install zkm-eml` etc.) but currently ship
> 0.0.1 placeholder stubs only — functional plugin code requires the git-clone path
> above. Entry-point–based plugin discovery (pip-installable plugins) is planned for
> zkm 1.0.

## Plugin development

See [`docs/plugin-spec.md`](docs/plugin-spec.md) and the reference
implementation in [`examples/zkm-notes/`](examples/zkm-notes/).

A plugin is a directory (or git repo) containing:

```
plugin.yaml    # name, version, config_schema, creates_dirs
convert.py     # def convert(store_path, config, *, progress=None) -> list[Path]
```

Install locally during development:

```bash
zkm plugin add ./my-plugin     # creates a symlink in plugins/
```

## Store layout

```
~/knowledge/
├── inbox/          # drop zone — unsorted items
├── notes/          # manual notes, diary, zettelkasten
├── originals/         # binary originals (git-annex / git-lfs / plain)
├── zkm-config.yaml    # non-secret config (committed)
├── .zkm-secrets.yaml  # credentials (chmod 0600, gitignored)
└── .zkm-index/        # BM25 index (gitignored)
```

Plugins create additional directories on first run (e.g. `mail/`, `messages/`).

## Phases

| Phase | Status | Features |
|-------|--------|----------|
| 1 — MVP | **done** | init, plugins, convert, index, search, query |
| 2 — Richer search | planned | embeddings, NER, store management commands |
| 3 — Integration | planned | FastAPI WebUI, entity pages, Zelegator integration |
| 4 — Temporal | planned | git-history queries, memory compaction |

## License

MIT — see [LICENSE](LICENSE)
