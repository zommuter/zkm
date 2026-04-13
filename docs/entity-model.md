# Entity model and WebUI

Phase 3 feature. Depends on NER from Phase 2.

## Entity pages

The WebUI's core interaction: click a person/org/place name → see a live-aggregated summary with related memories.

**This is NOT pre-computed.** Clicking "Frank" triggers:
1. `zkm search "Frank"` (BM25, plus embedding search if Phase 2 is done)
2. Collect all matching documents with snippets
3. Feed to LLM: "Summarize what I know about Frank based on these sources"
4. Render the summary with linked source documents

This keeps entity pages always current without a rebuild step.

## Why not pre-compute entity files?

Pre-computed entity summaries (like DiffMem's approach) go stale the moment new data arrives. For a personal knowledge base with frequent ingest, the rebuild cadence would need to be very high, and you'd need to track which entities are "dirty" after each ingest.

Live aggregation is simpler: no cache invalidation, no rebuild pipeline, always fresh. The cost is ~1-2 seconds per entity page (search + LLM call). Acceptable for interactive use.

**Exception:** Phase 4 memory compaction *does* write entity summary files — but those are for archival/compression, not for the WebUI's live view.

## NER → frontmatter flow (Phase 2)

When a converter writes a new markdown file, an optional post-processing step runs NER:

```python
# Pseudocode — actual implementation TBD
entities = ner_extract(text)  # spaCy de_core_news_sm or pattern-based
# → [{"type": "person", "value": "Frank"}, {"type": "org", "value": "Stadtwerke Konstanz"}]
```

Results are written back into the file's frontmatter:

```yaml
---
source: imap
date: 2026-04-13T14:30:00+02:00
tags: [bill, electricity]
entities:
  - {type: person, value: Frank}
  - {type: org, value: Stadtwerke Konstanz}
  - {type: place, value: Kreuzlingen}
---
```

The `entities` field is always derived — NER can be re-run and the field overwritten. The `tags` field remains manually curated. This distinction matters: tags are *your* categorization, entities are *extracted* facts.

## WebUI sketch (Phase 3)

Minimal FastAPI app:

- `/` — search box + recent activity
- `/search?q=...` — BM25/hybrid results with snippets
- `/query?q=...` — LLM-augmented answer with sources
- `/entity/<name>` — live-aggregated entity page
- `/doc/<path>` — rendered markdown with entity names linked

Entity names in rendered documents are auto-linked to `/entity/<name>`. This creates a navigable knowledge graph without maintaining an explicit graph database.
