# 2026-05-11 — N9d: LLM verifier for residual NER false positives

**Started:** 2026-05-11 23:16
**Session:** 26a67bed-3383-4a0a-8db0-b32852c65261
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🧠 Mira (multimodal ML — classifier cost, failure modes, privacy)
**Topic:** Design the LLM verifier path for residual open-set NER false positives confirmed by N9d-β re-pilot.

## Agenda

1. **Verification scope** — what gets sent to the LLM? All entities, suspicious-flagged residuals, or both?
2. **Caching key + model choice** — `(value, type)` only or include context? Local model selection (cost ceiling).
3. **Pipeline integration mode** — inline in `convert`, separate subcommand, or amender-style pass.
4. **Pilot protocol** — two-stage smoke gate before infra commitment; success bar declared upfront.
5. **N9e roadmap** — bidirectional heuristic ⇄ verifier provenance (schema sketch only, not implementation).

## Surfaced context

- N9d-β re-pilot (2026-05-11): open-set FP confirmed — person-lowercase German fragments ~3,847 (1.1%), single-token MISC suspicious 10,932 (3.2%). Both above the ≥0.5% volume floor; trigger fired.
- Total mentions: 340,431 post-N9f (already -55% vs raw).
- Existing LLM stack: `src/zkm/expand.py` (httpx + llama-swap probe + chat-completions); local models on llama-swap: aya-expanse-8b (bilingual), qwen2.5/3.5 family, qwen3.6-35B-A3B.
- `src/zkm/extraction_cache.py` keyed by `(body_sha256, model_name, model_version)` — designed for doc-level extraction, not entity-level verification.
- Two-stage smoke-gate protocol established in N9d-α (2026-05-11-1531) — same shape applies here.
- `_is_suspicious` predicate already exists in `plugins/zkm-ner/scripts/pilot.py` — seeds the candidate set for verification.
- Mira's pre-emption from warrant-check: at 30 in / 5 out tokens × 200ms × 340k entities = ~19 h wall-clock for naive pass; dedup by `(value, type)` collapses long tail.

## Discussion

### Item 1 — Verification scope

🏗️ Archie laid out three scopes: (a) all 340k mentions (deduped ~30–50k unique), (b) heuristic-passed entities (same set as a post-N9f), (c) only `_is_suspicious`-flagged residuals (already a predicate in `pilot.py`, ~10–15k items, ~3–5k unique). N9d-β data localises open-set FPs inside the suspicious bucket; legit top-N (Google LLC, PayPal, SBB) are not flagged.

