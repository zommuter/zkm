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

## NER → frontmatter flow (Phase 2.5)

NER is implemented in `plugins/zkm-ner/` as an amender plugin that runs default-on after every `zkm convert`. See `docs/ner.md` for the full pipeline (pattern categories, quality controls, cache shape, scope boundary). The section below describes the WebUI's use of the resulting frontmatter; extraction details live in `docs/ner.md`.

Results are written back into the file's frontmatter via `zkm.amendments`:

```yaml
---
source: imap
date: 2026-04-13T14:30:00+02:00
tags: [bill, electricity]
entities:
  - {scope: body, type: person, value: Frank}
  - {scope: body, type: org, value: Stadtwerke Konstanz}
  - {scope: body, type: place, value: Kreuzlingen}
  - {scope: signature, type: email_address, value: frank@stadtwerke.example, canonical: frank@stadtwerke.example}
  - {scope: signature, type: phone_number, value: "+41 44 123 45 67", canonical: "+41441234567", standard: E.164}
---
```

The `entities` field is always derived — NER can be re-run and the field overwritten. `zkm scrub ner` removes stale entities when extractor quality improves. The `tags` field remains manually curated. This distinction matters: tags are *your* categorization, entities are *extracted* facts.

## γ schema — entity type registry

As of zkm-ner v0.8.0, every entity carries a `scope` (provenance), optional `canonical` (normalised form), `standard` (governing standard for canonical), and `valid` (False if normalisation failed checksum). The dedup key is `(scope, type, value)` — the same entity value at different scopes coexists.

### Valid types

| Type | Canonical | Standard | Expected scope(s) | PII sensitivity |
|---|---|---|---|---|
| `email_address` | Yes (domain lowercase) | `rfc5321` | `body`, `signature` | High |
| `phone_number` | Yes (E.164) | `E.164` | `body`, `signature` | High |
| `iban` | Yes (compact, no spaces) | `ISO 13616` | `body` | Med |
| `amount` | Yes (`{decimal} {ISO-4217}`) | `ISO 4217` | `body` | Low |
| `url` | — | `rfc3986` | `body`, `signature` | Low |
| `org` | Value is canonical (gazetteer alias → canonical name) | — | `body`, `signature` | Low |
| `org_hint` | — | — | `body` | Low |
| `person` | — | — | `body`, `salutation`, `signature` | High |
| `place` | — | — | `body` | Low |
| `misc` | — | — | `body` | Low |
| `linkedin_profile` | — | — | `body`, `signature` | High |
| `github_profile` | — | — | `body`, `signature` | Med |
| `social_handle.<platform>` | — | — | `body`, `signature` | Med |
| `invoice_id` | — | — | `body` | Low |
| `tracking_id` | — | — | `body` | Low |
| `registration_code` | Yes for EAN-13/ISBN-13 (digits only) | `ISBN-13` / `EAN-13` where applicable | `body` | Low |

When `canonical` is present, both the raw `value` and the `canonical` form are indexed (see `src/zkm/index.py`, `src/zkm/embed.py`). When `valid: false`, the canonical failed its checksum; the raw value is stored as-is and flagged for review.

### Provenance scopes

Scopes are open-vocabulary; each plugin declares which scopes it emits via `plugin.yaml`. The following scopes are currently defined or planned:

| Scope | Producing plugin | Status | Meaning |
|---|---|---|---|
| `body` | zkm-ner (default) | Shipped v0.1.0 | Entities extracted from the document body |
| `contact` | zkm-vcard | Shipped v0.1.0 | Structured vCard fields (FN, EMAIL, TEL, ORG, URL, social handles) — authoritative, plugin-emitted |
| `signature` | zkm-eml (N9g-pre) | Planned | Entities from email signature block |
| `salutation` | zkm-eml (N9g-pre) | Planned | Entities from greeting / salutation line |

New scopes may be introduced by future plugins without a schema migration; `zkm.amendments` applies a graceful-read (missing scope defaults to `body`).

## WebUI sketch (Phase 3)

Minimal FastAPI app:

- `/` — search box + recent activity
- `/search?q=...` — BM25/hybrid results with snippets
- `/query?q=...` — LLM-augmented answer with sources
- `/entity/<name>` — live-aggregated entity page
- `/doc/<path>` — rendered markdown with entity names linked

Entity names in rendered documents are auto-linked to `/entity/<name>`. This creates a navigable knowledge graph without maintaining an explicit graph database.

## PII redaction (design note, deferred)

Entity extraction surfaces personal data — phone numbers, email addresses, person names — that may need to be withheld in certain sharing scenarios. The redaction strategy is deliberately deferred until the first concrete sharing scenario arises, because the right mechanism depends on the context: a full entity-type denylist for a structured export differs from on-the-fly masking in the WebUI, which differs from summary-level filtering when building LLM context. A premature general solution would constrain all three.

When a sharing scenario is concrete (export pipeline, public WebUI, or sync to a non-local LLM endpoint), the implementation target is a **config-driven entity-type denylist**: a list of `entity.type` values whose `value` strings are replaced with `[REDACTED]` at the rendering/export stage. Source markdown is never modified. Default is empty (no redaction).

The redactor's scope extends beyond source markdown: the BM25 index token stream and the dense embedding input both pass through the entity pipeline. `zkm.canonical.<type>` is the integration point — both index writers and the redactor normalize values through the same canonical function (`src/zkm/canonical.py`), so a denylist entry for `email_address` matches both the raw form and the domain-lowercase canonical form without requiring two separate rules.
