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
from pathlib import Path

def convert(store_path: Path, config: dict) -> list[Path]:
    """
    Convert source data into markdown files in the store.

    Args:
        store_path: Root of the knowledge store (e.g., ~/knowledge/)
        config: Dict of config values from .env, filtered to this plugin's keys

    Returns:
        List of created/updated markdown file paths (for indexing)

    The converter MUST:
    - Write .md files with valid YAML frontmatter (source, date, tags, sha256)
    - Set `source:` to this plugin's name
    - Place binary originals in store_path/originals/ with git-lfs-friendly extensions
    - Be idempotent: re-running should not duplicate existing entries (use sha256 dedup)
    - Create its declared dirs if they don't exist

    The converter MUST NOT:
    - Call any LLM or external AI service
    - Modify files outside its declared dirs and originals/
    - Store secrets in markdown files
    """
    ...
```

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

`zkm convert <plugin>` loads `.env` via `python-dotenv`, filters to the plugin's declared config keys, and passes them to `convert()`.

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

| Plugin | Source | Complexity | Notes |
|--------|--------|------------|-------|
| `zkm-imap` | Email via IMAP | Low | Phase 1 priority |
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