😈 Riku flagged three risks with (c): heuristic-trusting-heuristic blind spots; conservative bias (boilerplate-legal won't be filtered); minimum evidence to rescope is a future pilot showing FPs cross out of `_is_suspicious` reach (relevant when non-stationarity fires).

🧠 Mira: cost lens kills (a)/(b) at ~50 min/pass even deduped; (c) at ~5–10 min is comfortable. Privacy: (c) limits LLM exposure to pre-flagged suspicious strings rather than arbitrary mail content. Context-vs-value-only flagged as a separate decision (Item 2).

✂️ Petra: N=2 satisfied conditional on zkm-claude-* roadmap; non-stationarity rider already in scope. Out-of-scope for v1: own-name signature pollution, boilerplate-legal text.

**Item 1 decision:** scope = suspicious-flagged residuals (primary) + 1–2% random control sample of non-suspicious entities (blind-spot tripwire). All-heuristic-passed scope deferred — promote later once verifier proven.

### Item 2 — Cache key + model choice

🏗️ Archie: cache granularity `(value, type, model, version)` (small, dedup-friendly) vs `(value, type, context_sha256, …)` (principled but kills dedup). Local model options: aya-expanse-8b (bilingual, deployed), qwen2.5-3b/4b (faster, weaker on DE), qwen3.6-35B-A3B-UD-Q4_K_M (stronger, slower).

🧠 Mira proposed two-tier shape:
- Tier 1 cheap value-only prompt cached on `(value, type, model_version)`, Yes/No/Unclear; high-confidence Yes/No → final.
- Tier 2 one context-augmented call per value's *first* doc on `Unclear` returns; result stored as note inside the same cache entry (no re-keying).
- Cap: ~5k Tier 1 + ~1k Tier 2 = ~6k calls one-time (~20 min wall-clock), near-zero on re-run.
- Model: aya-expanse-8b as v1 starting point; swap to qwen3.6-35B-A3B-UD-Q4_K_M only if Tier 1 accuracy is poor.

😈 Riku flagged: Yes/No/Unclear prompt design is itself a quality decision, local model determinism caveat (temp 0 ≠ fully deterministic under quantisation); prompt tweaks re-run all 5k calls without explicit invalidation policy; pilot's 5-bucket classification must include a *verifier-removed-but-actually-legit* sub-class as a tripwire on legit-entity loss.

✂️ Petra: doc-context-free cache key required for v1.

🏗️ Archie: reuse `ExtractionCache` infra with `extractor_name="ner_verifier"`; repurpose `body_sha256` to hold `sha256(value + ":" + type)`; prompt hash baked into `model_version` (`+prompt-vN`).

**Item 2 decision:** two-tier shape + aya-expanse-8b as v1 model; qwen3.6-35B-A3B-UD-Q4_K_M tracked as fallback if pilot accuracy disappoints.

### Item 3 — Pipeline integration mode

🏗️ Archie laid out α (inline in convert — blocks mbsync hook), β (new `zkm-ner verifier` subcommand — most ceremony), γ (extend `zkm scrub` with `--with-verifier` flag — verifier acts as additional `_is_scrub_candidate` rule).

😈 Riku: α blocks the mbsync hook with LLM latency. γ recovery story matches existing scrub: git checkout + re-run. No live-pipeline disruption.

🧠 Mira: γ keeps LLM out of hot path; convert pipeline stays deterministic; re-running verifier as prompt tunes = cheap re-scrub (no convert cache invalidation). Privacy: opt-in on scrub invocation, not every mail sync.

✂️ Petra: γ lowest-ceremony, satisfies N=2 — zkm-claude-* scrub pass can opt-in to same flag later.

🏗️ Archie concrete shape under γ: `--with-verifier` flag on `zkm scrub`; `plugins/zkm-ner/src/zkm_ner/verifier.py` module called from `scrub()._is_scrub_candidate` when flag set; verifier reads `ner_verifier` extraction cache, makes LLM call on miss; verdict propagates as candidate-removal decision; pre-flight on `_is_suspicious`-flagged values + 1–2% control sample.

Pre-emption: γ matches user's lever-first instinct (scrub is the lever) and empirical-pilot preference (observable before `--apply`).

**Item 3 decision:** γ — extend `zkm scrub` with `--with-verifier` flag; new `verifier.py` in zkm-ner plugin; verifier verdict becomes another `_is_scrub_candidate` rule. No changes to convert pipeline.

### Item 4 — Pilot protocol + success bar

🏗️ Archie: two-stage gate mirroring N9d-α. Stage 1: 5 hand-picked representative values, eyeball verdicts. Stage 2: 300–500 unique values sampled from suspicious set + control; manual 5-bucket classification on a 100-value subset.

😈 Riku: gates declared upfront —
- Gate A (proceed to `--apply`): verifier-FP-drop-of-legit ≤ 2% AND verifier-correct-drop ≥ 60%.
- Gate B (re-prompt or fallback to qwen3.6-35B): 2% < FP-drop-of-legit < 5% OR correct-drop < 60%.
- Gate C (close N9d with rationale): FP-drop-of-legit ≥ 5%.
Numbers calibrated to ~70 lost legit entities at 2%, ~185 at 5% (latter visible in user queries).

🧠 Mira: per-language accuracy reporting in pilot (DE vs EN bias on aya); record as design note even if not blocking. Pilot cost: ~2 min LLM + ~30 min eyeball.

✂️ Petra: pilot deliverable is Stage 2 results + gate decision. Out of scope: fine-tuning, ensemble, prompt-template iteration beyond first pass.

**Item 4 decision:** two-stage gate; Stage 1 = 5 hand-picked values, Stage 2 = 300–500 unique values + 100-value eyeball classification. Gates A (≤2%/≥60% → apply), B (2–5%/<60% → retry), C (≥5% → close). Per-language accuracy recorded but not blocking.

### Item 5 — N9e roadmap (schema sketch only)

🏗️ Archie: append-only JSONL at `<store>/.zkm-state/ner-verifier-denylist.jsonl`; one record per `(value, type)`: `{value, type, verdict, source, model_version, first_seen, heuristic_would, n_observations}`. `source ∈ {verifier, heuristic, manual}`; `verdict ∈ {drop, keep}`. Next scrub loads file as cheap predicate; verifier-confirmed drops become deterministic stoplist entries (no LLM call needed).

😈 Riku: override direction is non-trivial — allowlist vs denylist precedence ambiguity. Drops-becoming-sticky is symmetric to keeps-becoming-sticky in theory but conflict resolution is open. Minimum evidence to design N9e: ≥1 observed verifier-override case from Stage 2.

🧠 Mira: `model_version` per record is mandatory — same `(value, type)` may flip verdicts on model swap; append-only enables drift audit.

✂️ Petra: schema sketch only; no code in this meeting; N9e TODO stays open with sketch attached; gated on N9d shipping + ≥5 disagreement cases observed.

**Item 5 decision:** N9e schema documented (`docs/ner.md` addendum); implementation gated on (N9d shipped) AND (≥5 verifier-override cases observed in Stage 2 pilot). No code in this meeting.

## Decisions

- **Scope:** verify only values flagged by `_is_suspicious` (pilot.py) + a 1–2% random control sample of non-suspicious entities as a blind-spot tripwire. All-heuristic-passed scope deferred — promote later once verifier proven.
- **Mechanism:** Mira's two-tier shape — Tier 1 value-only prompt cached on `(value, type, model_version)` with Yes/No/Unclear output; Tier 2 context-augmented call only on `Unclear` returns (one per value's first doc), result stored as note inside the same cache entry. Doc-context-free cache key for v1.
- **Cache:** reuse `src/zkm/extraction_cache.py` with `extractor_name="ner_verifier"`; key = `sha256(value + ":" + type)` stored in the `body_sha256` field; prompt hash baked into `model_version` (`+prompt-vN`).
- **Model:** aya-expanse-8b as v1 (bilingual, already deployed on llama-swap); qwen3.6-35B-A3B-UD-Q4_K_M tracked as fallback if v1 pilot accuracy disappoints. Temperature 0; deterministic-as-possible under quantisation.
- **Integration:** γ — extend `zkm scrub` with `--with-verifier` flag; new `plugins/zkm-ner/src/zkm_ner/verifier.py` module called from `scrub()._is_scrub_candidate` when flag set; verifier verdict acts as one more candidate-removal rule alongside the existing stoplist regex matches. No changes to `zkm convert` pipeline; LLM stays out of the mbsync hot path.
- **Pilot (Stage 1):** 5 hand-picked representative values covering person-lowercase + single-token MISC + one known legit-but-suspicious control; eyeball verdicts; verify behaviour matches manual expectation.
- **Pilot (Stage 2):** 300–500 unique values sampled from the full suspicious set + control; 100-value subset manually classified into 5 buckets (`verifier-correct-drop | verifier-correct-keep | verifier-FP-drop-of-legit | verifier-FP-keep-of-FP | verifier-unclear`).
- **Success gates (declared upfront):**
  - **Gate A → proceed to `--apply`:** `verifier-FP-drop-of-legit ≤ 2%` AND `verifier-correct-drop ≥ 60%`.
  - **Gate B → retry with prompt iteration or model swap:** `2% < FP-drop-of-legit < 5%` OR `correct-drop < 60%`.
  - **Gate C → close N9d with rationale:** `FP-drop-of-legit ≥ 5%` (verifier unsafe at current local-LLM accuracy; revisit when local LLMs improve).
