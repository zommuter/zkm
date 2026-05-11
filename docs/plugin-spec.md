# zkm plugin specification

## Overview

Each converter is a standalone git repo, installed into `plugins/` via `zkm plugin add <git-url>`. The tool repo gitignores `plugins/` — plugins are not vendored.

## Plugin structure

```
zkm-imap/
├── plugin.yaml     # Required: metadata + config schema
├── convert.py      # Required: converter implementation
├── README.md       # Recommended: usage instructions
└── ...             # Optional: additional modules, templates
```

## plugin.yaml

**Naming convention:** The manifest `name:` field is the plugin's bare CLI handle — no `zkm-` prefix. The directory name (`plugins/zkm-*`) carries the namespace at the repo level; `name:` must not repeat it. For example, a plugin in `plugins/zkm-eml/` must declare `name: eml`. `find_plugin()` strips a leading `zkm-` from CLI input for backwards compatibility with older invocations.

```yaml
name: imap
version: 0.1.0
description: Convert IMAP mailboxes to markdown
license: MIT

# Dirs this plugin creates in the store (on first run)
creates_dirs:
  - mail

# Config keys this plugin reads from $ZKM_STORE/.env
config:
  IMAP_HOST:
    required: true
    description: IMAP server hostname
  IMAP_USER:
    required: true
  IMAP_PASS:
    required: true
    secret: true
  IMAP_FOLDERS:
    required: false
    default: "INBOX"
    description: Comma-separated folder list
  IMAP_SINCE_DAYS:
    required: false
    default: "30"
    description: Only fetch emails newer than N days
```

## convert.py interface

```python
from __future__ import annotations
from collections.abc import Callable
from pathlib import Path

ProgressCallback = Callable[[int, int | None, str], None]

def convert(store_path: Path, config: dict, *, progress: ProgressCallback | None = None) -> list[Path]:
    """
    Convert source data into markdown files in the store.

    Args:
        store_path: Root of the knowledge store (e.g., ~/knowledge/)
        config: Dict of config values from .env, filtered to this plugin's keys
        progress: Optional callback(current, total, message). Call once per item
                  processed. total=None is allowed when the count isn't known upfront.

    Returns:
        List of created/updated markdown file paths (for indexing)

    The converter MUST:
    - Write .md files with valid YAML frontmatter (source, date, tags, sha256,
      processor, processor_version)
    - Set `source:` to this plugin's name
    - Set `processor:` to this plugin's name and `processor_version:` to its semver
    - Place binary originals in store_path/originals/ with git-lfs-friendly extensions
    - Be idempotent: re-running should not duplicate existing entries (use sha256 dedup)
    - Be a **no-op on inbox items it does not own**: when scanning `inbox/`, the plugin MUST only process items whose `.origin.json` sidecar lists this plugin's name in `producers[]` (or items the plugin produced itself by walking its own source). Running a plugin against an inbox containing only foreign items MUST return `[]` and exit 0.
    - Create its declared dirs if they don't exist
    - Accept a `progress` keyword argument and call it once per processed item when non-None

    The converter MUST NOT:
    - Call any LLM or external AI service
    - Modify files outside its declared dirs and originals/
    - Store secrets in markdown files
    """
    ...
```

The `progress` kwarg is **mandatory** in new plugins. zkm core passes it only when the plugin declares the parameter (checked via `inspect.signature`), so third-party plugins that omit it still load cleanly.

### Encoding contract

Plugins **MUST emit UTF-8 markdown**. The store, BM25 index, and dense embedder all assume UTF-8 throughout — mis-encoded text degrades stemming and retrieval quality for accented characters. When decoding external bytes (emails, PDF text, OCR output), plugins **SHOULD**:

1. Try the declared/detected charset first, but **skip permissive codecs** (`latin-1`, `cp1252`) in the primary attempt — they accept all byte sequences and mask wrong-charset declarations.
2. Fall back to a detection library (e.g. `charset-normalizer`) when the strict candidates fail.
3. Run a mojibake repair pass (e.g. `ftfy.fix_text`) to catch text that was already mis-decoded upstream before reaching the plugin.
4. Strip any leading BOM (`﻿`) from decoded text before writing to markdown.

Minimal example of a progress-aware loop:

```python
def convert(store_path, config, *, progress=None):
    items = list(_discover_items(config))
    total = len(items)
    for i, item in enumerate(items, 1):
        _process(item)
        if progress:
            progress(i, total, item.name)
    return created
```

