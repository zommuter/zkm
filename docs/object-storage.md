# Object storage in zkm

## Why a CAS layer at all

Git is content-addressed, but git-annex and git-lfs externalize the actual bytes. That means git object IDs are not stable in-tree paths. zkm's CAS layer (`_objects/<aa>/<rest>`) provides a stable, in-tree path for binary content that stays valid regardless of which backend (annex / lfs / none) is in use.

The date-sharded inbox symlinks (`inbox/<subdir>/YYYY/MM/<filename>`) give downstream plugins a conventional filesystem view without re-fetching. CAS is the storage side; symlinks are the navigation side.

## On-disk layout

```
<store>/
├── mail/
│   ├── _objects/
│   │   └── aa/
│   │       ├── bbb...          # bytes (one file per sha256)
│   │       └── bbb....json     # per-object sidecar (all producers)
│   └── messages/YYYY/MM/       # rendered markdown
└── inbox/
    └── mail/
        └── YYYY/MM/
            ├── filename         # symlink → ../../../../mail/_objects/aa/bbb...
            └── filename.origin.json  # inbox-side sidecar (same schema)
```

## Sidecar schema v1

Both the per-object sidecar and the inbox `.origin.json` use the same schema:

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

`producers` is the "pointed-by" list. It answers the question "which source items produced this attachment?"

## Producer-dedup invariant