- **Per-language accuracy reporting** in Stage 2 (DE vs EN bias on aya). Recorded but not blocking — informs future model-swap decision.
- **N9e:** schema sketch documented (`docs/ner.md` addendum); append-only JSONL at `<store>/.zkm-state/ner-verifier-denylist.jsonl`; one record per `(value, type)` with `verdict`, `source ∈ {verifier, heuristic, manual}`, `model_version`, `first_seen`, `heuristic_would`, `n_observations`. Implementation gated on (N9d shipped) AND (≥5 verifier-override cases observed in Stage 2). Drops-becoming-sticky is the only direction designed; keeps-becoming-sticky (allowlist) deferred — precedence ambiguity unresolved.
- **Non-stationarity rider** (from warrant-check) **stays active**: re-evaluate N9d threshold + N9e schema after any non-mail amender plugin (zkm-claude-code, zkm-claude-ai, …) lands at scale.

**Out of scope for v1:**
- Own-name signature pollution (`Tobias Kienzler` ×11k) — separate TODO in zkm-eml.
- Boilerplate-legal text (Class B, deferred at N9c-6).
- Model fine-tuning, ensemble of multiple LLMs.
- Per-document re-verification (cache key MUST be doc-context-free).
- N9e keeps-becoming-sticky allowlist branch.
- Inline verifier in `zkm convert` (option α, rejected — blocks mbsync hook).
- Standalone `zkm-ner verifier` subcommand (option β, rejected — needless ceremony).

## Action items

