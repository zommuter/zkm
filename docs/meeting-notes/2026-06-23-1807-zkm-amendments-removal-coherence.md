# 2026-06-23 — zkm amendments removal coherence (ner scrub↔cache; notmuch tag removals)

**Started:** 2026-06-23 18:07
**Session:** 6527b616-3844-485b-98e3-8eaa68940163
**Mode:** /meeting (Class 3) — dispatched from a `/meeting --cross` 80/20 relay-unblock triage
**Attendees:** 🧮 Reni (multi-writer set merge / attribution-aware retraction), 🧬 Nora (IE/NER typology), Riku (skeptic / observe-before-preventing)

## Context

A cross-project triage ("which meetings unblock the most relay work?") found the relay fleet is
**design-starved** (22 `[HARD — meeting]` items vs 6 open `[ROUTINE]`), and that the apparent
80/20 cluster (zkm scanned-doc/OCR routing) was already decided + decomposed but never written
back to the plugin ROADMAPs (see Forward actions). The genuinely-warranted convergence was the
two zkm state-coherence items, which share one shape: `zkm.amendments` merges sets by **union**
(grows, never shrinks), and removal logic lives outside the pipeline.

Key discovery during context-gather: the core attribution-aware retract primitive **already
shipped** — `zkm/src/zkm/amendments.py` has `emit_set` / `mode="set"` / `_retractable_values`
/ `plan_retractions`, retracting only a producer's own prior claims (`emitted_by`-scoped),
never user/other-producer values. Neither plugin uses it yet (both still call legacy `emit`).

## Items

### id:7b4e — zkm-ner: keep scrub and the extraction cache coherent

Failure mode (deterministic): `scrub(dry_run=False)` edits frontmatter only; the extraction
cache (`convert.py:129/152`) keeps the removed entities; the next full-sweep `convert` hits the
cache (body sha unchanged), re-emits the stale set, and union-merge resurrects the scrubbed
value. `entities` is not in core `_SET_FIELDS=("tags",)`, so declarative retraction doesn't even
apply to it yet. Adopting `emit_set` alone does NOT fix it — a cache hit re-asserts the *stale*
cached set.

### id:f103 — zkm-notmuch: propagate notmuch tag REMOVALS to frontmatter

Stated blocker was "needs a new core-level removal semantic in `zkm.amendments`". **That semantic
shipped** (`emit_set` + attribution-aware retraction = exactly f103's acceptance sketch: retract
only `emitted_by: notmuch`'s own prior tags, never user/eml tags). zkm-notmuch still calls legacy
`emit` (`convert.py:85`). No design decision remains.

## Discussion

🧮 Reni: same family as f103; the shipped primitive does the heavy lifting. The only reason ner
doesn't "just work" is the cache re-asserting the stale set every sweep — so the fix must make the
cache *emit the post-scrub set*. Rewriting the cache in place makes scrub a second cache writer →
breaks idempotence-by-construction → reject.

🧬 Nora: entities are typed `(scope,type,value)` tuples, not tags; `entities` must be added to
`_SET_FIELDS` as a prerequisite for any `emit_set` fix. Porting removal logic upstream is wrong by
typology: isolated-POS + verifier are value-level heuristics, but scrub also absorbs **human**
"that's a false positive" calls — judgments you can't move into the extractor. Upstream also forces
the expensive verifier on every extraction.

Riku: is 7b4e a real bug or hypothetical? — Reni: deterministic (unchanged body sha → cache hit →
stale re-emit, every sweep). Observe-first gate met. Riku backs the tombstone path on condition it
**reuses `emit_set`** (one primitive, not two) and ships **no tombstone-GC** until growth is
observed.

## Decisions

- **D1 (id:7b4e) — Tombstone + emit_set.** `scrub` writes a per-store tombstone keyed
  `(scope,type,value)`; `convert` filters the cached entity set through the tombstone, then
  `emit_set` asserts the filtered set; the shipped core `_retractable_values` clears the resurrected
  values from frontmatter. Cache stays **immutable / single-writer**. Absorbs both heuristic and
  human removals. Rejected: (a) scrub-rewrites-cache (second writer, breaks idempotence,
  data-loss risk); (b) port-upstream (can't absorb human FP removals; verifier-cost blowup);
  (d) hybrid (two coherence paths). No tombstone-GC machinery until list growth is actually
  observed (observe-first).
- **D2 (id:f103) — Reclassify `[HARD — meeting]` → `[ROUTINE]`.** Core blocker shipped; remaining
  work is a plugin migration (switch `convert.py:85` `emit`→`emit_set` asserting the current tag
  set). Dispatch via `/relay review zkm-notmuch`. No meeting.

## Action items

- [ ] core `zkm.amendments`: add `entities` to `_SET_FIELDS` so declarative set-retraction applies to entities (red-green in zkm core) <!-- id:29ac -->
- [ ] zkm-ner: per-store tombstone store keyed `(scope,type,value)`; `scrub(dry_run=False)` writes a tombstone per removed entity (no GC until growth observed) <!-- id:0566 -->
- [ ] zkm-ner `convert`: filter the cached entity set through tombstones, switch `emit`→`emit_set` (depends on id:29ac) <!-- id:fa5a -->
- [ ] zkm-notmuch id:f103: reclassify to `[ROUTINE]` and migrate `convert.py:85` `emit`→`emit_set` (current tag set); dispatch via `/relay review zkm-notmuch` <!-- id:f103 -->

## Forward actions (not minted — relay's job)

- `/relay review zkm-pdf` + `/relay review zkm-scan` — apply the 2026-06-22 `pdftext` decomposition
  (core id:9e13 landed; emit migrations d3c9/zkm-pdf, 1681/zkm-scan as `[ROUTINE]`; retire the stale
  `9475`/`02bd` `[HARD — meeting]` umbrellas). Biggest immediate executor unblock, no meeting.
- `/relay review zkm-ner` — emit D1's three children (29ac/0566/fa5a) into the ROADMAP as `[ROUTINE]`.
- `/relay review zkm-notmuch` — apply D2 (f103 → `[ROUTINE]` + migration).

## Gate-deferred (NOT meeting-worthy now)

- zkm-photo 8740/62cb/a711 — gated on Phase 3 (WebUI / amender infra), not started.
- zkm-whatsapp 367f (gated on v1-live + observed day-boundary retrieval pain), bf12 (gated on a
  real missed-number case + unbuilt Phase 4 alias design).