Plugins may optionally export a `reprocess` function to support `zkm convert <plugin> --reprocess`:

```python
def reprocess(store_path: Path, config: dict, existing: list[Path], *, progress: ProgressCallback | None = None) -> list[Path]:
    """
    Re-derive already-ingested markdown files from their originals.

    existing: list of .md paths managed by this plugin (already filtered by
              processor_version for --reprocess, or all files for --reprocess-all).

    Returns list of updated .md paths.
    """
    ...
```

## Cancellation

`zkm convert` installs a two-tier signal / ESC handler:

- **First Ctrl+C, SIGTERM, or ESC** (in TTY) → *soft cancel*. The progress callback raises `PluginInterrupt` at the next item boundary. A 30-second countdown is shown; if the plugin doesn't yield within the deadline, hard cancel fires automatically.
- **Second signal, or 30s timer expiry** → *hard cancel*. `KeyboardInterrupt` is raised in the main thread at the next interpreter check (interrupts blocking I/O).
- **SIGKILL** → OS-handled; no graceful path possible.
- **SIGUSR1** → reserved by core for progress reporting. `zkm` installs a SIGUSR1 handler that forces an immediate PID-file write and emits a dd-style stderr line. **Plugins must not install their own SIGUSR1 handler** — doing so will break `zkm status`.

Plugin contract for cancel:

- `progress()` **may raise `PluginInterrupt`** (a `KeyboardInterrupt` subclass). Plugins must not swallow `KeyboardInterrupt` in their main loop.
- Use `try/finally` for cleanup that must run on cancel (e.g., regenerating index files, flushing partial writes).
- Write output files **atomically** (write-then-rename or use a temp path) so a mid-item hard cancel doesn't leave corrupt state.
- Idempotent dedup means re-running after a cancel safely resumes from where the run stopped.

```python
def convert(store_path, config, *, progress=None):
    created = []
    touched = set()
    try:
        for i, item in enumerate(items, 1):
            _process(item, created, touched)
            if progress:
                progress(i, total, item.name)  # may raise PluginInterrupt
    finally:
        _regenerate_indexes(touched)  # runs even on cancel
    return created
```

If `reprocess` is not exported, `zkm convert --reprocess` falls back to calling `convert()` with `ZKM_REPROCESS` set in the environment (`"outdated"` or `"all"`). Simple plugins can check `os.environ.get("ZKM_REPROCESS")` and skip sha256 dedup accordingly.

## Frontmatter

Every `.md` file written by a plugin MUST include:

```yaml
source: <plugin-name>          # identifies the originating plugin
date: 2026-04-13T14:30:00+02:00  # ISO 8601 with timezone
tags: []                       # list (may be empty)
sha256: abc123...              # SHA-256 of the original content or a stable canonical form
original: originals/...        # relative path to raw original (if applicable)
processor: <plugin-name>       # same as source; used for --reprocess targeting
processor_version: 0.1.0       # plugin's semver from plugin.yaml
```

The `original` field is optional for sources without binary originals (e.g. a generated note). `processor` and `processor_version` enable `zkm convert --reprocess` to detect which files need re-derivation when the plugin algorithm improves.

For plugins that handle conversations (email, chat, SMS), see [docs/messaging-spec.md](messaging-spec.md) for additional required fields (`message_id`, `thread_id`, `in_reply_to`, etc.).

## Frontmatter amendments

The md *body* is single-writer — the producing plugin owns it and must not be modified by other plugins. The md *frontmatter*, however, is multi-writer: source plugins write initial placeholder values (`tags: []`, `entities: []`) and *amender* plugins extend those values by emitting amendment records. The merge engine (`zkm.amendments`, landing in Session 10) reads the amendment queue and merges records into frontmatter atomically. This mirrors the multi-producer pattern of `.origin.json` sidecars but operates on md frontmatter instead of CAS objects.

### Per-field merge rules

| Field | Merge rule |
|-------|------------|
| `tags` | Set-union (deduplicate, sort) |
| `entities` | Set-union with role-tagged dedup (key: `(name, role)`) |
| Scalars | Last-write-wins; `emitted_by` attribution recorded in `.amendments.json` sidecar |
| Structured lists | Require an explicit merge key declared by the amender (e.g. `participants` keyed on `address`) |

### Amendment record schema