- [ ] **N9d-1.** New module `plugins/zkm-ner/src/zkm_ner/verifier.py` (~100 LOC). Public API: `verify(value: str, type: str, *, model: str, endpoint: str, api_key: str, context: str | None = None) -> Literal["drop", "keep", "unclear"]`. Reuses httpx + llama-swap probe pattern from `src/zkm/expand.py`. Tier 1 prompt template hard-coded; Tier 2 takes `context` arg.
- [ ] **N9d-2.** Cache integration. `verifier.py` imports `from zkm.extraction_cache import ExtractionCache` with `extractor_name="ner_verifier"`. Key construction: `body_sha256 = sha256(f"{value}:{type}").hexdigest()`. `model_version = f"{model}+prompt-v1"` (bump on prompt edits).
- [ ] **N9d-3.** Scrub integration. Add `--with-verifier` flag to `zkm scrub` CLI in `src/zkm/cli.py`. Plumb flag into plugin's `scrub()` via config or kwarg. In `plugins/zkm-ner/convert.py::scrub()._is_scrub_candidate`, add branch: when flag is set AND value is `_is_suspicious`-flagged (port the predicate from `scripts/pilot.py`), call `verifier.verify(...)`; treat `"drop"` as candidate-for-removal.
- [ ] **N9d-4.** Suspicious-predicate port. Move `_is_suspicious` from `plugins/zkm-ner/scripts/pilot.py` into `plugins/zkm-ner/src/zkm_ner/suspicious.py` as a reusable module; pilot.py imports from there. ~10 LOC.
- [ ] **N9d-5.** Control sample. Implement `--with-verifier-control-pct=1.5` flag (default 1.5%) on `zkm scrub`. When set, additionally sample non-suspicious entities at that percentage and pass them through the verifier for the blind-spot tripwire. Log control-sample verdicts to stderr.
- [ ] **N9d-6.** Unit tests in `plugins/zkm-ner/tests/test_verifier.py`. Mock httpx; cover: Tier 1 yes → keep, Tier 1 no → drop, Tier 1 unclear → Tier 2 escalation, cache hit short-circuits LLM call, prompt-hash bump invalidates cache, model timeout/error returns `"unclear"` (safe-default fallback — don't drop on error). Aim ≥10 tests.
- [ ] **N9d-7.** Stage 1 smoke gate. Run verifier on 5 hand-picked values (3 known-FP from N9d-β + 1 known-legit + 1 ambiguous control). Eyeball verdicts; require ≥4/5 match expectation. Document in pilot artefact.
- [ ] **N9d-8.** Stage 2 pilot. Run `zkm scrub ner --with-verifier --dry-run` against full corpus; dump verifier verdicts to `.zkm-state/ner-verifier-pilot-<ISO8601>.jsonl`. Manually classify 100-value subset into 5 buckets; tally; apply Gate A/B/C decision.
- [ ] **N9d-9.** Per-language accuracy lens (Mira). Tag each Stage 2 verdict with detected language (langdetect on `value` or surrounding context). Compute per-language correct-drop / FP-drop-of-legit rates; record in pilot meeting note.
- [ ] **N9d-10.** Gate decision artefact. Write `docs/meeting-notes/YYYY-MM-DD-HHMM-n9d-pilot-results.md` (Class 2 planning record). Includes Stage 2 numbers, per-language table, gate verdict (A / B / C), and either: full implementation+`--apply` rollout (A), prompt-iteration follow-up plan (B), or close-N9d rationale (C).
- [ ] **N9d-11.** N9e sketch into `docs/ner.md`. Add subsection "N9e — closed-loop verifier denylist (deferred)" with schema example + gate condition. Half-page max.
- [ ] **N9d-12.** TODO.md updates: mark N9d (LLM verifier path) as in-progress; add N9d-1 through N9d-11 as sub-items; update N9e entry to reference the sketch + gate condition.
- [ ] **TODO orphan cleanup** (independent of N9d): add `docs/object-storage.md reconciliation (low priority)` to TODO.md from 2026-05-11-1506-n10-n11-docs-bundle meeting; document N9c-10 sub-item from this session's earlier Class 2 planning record.
- [ ] **meeting-style.md:** add this meeting + the N9c-10 Class 2 record to the past-meetings index.

## Verification

- Unit tests: `cd plugins/zkm-ner && uv run pytest tests/test_verifier.py -q` — all green; ≥10 tests.
- Full plugin suite: `cd plugins/zkm-ner && uv run pytest -q` — no regressions.
- Stage 1 smoke gate: eyeball 5/5 verdicts match manual expectation OR halt and rewrite prompt.
- Stage 2 numbers in pilot artefact match gate-decision criteria.
- `zkm scrub ner --with-verifier --dry-run` runs to completion with verifier-pilot JSONL written.
- N9d-pilot-results meeting note exists and references the Stage 2 artefact path.
