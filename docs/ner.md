# NER — Named Entity Recognition

zkm-ner is an **amender plugin** that extracts entity mentions from markdown bodies and merges them into the `entities:` frontmatter field via `zkm.amendments`. It ships at `plugins/zkm-ner/`.

## Overview

- Declared as `kind: amender` in `plugins/zkm-ner/plugin.yaml`.
- Runs **default-on** after every `zkm convert <producer-plugin>`. Opt out with `--no-amenders`.
- **Never writes the document body.** Only emits amendment records; the merge engine writes frontmatter.
- Creates no store directories (`creates_dirs: []`).
- Configuration: `ZKM_NER_MODEL` (backend), `ZKM_NER_LANG` (force language), `ZKM_NER_GAZETTEER` (custom org YAML).

## Extractor pipeline

Processing order per document:

1. **Pre-strip** — `textfilter.strip_markdown_artefacts` removes markdown table separators, pure-pipe rows, and empty pipe-cell artefacts from the body before extraction.
2. **Pattern overlay** — high-precision regex patterns applied first; typed entities bypass the downstream POS-filter.
3. **spaCy NER** — `de_core_news_sm` and `en_core_web_sm`; language selected by doc-level `langdetect`; `ZKM_NER_LANG` forces a fixed language.
4. **POS-filter** — spaCy NER results filtered to `ent.root.pos_ == "PROPN"` only; pattern-overlay entities bypass.
5. **Post-filter** — `textfilter.drop_stoplist`, `textfilter.drop_commonnoun_stoplist`, `textfilter.drop_structural_artefacts` applied to all entity values.
6. **Merge with pattern results** — patterns win on span overlap.
7. **GLiNER backend** (opt-in) — replaces spaCy when `ZKM_NER_MODEL=gliner`; requires `pip install zkm-ner[gliner]`; uses `gliner-multilingual-v2.1`.

### Pattern categories

