# Phase 1 design decisions

Design decisions and open questions captured during the Phase 1 planning session (2026-04-13).

## Library choices

| Concern | Chosen | Rejected alternatives |
|---|---|---|
| CLI framework | `click>=8.1` | Typer (adds Pydantic), argparse (verbose for subcommand trees) |
| Git invocation | `subprocess.run(["git", ...])` | GitPython (heavy for 5 commands), pygit2 (overkill) |
| BM25 | `rank-bm25` (pure-Python, ~200 LOC) | Whoosh (unmaintained), tantivy-py (Rust binary), Elasticsearch |
| Frontmatter | `python-frontmatter` | pyyaml + manual split (viable fallback if dep count matters) |
| LLM HTTP client | `httpx` + hand-rolled POST to `/v1/chat/completions` | `openai` SDK (pulls pydantic/anyio/httpx anyway, heavy) |

All choices follow the CLAUDE.md principle: **stdlib > small lib > framework**.

## Structural decisions

### Plugin management
Plugins are cloned with `git clone` into `plugins/<repo-name>/`. The `plugins/` directory is gitignored in the tool repo — plugins are independent repos, not submodules. Submodules require a commit-on-add roundtrip with no benefit for personal-use tooling.

### Index location
`$ZKM_STORE/.zkm-index/` — inside the store, gitignored by `zkm init`. Rejected: tool-repo-local (would break multi-store usage).

### LLM configuration
Three env vars: `ZKM_LLM_ENDPOINT`, `ZKM_LLM_MODEL`, `ZKM_LLM_KEY`. Works with any OpenAI-compatible endpoint (Ollama, OpenRouter, llama.cpp server, OpenAI). Env vars compose well with shell profiles and `.env`.

### Binary backend auto-detection
`store.py` uses `shutil.which("git-annex")` then `shutil.which("git-lfs")` then falls back to `none`. Mirrors the bash-era `zkm-init.sh` logic.

### `zkm init` idempotency
If `$STORE/.git` already exists, `init_store()` prints a message and returns without error. Lets `zkm init` be re-run safely (e.g., from a setup script).

## Open questions

These are deferred decisions that should be revisited before implementing the relevant Phase 1 features.

### 1. Store `.env` vs. tool-side config for LLM keys
Plugins read `$ZKM_STORE/.env`. Should `ZKM_LLM_*` live there too, or in `~/.config/zkm/config.toml`?

- **Store-side**: one place for all secrets; travels with the store on backup.
- **Tool-side**: separates "store secrets" (credential for a source) from "tool preferences" (which LLM to use); doesn't accidentally include LLM keys in store backups.

Current default assumption: env vars in shell profile, with `$ZKM_STORE/.env` for source credentials only.

### 2. Commit cadence for `zkm convert`
Options: one commit per plugin run (current assumption), one commit per file, or no auto-commit (`--no-commit` flag). One-per-run chosen as default because it keeps the git log clean. A `--no-commit` flag is planned to let users review before committing.

### 3. Index format: pickle vs. SQLite FTS5
`rank_bm25` serialized via pickle is fast to implement but opaque and sensitive to Python version changes. SQLite FTS5 is also BM25, queryable via CLI tools, and durable. Worth revisiting after first real data in the store.

### 4. `zkm-imap` cursor strategy
The plugin needs to track which messages have been imported to stay idempotent. A sidecar cursor file (`$ZKM_STORE/mail/.cursor`) storing `UIDVALIDITY` + last imported UID is the standard IMAP pattern. Decision deferred to when the plugin is written. The plugin **must not** mark messages as `\Seen` on the server — read-only access is safer.

### 5. Timestamp trust for historical imports
`docs/temporal-queries.md` already notes that commit dates ≠ content dates for historical imports. For all Phase 1 work, frontmatter `date:` is authoritative. Plugins are responsible for extracting and writing the correct date. The indexer should sort/filter by frontmatter `date:`, not by file mtime or commit timestamp.

## Feedback preserved for future sessions

- **Prefer replacement over shims** — user explicitly asked to replace `zkm-init.sh`, not keep a deprecated wrapper. Apply the same interpretation to future "replace X" requests unless stated otherwise.
- **Minimal deps** — the stdlib-first rule applies to all future features. No LangChain, no heavyweight SDKs. Check if a small focused library exists before pulling in a framework.