```json
{
  "schema": 1,
  "key": {"message_id": "<abc123@example.com>"},
  "fields": {"tags": ["bill"]},
  "emitted_by": "zkm-notmuch",
  "emitted_at": "2026-05-08T14:30:00+02:00"
}
```

Key resolution order: `message_id` → `sha256` → relative `path`. The first present key in the record is used. Amenders SHOULD prefer `message_id` for messaging plugins and `sha256` for all other sources.

### Queue-if-md-missing

If an amendment's key resolves to no md file (e.g. `zkm-notmuch` ran before `zkm-eml`), the record is held in the amendments queue and replayed on the next `zkm convert <amender>` or `zkm reconcile`. Records are never silently dropped.

### Attribution sidecar

Each amended md gets a per-md sidecar at `<md-path>.amendments.json`:

```json
{"schema": 1, "applied": [<record>, ...]}
```

This lists every amendment record merged into the md, in application order.

Round-trip test contract (implementation in Session 10): `zkm-eml` writes `tags: []`; a `zkm-notmuch` amendment with `tags: [bill]` is applied; merged md shows `tags: [bill]`; `<md>.amendments.json` contains the record with `emitted_at`.

## Inbox handoff and origin sidecar

Plugins that produce binary attachments (e.g. `zkm-eml`, `zkm-whatsapp`) place them in `inbox/<subdir>/YYYY/MM/` as symlinks into `store_path/mail/_objects/<aa>/<rest>` (or an equivalent CAS store). This lets downstream plugins (`zkm-pdf`, `zkm-photo`) pick them up without re-fetching.

### One canonical symlink per CAS object

When the same attachment content (by sha256) is referenced by more than one source item, only **one** inbox symlink is created. Its date path corresponds to the lexicographically earliest producer path — for date-sharded message paths this is the chronologically earliest message. Additional producers are recorded in the sidecar only.

### Sidecar file

Every inbox symlink MUST have an adjacent `.origin.json` sidecar at `<symlink-path>.origin.json`. The sidecar is a derived file: plugins write or rewrite it whenever they write or update the symlink.

Schema v1:

```json
{
  "schema": 1,
  "sha256": "<sha256 of the bytes the symlink targets>",
  "producers": [
    {
      "plugin": "eml",
      "message": "mail/messages/2026/04/2026-04-13-1430-abc12345-invoice.md",
      "sha256": "<sha256 of the producing message's original .eml>"
    }
  ]
}
```

Invariants:
- `sha256` matches the content-addressable object the symlink points to (verifiable with `sha256sum`)
- `producers` is never empty; ordered by `message` path (ascending) so the list is stable across re-runs
- All paths are relative to `store_path`

### Update strategies

**Incremental run** (processing new items): if a sidecar already exists for a CAS object (another message already produced this attachment), read the existing sidecar, append the new producer entry (dedup on `producer.sha256` — the source-content hash, not the rendered `message` path, which can shift between runs), sort by `message`, and write atomically (write-to-temp → rename).

**`--reprocess-all`**: rebuild the sidecar from scratch by scanning all managed `.md` files for attachment references. This guarantees the sidecar is consistent with the current store state even if messages were deleted or renamed.

### Plugin contract

- A plugin that writes inbox symlinks MUST also write/update `.origin.json` sidecars.
- Sidecars MUST be written atomically (tmp-file + rename) so a mid-write cancel doesn't leave a corrupt JSON file. Plugins SHOULD use `zkm.sidecar.merge_producer()` once available (Phase 2) rather than implementing this directly.
- Downstream plugins MUST NOT assume the sidecar exists — gracefully handle its absence.
- The `zkm convert` auto-commit picks up sidecar files via `git add -A`; plugins do not need to return them from `convert()`.

### Core helpers (Phase 2+)

Once `zkm.sidecar`, `zkm.cas`, `zkm.inbox`, `zkm.atomic`, and `zkm.hashing` land in core, plugins SHOULD import from these rather than re-implementing the protocol. See `docs/object-storage.md` for the full API and rationale. Direct file-writing is still permitted but treated as legacy once the library is available.

### Unowned items

The inbox is a shared zone — multiple producer plugins may deposit items there, and multiple consumer plugins may read from it. A plugin MUST NOT process, rewrite, or delete inbox items it did not produce. Ownership is determined by the `.origin.json` sidecar: an item belongs to plugin `X` if `X` appears in `producers[].plugin`. Plugins that scan `inbox/` for downstream processing (e.g. `zkm-pdf` picking up attachments) MUST check the sidecar and skip items not produced by a plugin they are designed to consume. This prevents `zkm-photo` from accidentally re-processing a PDF that `zkm-eml` deposited for `zkm-pdf`.