| Pattern type | `entity.type` | Canonical | Standard | Notes |
|---|---|---|---|---|
| Email address | `email_address` | Yes (domain lowercase) | `rfc5321` | RFC 5321 local+domain |
| Phone — DE/CH | `phone_number` | Yes (E.164) | `E.164` | +41 / +49 / 0800 / 07xx; libphonenumber |
| URL | `url` | — | `rfc3986` | http/https; excludes bare domains |
| Domain → org hint | `org_hint` | — | — | bare domain stripped of TLD |
| IBAN | `iban` | Yes (compact, no spaces) | `ISO 13616` | mod-97 checksum; `valid: false` on fail |
| Monetary amount | `amount` | Yes (`{decimal} {ISO-4217}`) | `ISO 4217` | DE/CH/EN formats; DE decimal comma normalised |
| Invoice identifier | `invoice_id` | — | — | keyword-anchored (Rechnung-Nr, Invoice #, …) |
| Parcel tracking | `tracking_id` | — | — | UPS 1Z…, DHL JD…, Swiss Post 99… |
| Registration code | `registration_code` | Yes for EAN-13/ISBN-13 | `ISBN-13` / `EAN-13` where applicable | HRB/HRA, ISBN-13, EAN-13, DIN |
| Social handle — Discord | `social_handle.discord` | — | — | `#1234` discriminator required |
| Social handle — Telegram/Steam/GitHub/Twitter/Fediverse | `social_handle.<platform>` | — | — | per-platform regex |
| LinkedIn profile | `linkedin_profile` | — | — | `linkedin.com/in/...` URL |
| GitHub profile | `github_profile` | — | — | `github.com/<handle>` URL |
| Org gazetteer | `org` | Value IS canonical | — | alias → canonical lookup via `gazetteers/orgs.yaml` |

spaCy types that pass the POS-filter: `PER` (→ `person`), `ORG` (→ `org`), `LOC` (→ `place`), `MISC` (→ `misc`). spaCy-produced entities carry no `canonical` or `standard` field.

## Quality controls

Extracted entities pass through a filter chain addressing four pollution classes identified during the N9 pilot (55k-document mail corpus):

| Pollution class | Example FPs | Fix layer | Implementation |
|---|---|---|---|
| 1 — Markdown syntax fragments | `---`, `===` | Pre-strip body | `strip_markdown_artefacts()` |
| 2 — Email header column names | `Subject`, `Thread`, `Betreff` | Closed-set stoplist | `_STOPLIST` (N9b, 14 words) |
| 3 — Subject-line prefixes | `Re`, `Fwd`, `Aw` | Same closed-set stoplist | `drop_stoplist()` |
| 4 — Common-noun false positives | `Du`, `Zeit`, `EUR`, `Internet` | POS-filter + commonnoun stoplist | `_pos_filter()` + `_COMMONNOUN_STOPLIST` (N9c) |
| 5 — Pipe-cell structural artefacts | `| |`, `|  |` | Value regex reject | `drop_structural_artefacts()` (N9c-8) |

Each fix layer is keyed into the extraction cache via a `model_version` string (currently `+textfilter-v2+posfilter-v1`). A quality improvement that changes the output distribution **must** bump `model_version` so the cache auto-invalidates.

`zkm scrub ner [--apply]` retroactively removes stale entities from frontmatter when a quality improvement would have filtered them. The set-union amendment merge cannot remove; scrub is the only removal path.

## Cache

`src/zkm/extraction_cache.py` — per-store, per-extractor, per-document cache.

**Key:** `(body_sha256, model_name, model_version)`. Body sha256 hashes the *body content only* (frontmatter stripped); changing frontmatter does not invalidate the cache.

**Location:**
```
<store>/.zkm-state/extraction-cache/ner/<sha256[:2]>/<sha256[2:]>.json
```

**Schema (version 1):**
```json
{
  "_schema_version": 1,
  "body_sha256": "abc…",
  "extractor": "ner",
  "entries": {
    "<model_name>:<model_version>": {
      "entities": [...],
      "cached_at": "2026-05-11T14:30:00+02:00"
    }
  }
}
```

A model swap preserves other variants in the same file. Schema version bump drops all entries for that extractor (lazy rewrite on next `put`).

> **Note:** `docs/object-storage.md` describes a *different* extraction cache — a per-CAS-object content cache for the binary-extraction pipeline (pdf/photo/scan OCR), which is still design-only. The two caches are distinct by key space, location, and target content class. Reconciliation of the two designs is a follow-up task.

## Amender contract

Full amendment merge rules: see `docs/plugin-spec.md` § "Frontmatter amendments" (the canonical source, covering `tags`, `entities`, scalar last-write-wins, and structured-list merge keys).

NER-specific notes:
- Set-union dedup key is `(type, value)` — not the pre-N4 `(name, role)`.
- The amendment record's `emitted_by` field is `"ner"`.
- A re-run against unchanged documents short-circuits entirely at the cache-hit branch; no amendment records are emitted.

## Scope boundary

**Mentions, not UIDs.** `entity.value` is the mention string as it appears in the document. There is no `id:` field, no `same_as:` cross-document link, no heuristic identity clustering. Reason: a name alone is not a unique identifier — duplicate first+last names exist in real corpora, and false merges are harder to undo than a manual merge.

**What is out of scope (permanently or until Phase 4):**
- Cross-document co-reference resolution — deferred to Phase 4.
- Intra-document pronoun co-reference (`he`, `she` → entity) — deferred to Phase 4.
- Heuristic fuzzy clustering (`Frank Müller` → single entity record) — deferred; manual-merge tooling preferred.
- GLiNER as default backend — opt-in only; `ZKM_NER_MODEL=gliner`.
- LLM verifier pass on residual FPs — backlogged as N9d, gated on post-N9c re-pilot residual rate.
- Closed-loop learned denylist — backlogged as N9e, depends on N9d.

## Quality pilot methodology

When running a classification gate (e.g. via `scripts/gate_classify.py`), each sample item **must** include at least 500 characters of surrounding context, or the full document body when the document is shorter. A 120-char `context_snippet` is insufficient for human judgement on short or ambiguous entity strings — the N9d Stage 2 pilot (2026-05-12) demonstrated that person-lowercase fragments and single-token MISC entities cannot be reliably classified without seeing the enclosing sentence and at least one paragraph of context.

Concretely: any script that generates a JSONL review file for human classification must expose the entity value, its `suspicious_reason`, and a `context` field containing `body[max(0, start-250):end+250]` (≥500 chars centred on the entity span). If the entity span is not tracked, fall back to the full body.
