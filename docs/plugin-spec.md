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