## Scrub

`zkm scrub <plugin>` calls the plugin's optional `scrub()` function to retroactively clean up stale frontmatter field values. This is the correct mechanism when an extraction quality improvement (e.g., a new stoplist or POS-filter) means previously-written entities are now incorrect — the set-union amendment merge cannot remove them, so an explicit scrub pass is needed.

### Contract

```python
def scrub(
    store_path: Path,
    config: dict,
    *,
    dry_run: bool = True,
    verbose: bool = False,
    progress=None,
) -> dict[str, int]:
    ...
```

Return shape: `{"files_scanned": int, "files_changed": int, "entities_removed": int}`.

If a plugin does not define `scrub`, `zkm scrub <plugin>` exits 2 with a clear message.

### Requirements

- **Idempotent.** A second `--apply` run MUST report `files_changed=0` and `entities_removed=0`. The caller verifies this.
- **Frontmatter-only.** `scrub()` MUST NOT read or write `<md>.amendments.json` attribution sidecars. Those sidecars record which amendment records were applied; scrub is a direct frontmatter mutation, not a record application.
- **Atomic writes.** Use `zkm.atomic.write_atomic` when writing modified files.
- **Skip hidden dirs.** Exclude paths where any parent component starts with `.` (e.g., `.git`, `.zkm-state`, `.zkm-index`).
- **Dirty-tree guard.** Core enforces this before dispatch — no plugin-side check needed.

### Scrub is not a replacement for extraction quality

Scrub is a one-time migration tool, not a production code path. The right fix is always to improve the extractor so it never emits the undesired value. Scrub cleans up the historical backlog; the improved extractor prevents recurrence.

## Secret management

Secrets live in `$ZKM_STORE/.env`, which is gitignored. Format:

```
# IMAP plugin
IMAP_HOST=mail.example.com
IMAP_USER=user@example.com
IMAP_PASS=hunter2

# WhatsApp plugin
WA_BACKUP_PATH=/path/to/syncthing/whatsapp
```

`zkm convert <plugin>` loads `.env` (hand-rolled `KEY=VALUE` parser — no shell expansion, no multi-line values), filters to the plugin's declared config keys, and passes them to `convert()`.

For plugins requiring OAuth or API tokens (e.g., LinkedIn, Instagram), the same `.env` pattern applies. Plugins should document their auth flow in their README.

## Installing a plugin

```bash
zkm plugin add https://github.com/you/zkm-imap.git
# → clones into plugins/zkm-imap/
# → validates plugin.yaml
# → prompts for missing .env keys

zkm plugin list
# imap  0.1.0  (plugins/zkm-imap)

zkm plugin remove imap
# → removes plugins/zkm-imap/
```

## Known plugin ideas

See [docs/messaging-spec.md](messaging-spec.md) for the full messaging plugin contract.

| Plugin | Source | Complexity | Notes |
|--------|--------|------------|-------|
| `zkm-eml` | `.eml` files / Maildir | Medium | Phase 1. Pairs with mbsync for fetch |
| `zkm-imap` | Live IMAP fetch | Low | Phase 2. Thin wrapper; mbsync preferred |
| `zkm-whatsapp` | WA local backup | Medium | Needs crypt14/15 decryption |
| `zkm-threema` | Threema backup | Medium | Threema safe export → JSON |
| `zkm-signal` | Signal SQLite DB | Medium | Requires phone access |
| `zkm-telegram` | Telegram JSON export | Low | Built-in export feature |
| `zkm-instagram` | IG data download | Low | JSON from data download request |
| `zkm-facebook` | FB data download | Low | JSON from data download request |
| `zkm-linkedin` | LI data export | Low | CSV from settings |
| `zkm-scan` | OCR via tesseract | Low | Watch folder pattern |
| `zkm-photo` | EXIF → sidecar md | Low | exiftool extraction |
| `zkm-diary` | Structured daily note | Trivial | Template + date |
| `zkm-chatlog` | AI chat exports | Low | Parse various formats |

Social media exports (Instagram, Facebook, LinkedIn) are typically one-shot data download requests, not live sync. The plugins parse the downloaded archive into markdown.