**The dedup key is `producer.sha256`** (the producing source object's content hash), not the rendered `message` path. Rendered paths can shift between runs (e.g. when a Message-ID is synthesized from headers and those headers vary slightly between retrieval methods). Source content does not shift.

Violation of this invariant causes the `producers[]` list to grow on every rescan — the symptom that prompted this design review (2026-05-07).

### Multiple producer plugins are normal

The `producers[]` list may contain entries from **distinct plugins** for the same CAS object. Example: a JPEG attached to an email is produced by `zkm-eml` (as `producer.plugin = "eml"`); the same JPEG, scanned independently by `zkm-photo`, adds a second entry with `producer.plugin = "photo"` keyed by the photo source path. Dedup remains on `producer.sha256`, so a second run of either plugin does not grow the list — but a *new* plugin attaching to an existing CAS object always extends `producers[]` by exactly one entry.

## One canonical symlink per CAS object

When the same attachment content (by sha256) is referenced by more than one source item, only one inbox symlink is created. Additional producers are recorded in the sidecar. The symlink's date path corresponds to the earliest producer by `message` path (ascending sort), which for date-sharded paths is the chronologically earliest message.

## Extraction caches — two distinct designs

There are two separate extraction caches in zkm. They share a similar key structure but address different extraction problems and live in different locations.

### 1. Per-document NER cache (`src/zkm/extraction_cache.py`) — shipped Phase 2.5

Caches the output of text-level extractors (NER, future OCR text post-processing) keyed by the **body content hash** of the rendered markdown, not the CAS object. Lives at `<store>/.zkm-state/extraction-cache/<extractor>/<aa>/<rest>.json`. Key tuple: `(sha256_of_body, extractor_name, model_name, model_version)`. An extractor upgrade (e.g. bumping `model_version` in `version.py`) automatically misses old entries.

This cache is **implemented** and in production use by `zkm-ner`. See `docs/ner.md` for the full design, cache invalidation rules, and the `model_version` bump convention.

### 2. Per-CAS-object content cache — design only, Phase 3+

Content plugins (pdf/photo/scan) run expensive binary extraction on every invocation (text layer parsing, OCR, VLM captioning). A per-CAS-object cache will make re-runs cheap by skipping completed stages.

**Cache shape** — per CAS object, multi-stage, per-extractor. Suggested location: `<aa>/<rest>.extract.json` alongside the object file:

```json
{
  "schema": 1,
  "sha256": "<sha256 of the object>",
  "stages": {
    "pdfplumber-0.10": {"text": "...", "extracted_at": "2026-05-08T14:30:00+02:00"},
    "tesseract-5.3":   {"text": "...", "extracted_at": "2026-05-08T14:35:00+02:00"}
  }
}
```

Stage keys are `<extractor-name>-<version>` so an extractor upgrade automatically misses the old cache entry.

**Open question — merge with `producers[]`**: the per-object `.json` sidecar (today producers-only) could gain a `stages` key, or extraction cache could live in a separate `.extract.json` file. Decision deferred to Phase 3 when N=2 evidence (zkm-pdf + zkm-scan both landing) makes the trade-offs concrete.

**Status**: no implementation in Phase 2.5. Design captured here so the first content plugin (`zkm-receipt` or similar in Phase 3) lands against an established target.

## Library API (Phase 2+, `src/zkm/`)

```python
from zkm.atomic  import write_atomic                      # write_atomic(path, content)
from zkm.hashing import sha256_file, git_blob_sha1        # git_blob_sha1(path) → SHA-1 hex
from zkm.hashing import git_blob_hash_bytes               # git_blob_hash_bytes(data, object_format="sha1"|"sha256")
from zkm.cas     import write_object                      # write_object(store, subdir, src) -> Path
from zkm.sidecar import merge_producer, remove_producer   # concurrent-safe (fcntl.LOCK_EX)
from zkm.sidecar import read_sidecar, rebuild_sidecar
from zkm.inbox   import symlink_with_sidecar              # implements one-canonical-symlink protocol
```

`git_blob_hash_bytes` (added M6 / 2026-05-14) supports SHA-256 git repos (`object_format="sha256"`); defaults to SHA-1 for backward compatibility.

`merge_producer` and `remove_producer` acquire an exclusive `fcntl` lock on a sibling `.lock` file before the read-modify-write, eliminating the race condition verified in the 2026-05-14 concurrent-run-guard session.

Plugins SHOULD import from these rather than re-implementing the protocol. See `docs/plugin-spec.md § Core helpers`.

## Sidecar vs. in-document storage

When deciding whether new per-file data belongs in the `.md` itself or in a sidecar
file, apply this heuristic (ratified 2026-06-26, meeting id:3322):

> **Single-producer + in-band + primary data → in-document (frontmatter or footer).**
> **Multi-producer + out-of-band + machine bookkeeping (values mirrored to frontmatter) → sidecar.**

In practice:

| Property | In-document | Sidecar |
|---|---|---|
| Writer count | Single (the plugin that owns the file) | Multiple (amenders, cross-plugin) |
| Write timing | In-band with the same convert pass that writes the body | Out-of-band / async (queued, applied later) |
| Content type | Primary data or truth-source (manifest, transcript) | Machine bookkeeping; human-facing values mirrored elsewhere |
| Self-contained? | Yes — git-mv / restore works on the `.md` alone | No — needs the sidecar to reconstruct full state |

**Applied examples:**
- **Per-chat-day manifest** (`<!-- zkm:manifest … -->` footer): single-producer (the chat plugin), in-band, primary data → **in-document footer**. See `docs/messaging-spec.md §Footer manifest`.
- **Amendment ledger** (`<md>.amendments.json`): multi-producer (NER, notmuch, future amenders), out-of-band (queued and applied asynchronously), machine bookkeeping (producer-sets + ref-counts; values mirrored to frontmatter) → **sidecar**.

The amendment ledger uses a sidecar for the EXACT INVERSE reason the manifest uses the footer: if attribution lived in the `.md`, every amender would rewrite a file owned by a different plugin, creating write contention with the body-writer and each other.

## Hygiene commands

- **`zkm rm <path>`** — remove a managed `.md`; decrement sidecar `producers[]`; if last producer, remove the inbox symlink; if the CAS object is now unreferenced, remove it. Dry-run by default; `--apply` to commit.
- **`zkm gc`** — scan all sidecars; report (or remove with `--apply`) CAS objects whose `producers` list is empty or missing.

These commands live in core because they must reason about all plugins' producers simultaneously. A per-plugin `rm` cannot safely decide whether another plugin still references the same CAS object.
