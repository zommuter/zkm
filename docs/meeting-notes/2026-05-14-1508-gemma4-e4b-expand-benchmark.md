# 2026-05-14 — gemma4-e4b as expand model: n=7 benchmark

**Started:** 2026-05-14 15:08
**Session:** 8552820d-ab16-4e21-a60b-f090d368bb59
**Mode:** Class 2 planning record (no meeting — empirical benchmark session)
**Topic:** Compare gemma4-e4b vs aya-expanse-8b for `--expand` query expansion; decide default expand model.

## Context

The 2026-05-08 discovery stated "aya-expanse-8b is the only tested local model that reliably emits EN+DE expansion keywords for both DE and EN queries." gemma4-e4b was not in the stack at that time. After gemma4-e4b was promoted to default LLM (2026-05-13, always-on TTL=0), the question arose: has gemma4-e4b ever been tested for the `--expand` path?

Answer: no. This session ran the comparison.

## Plan

1. Patch `~/knowledge/zkm-config.yaml` `core.expand.model` temporarily to gemma4-e4b.
2. Run 7 queries (2 initial DE/EN pair + 5 diverse follow-ups) with both models.
3. Evaluate: bilingual coverage, keyword quality, query echoing, volume.
4. Restore config; decide; file follow-up TODOs.

Note: `ZKM_LLM_EXPAND_MODEL` env var is no longer read after M2 — config patch was required.

## Results

| Query | Lang | aya-expanse-8b | gemma4-e4b |
|---|---|---|---|
| Stromrechnung | DE | 12 kw; bilingual; on-topic; mild drift (Erneuerbare Energien) | 6 kw; precise 3+3; on-topic; no drift |
| electricity invoice payment | EN | 6 kw; clean 3+3 | 6 kw; **query echoed** as kw #1; 4 DE variations of same concept |
| Krankenkasse Prämie | DE | 10 kw; bilingual; mixed-language within kw ("monatliche Prämie Monthly premium") | 6 kw; clean 3+3; natural phrasing |
| vacation hotel booking | EN | 12 kw; diverse | 6 kw; **query echoed twice** ("vacation hotel booking", "hotel booking vacation") |
| GitHub Actions workflow | EN | 6 kw; good bilingual; no drift | 6 kw; **query echoed**; no DE-specific terms added |
| Wohnungssuche Miete | DE | 10 kw; decent; one awkward compound | 6 kw; EN slightly odd ("Rental search housing"); DE good |
| invoice Amazon order | EN | 6 kw; clean; on-topic | 6 kw; near-query repetition; DE good |

**Averages:** aya 8.9 kw/query; gemma 6.0 kw/query (always exactly 3+3).

## Key findings

- **gemma4-e4b IS bilingual** — reliably produces both EN and DE keywords for all 7 queries (DE and EN input). The "only tested model" qualifier in the 2026-05-08 discovery is now obsolete.
- **Query-echo problem** — gemma4-e4b returns the query string (or a near-variant) as one of its keywords in 5 of 7 cases. Since the query is already in the BM25 search, this expansion slot adds no recall value.
- **aya has better diversity** — generates more keywords with wider synonym variety; gemma4-e4b stays on-topic but at cost of variety.
- **aya has one artifact** — mixes DE+EN within a single keyword token in 1/7 cases.
- **Timing** — not explicitly benchmarked for expand calls. Proxy: gemma4-e4b is always warm (TTL=0, preloaded); aya cold-loads on demand (observed 180s warm-up window message in one test). TTFT numbers from llm_benchmark.py (0.62s gemma vs 0.99s aya) apply to query-answering, not expand completions.

## Decisions

- **Switch expand model to gemma4-e4b** — always-on warm model; bilingual coverage confirmed; echo issue accepted for now pending fix. `~/knowledge/zkm-config.yaml` `core.expand.model: gemma4-e4b` (applied in this session).
- **File echo-issue TODO** — investigate prompt tweak to suppress query echoing; if fixed, quality gap closes.
- **File expand-latency TODO** — run explicit timing comparison (expand call wall-clock) before the echo-fix session to have a proper before/after baseline.
- **Update 2026-05-08 discovery** — remove "only tested model"; add gemma4-e4b finding with echo caveat.
- **M8 done** — user confirmed `zkm convert eml --reprocess` was run and yielded 0 updates; marking complete.

## Action items

- [ ] `TODO.md` — add echo-issue investigation under expand/LLM section; add expand-latency benchmark item; mark M8 done.
- [ ] Update `docs/meeting-notes/meeting-style.md` past-meetings index.
- [ ] Update 2026-05-08 bilingual-expand discovery entry.
