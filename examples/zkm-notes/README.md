# zkm-notes

[zkm](https://github.com/zommuter/zkm) plugin that imports plain text and markdown files from a local directory into the knowledge store's `notes/` subfolder.

This plugin is **bundled in the zkm repo** (`examples/zkm-notes/`) as a reference implementation and a usable plain-text importer. It exercises the full plugin interface (see [`docs/plugin-spec.md`](https://github.com/zommuter/zkm/blob/main/docs/plugin-spec.md)).

## What it does

- Scans a source directory recursively for `.txt` and `.md` files
- Deduplicates by SHA-256 — re-running is safe and idempotent
- Writes each new file to `notes/<date>_<slug>.md` with frontmatter
- Preserves existing `date:` frontmatter if present; falls back to file mtime
- Accepts optional default tags via `NOTES_DEFAULT_TAGS`

## Install

The plugin is already present in every zkm checkout. Register it:

```bash
zkm plugin add ./examples/zkm-notes
```

## Configure

Add to `$ZKM_STORE/.env`:

```env
NOTES_SOURCE_DIR=/path/to/your/notes/folder
NOTES_DEFAULT_TAGS=imported          # optional, comma-separated
```

## Run

```bash
zkm convert notes
```

## For plugin authors

This plugin is the canonical reference for the zkm plugin contract:

- `convert(store_path, config)` receives resolved config values (missing required keys already validated)
- Declare store subdirs in `creates_dirs` in `plugin.yaml`
- Deduplicate via the `sha256` frontmatter field
- Return a list of newly written `Path` objects

See [`docs/plugin-spec.md`](https://github.com/zommuter/zkm/blob/main/docs/plugin-spec.md) for the full interface contract.

## License

MIT — see [LICENSE](https://github.com/zommuter/zkm/blob/main/LICENSE) (bundled with core zkm)
