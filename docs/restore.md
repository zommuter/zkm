# zkm store — disaster recovery

This document describes how to recover the knowledge store (`~/knowledge/`) after a full disk loss.

## Primary path: restore from filesystem backup

`~/knowledge/` — including hidden dirs `.zkm-state/` and `.zkm-index/` — should be
covered by your filesystem backup tool (borg, restic, ZFS snapshots, etc.). These tools
do **not** read `.gitignore`; gitignored files are included by default unless explicitly
excluded from the backup job.

Configuration of the backup tool is outside zkm's scope; see `~/src/zomni/` for
the system-level backup setup.

If a recent backup is available, restore the full directory tree and all derived caches
are intact. No re-derive needed.

## Fallback path: re-derive from the markdown tree

If no backup exists (or the backup predates recent conversions), restore only the git
repository:

```bash
git clone <remote-url> ~/knowledge
cd ~/knowledge
zkm convert zkm-ner    # re-extract NER entities into .zkm-state/extraction-cache/  (~25 min)
zkm index              # rebuild BM25 index into .zkm-index/bm25.pkl               (~few min CPU)
zkm index --embed      # rebuild dense embeddings into .zkm-index/embeddings.npz   (~25 min GPU)
```

**Re-derive budget as of 2026-05-13:** ~50 min total (NER 25 min + embed 25 min).
This grows linearly with corpus size and extractor count. Once additional amenders
(zkm-receipt, OCR, etc.) land, budget may reach several hours — at that point
re-evaluate whether the extraction cache should be committed or backed up
separately (see `docs/meeting-notes/2026-05-13-1950-derivable-expensive-data-in-git.md`).

## What is and is not in git

| Path | In git? | Notes |
|------|---------|-------|
| `mail/`, `notes/`, `inbox/` | **yes** | source-of-truth markdown tree |
| `.zkm-state/extraction-cache/` | no — gitignored | 1.1 GB, re-derivable in ~25 min |
| `.zkm-index/embeddings.npz` | no — gitignored | 308 MB, re-derivable in ~25 min |
| `.zkm-index/bm25.pkl` | no — gitignored | 279 MB, re-derivable in minutes |
| `.zkm-state/zkm-eml.json` | no — gitignored | watermark (trivial to lose) |

## Future: `zkm verify` (not yet implemented)

A fast integrity check command (`zkm verify`) could walk the markdown tree, query
`ExtractionCache.get(body_sha256, extractor, model, version)` for each document,
and report the fraction of cache misses — without re-extracting anything.
Implementation: ~2 lines against the existing `ExtractionCache` API plus a tree walk.

**Build gate:** a cache-corruption incident is observed, OR a sub-second "is my cache
intact?" check becomes a concrete need. Do not build speculatively.
