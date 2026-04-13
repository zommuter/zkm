# zkm-notes

Sample zkm plugin that imports plain text and markdown files from a local directory
into the knowledge store's `notes/` subfolder.

This plugin is **included in the zkm tool repo** as a reference implementation.
It exercises the full plugin interface (see `docs/plugin-spec.md`).

## Install

```bash
zkm plugin add ./examples/zkm-notes
```

## Configure

Add to `$ZKM_STORE/.env`:

```
NOTES_SOURCE_DIR=/path/to/your/notes/folder
NOTES_DEFAULT_TAGS=imported          # optional, comma-separated
```

## Run

```bash
zkm convert notes
```

Every file not yet imported (identified by sha256) is written to `notes/` with YAML frontmatter.
Re-running is safe — already-imported files are skipped.

## Design notes (for plugin authors)

- `convert(store_path, config)` receives resolved config values (missing required keys already validated)
- Declare subdirs in `creates_dirs` in `plugin.yaml`; dedup via `sha256` frontmatter field
- Date from file mtime; preserved if the source already has frontmatter `date:`
