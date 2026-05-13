# zkm — Phase 2 TODO

See `CLAUDE.md` for architecture overview. See `docs/phase2-plan.md` for sequencing.
Completed Phase 1 tasks archived in `docs/phase1-done.md`.

## Infrastructure / cross-project

- [ ] Evaluate replacing llama-3.2-3b with Gemma 4 E4B for zkm LLM calls — `gemma4-e4b` in workload group on zomni llama-swap since 2026-05-12; benchmark text-only quality (via zelegator or ai-codebench); if Gemma ≥ llama at comparable speed, promote to always-on and retire llama-3.2-3b workload slot — cross-link: ~/src/helferli/docs/meeting-notes/2026-05-12-2036-asr-language-detection.md

## Phase 2 session 6 — hybrid search quality

- [x] Widen dense candidate pool from `top_k*3` to `max(top_k*20, 200)` — clears literal-match saturation so cross-lingual hits enter RRF fusion — covered by tests/test_query_recall.py on 2026-05-07
- [x] Add `SearchTrace` dataclass; three silent BM25-only fallbacks now set a `dense_skipped_reason`; CLI emits stderr warning on skip — covered by tests/test_query_recall.py on 2026-05-07
- [x] Add `--expand` flag to `zkm search` (opt-in LLM expansion for cross-lingual recall; `zkm query` keeps expansion default-on) — covered by tests/test_query_recall.py on 2026-05-07
- [x] New `zkm doctor` subcommand: md/bm25/embed doc counts, stale-index detection, embed + LLM endpoint probes — manually verified on real store 2026-05-07
- [x] Updated `docs/field-test-bge-m3.md`: realistic step 3 (--expand required on literal-heavy corpora), diagnostic checklist — 2026-05-07
- [x] Fix `expand.py` parser bugs: `_parse_keywords` handles inline comma/quote-separated and section-header formats; `_parse_hypothetical_text` handles `Section 2` marker without blank line and strips label prefix; bilingual prompt + `_PROMPT_HASH` cache invalidation — covered by tests/test_expand.py (20 tests) on 2026-05-07
- [x] Bilingual expand model audit — live-tested all configured models + aya-expanse-8b + Apertus-8B against the exact _EXPANSION_PROMPT; finding: aya-expanse-8b is the only local model that reliably emits EN+DE keywords for both DE and EN questions; tightened _EXPANSION_PROMPT ("3 EN then 3 DE phrases, translate into the OTHER language"), made _parse_keywords cross Section-2-marker blank lines (aya markdown format), skip **Language:** sub-headers, strip <|END_OF_TURN_TOKEN|>; added aya-expanse-8b to /etc/llama-swap/config.yaml; updated docs/field-test-bge-m3.md with live-test model table + bilingual probe — covered by tests/test_expand.py (21 tests) on 2026-05-07

## Phase 2 session 7 — aya expansion bugs (3 blockers found in live test)

- [x] **5-keyword cap kills German half**: raised cap from 5 to 12 in `_parse_keywords` — aya's 6 EN + 6 DE output now fully survives; covered by `test_parse_keywords_caps_at_twelve` and `test_parse_keywords_aya_bilingual_six_plus_six` on 2026-05-07
- [x] **`Section 1 — Search terms` leaks as keyword when no trailing colon**: made trailing colon optional in section-label regex (`^Section\s*\d+\s*[—–\-]+\s*[^:]+:?\s*`) — covered by `test_parse_keywords_section_header_no_colon` on 2026-05-07
- [x] **Stale expansion cache on model switch**: cache key now includes model name (`_PROMPT_HASH + model + question`) so switching `ZKM_LLM_EXPAND_MODEL` auto-invalidates; existing bad entries in `~/knowledge/.zkm-index/expansion-cache.json` become unreachable (different key) — covered by `test_expand_query_cache_misses_on_different_model` on 2026-05-07. One-off clear still needed for the pre-fix bad entries: `rm ~/knowledge/.zkm-index/expansion-cache.json`
- [x] **Stale cache survives parser fixes**: added `_PARSER_VERSION = "v2"` constant folded into cache key; cache file now uses `{"_parser_version": "v2", "entries": {...}}` envelope; `_load_cache` discards and rewrites the file on version mismatch — future parser changes only need to bump `_PARSER_VERSION`; covered by `test_expand_query_cache_misses_on_parser_version_bump` and `test_expand_query_legacy_cache_format_ignored` on 2026-05-07

## Query quality (post-MVP backlog)

- [x] **Field-test on real store** — all 5 steps passed on 55125-doc store: hybrid beats BM25-only for DE queries (1→5 hits for "Stromrechnung"), DE→EN cross-lingual 43/50 ✓, EN→DE 1/50 (corpus is ~95% DE), semantic steps 4+5 work; one finding filed below — verified by user on 2026-05-07
- [x] **Rigorous cross-lingual anchors in field test** — replaced grep-count approach with disjoint-vocabulary pairs (O2 bills DE-only, Google Cloud/Cloudflare/AWS invoices EN-only); baselines exactly 0, --expand yields 11 EN and 3 DE hits; documented that shared proper-noun pairs (Hotel Katharinenhof) contaminate the test — verified live on 2026-05-07
- [x] **LLM conflates generic "Rechnung" docs with "Stromrechnung"** — confirmed corpus gap: no electricity utility bills in store (only one electricity-meter email from 2012); this is expected behaviour, not a retrieval bug; updated field-test step 5 queries to use O2/hotel which have real corpus coverage — confirmed 2026-05-07
- [x] Separate expansion model from answer model — `ZKM_LLM_EXPAND_MODEL` / `ZKM_LLM_EXPAND_ENDPOINT` / `ZKM_LLM_EXPAND_KEY`; `_resolve_expand_config` falls back to main LLM config; `zkm doctor` shows expand endpoint when it differs — covered by tests (203 zkm tests passing) on 2026-05-07
- [x] Surface expansion terms to the user (`zkm query --show-expansion`) for transparency and debugging — `--show-expansion` flag on both `zkm search` and `zkm query`; keywords + hyp_text plumbed through `SearchTrace`; 3 new tests (206 passing) — 2026-05-07
- [x] **Expansion timeout on cold model** — `_probe_model_loaded` checks llama-swap `/running` before the POST; if cold, timeout extends from 30s → 180s (configurable `ZKM_LLM_EXPAND_COLD_TIMEOUT`) with a stderr notice; expansion failure now returns typed reason (`"timeout" | "endpoint_error" | "parse_error"`); `zkm query` and `zkm search --expand` exit 2 on failure by default; `--allow-fallback` opts into silent BM25 fallback; `zkm doctor` always shows expand model load state — covered by 13 new tests (225 zkm tests passing) on 2026-05-07
- [x] **LLM hallucinates when corpus lacks the queried document type** — fixed via (c) + (a): system prompt now instructs the LLM to judge relevance first and say so when sources are off-topic; `zkm query` emits a stderr "top-hit relevance is low" warning when `hits[0].score` is below a per-backend floor (`ZKM_QUERY_LOW_BM25_THRESHOLD=1.0`, `ZKM_QUERY_LOW_DENSE_THRESHOLD=0.5`); field-test step 5b live-verified: "Stromrechnung" probe correctly refused (named O2 bills / meter-reading email, no invented figure); counter-test "O2 Herbst 2014" answered 14,98 EUR with citations — covered by `test_llm_stream_system_prompt_instructs_relevance_check` and `test_zkm_query_warns_on_low_relevance_score` (228 tests passing); live-tested on 55125-doc store on 2026-05-07
- [x] **`zkm query` sources list is unordered** — numbered Sources block `[1] path…` matches LLM's inline `[N]` citations; system prompt updated to request `[N]` style consistently — covered by tests/test_query_recall.py on 2026-05-07
- [x] Doc chunking (any long .md, not just emails/threads) — see `docs/meeting-notes/2026-05-08-doc-chunking.md`; decision: core feature, embed-side char-window chunker, file-level RRF — covered by session 8 (259 tests passing) on 2026-05-08

## Phase 2.5 — next plugins (decided 2026-05-08-next-plugins.md, 2026-05-08-information-flow.md)

Order: pre-flight specs → zkm.amendments lib → photo → pdf → scan → notmuch → (scoping) → whatsapp.
WhatsApp requires three core additions before its own session; see session 15.

Pre-flight sessions (9a–9d) must land before any plugin session starts.

- [x] Session 9a (pre-flight): add "MUST be no-op on unowned inbox items" rule to `docs/plugin-spec.md` (~1 paragraph); contract: plugin run against foreign-only inbox returns `[]` exit 0 — covered by docs updates on 2026-05-08
- [x] Session 9b (pre-flight): add paragraph to `docs/object-storage.md` confirming multi-producer-plugin sidecars are normal (e.g. photo + scan against same CAS object) — covered by docs updates on 2026-05-08
- [x] Session 9c (pre-flight): write the amendment contract section in `docs/plugin-spec.md`. Per-field merge rules: `tags` set-union; `entities` set-union with role-tagged dedup; scalars last-write-wins-with-`emitted_by`-attribution; structured lists need explicit merge keys. Amendment record schema: `{key: {message_id|sha256|path: ...}, fields: {...}, emitted_by: <plugin-name>, emitted_at: <iso8601>}`. Round-trip test: zkm-eml writes md with `tags:[]`; amendment with `tags:[bill]` lands; merged md shows `tags:[bill]` with attribution sidecar entry — covered by docs updates on 2026-05-08
- [x] Session 9d (pre-flight): design note for extraction-cache in `docs/object-storage.md`. Cache shape (per-CAS-object, multi-stage, per-extractor), planned merge with `producers[]` sidecar. **No implementation** — deferred until first content-plugin (zkm-receipt) lands in Phase 3 and N=2 evidence is concrete — covered by docs updates on 2026-05-08
- [x] Session 10 (core lib): `src/zkm/amendments.py` — read amendment records, key-resolve against md tree by `message_id`/`sha256`/path, merge per field rules, write back, track attribution sidecar. ~200 LOC + tests. Must land before session 14 — covered by tests/test_amendments.py (26 tests, 285 total) on 2026-05-08
- [x] Session 11: `zkm-photo` repo (`~/src/zkm-photo/`) — EXIF date→`date`; EXIF GPS→`location` decimal degrees (no reverse-geocode); camera model→`camera` scalar; sha256+CAS dedup; markdown image link in body. Uses only `zkm.atomic|cas|sidecar|inbox|hashing`. `creates_dirs: [photos, originals/photos]`. Idempotent (second run → 0 new files). 11 tests passing (incl. multi-producer sidecar cross-plugin test) — 2026-05-08. Note: `camera` goes to `camera:` scalar (not `tags:[]`) to preserve the amendment placeholder contract; `tags:[]` is left empty for future amenders.
- [x] Session 12: `zkm-pdf` (text-only) — emit md when text extraction ≥ N chars; silently skip scanned-only PDFs (leaves them for zkm-scan); test confirms skip. `PDF_MIN_TEXT_CHARS=100` default (flagged as provisional heuristic; to revisit at Session 13 design with `.zkm-state/zkm-pdf-skipped.jsonl` data). Two input paths: inbox/ PDFs (from zkm-eml, reuses existing CAS) + optional `PDF_SOURCE_DIR`. 12 tests passing — 2026-05-08
- [x] Session 13: `zkm-scan` (OCR, tesseract) — per-doc md; `progress` reporter; cancellable per plugin-spec cancellation contract. Processes images (JPEG, PNG, TIFF, BMP, GIF, WEBP) and scanned PDFs via pytesseract + pdf2image; SCAN_SOURCE_DIR + inbox fan-out; owned-by check for eml/photo/scan; per-doc md in scans/; sha256 dedup; SCAN_LANG + SCAN_MIN_TEXT_CHARS config knobs. 13 tests passing — 2026-05-08
- [x] Session 14: `zkm-notmuch` plugin (`plugins/zkm-notmuch/`) — first amender. Reads tags via `notmuch dump --format=batch-tag` (subprocess; no Python binding required). Normalises message IDs to `<id>` form to match zkm-eml `raw_message_id` frontmatter. Emits amendment records via `zkm.amendments` (set-union merge into `tags`). Applies queue immediately; pending records left for re-run after `zkm-eml`. `NOTMUCH_CONFIG` and `NOTMUCH_TAGS_EXCLUDE` config knobs. 16 tests passing — 2026-05-08
## Phase 2.5 — NER (decided 2026-05-10-1148-entity-extraction.md)

NER lands before whatsapp. `zkm convert <plugin>` runs amenders default-on (`--no-amenders` to skip). Session 9d extraction-cache transitions from design-only to implementation alongside zkm-ner.

- [x] **N1.** New plugin repo `plugins/zkm-ner/` (mirrors zkm-notmuch layout). `plugin.yaml`: `kind: amender`, `creates_dirs: []`. `pyproject.toml` `version = "0.1.0"`, `requires zkm>=0.2.0,<0.3.0`. Contract: `convert(store, config) -> []`; emits amendment records via `zkm.amendments`. Tagged v0.1.0, pushed to fievel — 2026-05-10.
- [x] **N2.** Extractor pipeline `plugins/zkm-ner/src/zkm_ner/extract.py`: `extract(body, lang) -> list[Entity]`. Pattern overlay first (email, phone/CH, url, domain→org_hint, social_handle.{discord,telegram,steam,...}, linkedin_profile, github_profile, org_gazetteer). spaCy NER second (de+en small models, doc-level langdetect routing). Patterns win on overlap. GLiNER backend behind `zkm-ner[gliner]` optional extra + `ZKM_NER_MODEL=gliner`. 30 tests passing — 2026-05-10.
- [x] **N3.** Extraction-cache core lib `src/zkm/extraction_cache.py`. Per-store at `<store>/.zkm-state/extraction-cache/`. Key: `(sha256_of_body, extractor_name, model_name, model_version)`. Atomic write, schema version. Cache hit short-circuits extractor. 15 tests (hit/miss/version-bump/corruption/extractor isolation) — 330 tests passing, 2026-05-10.
- [x] **N4.** zkm-ner amendment writer `plugins/zkm-ner/convert.py`. Per-doc: check cache → run extractor on miss → `zkm.amendments.emit({entities: [...]}, emitted_by="ner")` → `apply_queue`. Set-union dedup on `(type, value)`. Re-run → 0 new amendments on warm cache. Fixed: `amendments.py` entity dedup key updated from `(name, role)` to `(type, value)`; `convert.py` body sha256 now hashes body content only (not whole file). 6 tests (test_convert.py) — 36 zkm-ner + 330 core tests passing — 2026-05-10.
- [x] **N5.** Default-on amender chain in `src/zkm/convert.py:cmd_convert`. `--no-amenders` flag opts out. Discovers amender plugins via `kind: amender` in `plugin.yaml`. `Plugin.kind` field + `list_amenders()` in `convert.py`. Commit fires after amenders run (covers amendment writes). 6 new tests (336 total) — 2026-05-10.
- [x] **N6.** Verify mbsync hook (`plugins/zkm-eml/hooks/post-commit`) inherits default-on — no change needed; confirm in journald that zkm-ner runs after convert. Verified: 29855 mail/messages/*.md have `entities:` frontmatter; knowledge store clean — 2026-05-10.
- [x] **N7.** Pattern overlay tests: email, phone (DE/CH formats), URL, domain→org_hint, all social handle subtypes, linkedin_profile, github_profile, gazetteer canonicalisation. 20 cases in `plugins/zkm-ner/tests/test_patterns.py` — covered by N2 session, 2026-05-10.
- [x] **N8.** spaCy backend tests: German fixture, English fixture, mixed-language fallback (accept doc-level routing limitation). `plugins/zkm-ner/tests/test_spacy_backend.py` — covered by N2 session, 2026-05-10.
- [x] **N9.** Pilot script `plugins/zkm-ner/scripts/pilot.sh` + `scripts/pilot.py`: histogram (760k mentions, 13 types), top-N per type, suspicious-value dump (138k flagged); review file at `<store>/.zkm-state/ner-pilot-review.jsonl`. Key finding: "Subject"/"Thread"/"Re"/"Betreff" top person list — email header artifacts. Two-week pilot window starts 2026-05-10.
- [x] **N9a.** (pilot finding) Entity value normalization: strip leading/trailing whitespace and newlines from `value` strings before storing — pilot surfaced values like `'…\n \n'` and `'sam\n\n'` in the person list. Fixed via `Entity.__post_init__` in `_types.py` (covers all extractors); 3 regression tests added — 39 zkm-ner + 336 core tests passing 2026-05-10.
- [x] **N9b.** (pilot finding) Email-header stoplist + markdown-syntax pre-strip. Design decided 2026-05-10 (see `docs/meeting-notes/2026-05-10-1640-n9b-email-header-stoplist.md`). Scope: 3 pollution classes (markdown-syntax fragments, header column names, subject-line prefixes). Two-stage fix in new `plugins/zkm-ner/src/zkm_ner/textfilter.py`.
  - [x] N9b-1. `textfilter.py` — `strip_markdown_artefacts` + `_STOPLIST` (14 words) + `drop_stoplist` — covered by tests/test_textfilter.py (58 zkm-ner tests passing) 2026-05-10.
  - [x] N9b-2. Wire into `extract.py` (pre-strip body; post-filter before dedup) — covered by tests/test_textfilter.py 2026-05-10.
  - [x] N9b-3. Bump `model_version` in `version.py` (`+textfilter-v1`) to force extraction-cache rebuild — covered by tests/test_textfilter.py 2026-05-10.
  - [x] N9b-4. 19 tests in `tests/test_textfilter.py` (separator rows, pure-pipe, data-row preservation, all 14 stoplist words parametrised, case-insensitive, no-substring FP) — 58 zkm-ner + 336 core tests passing 2026-05-10.
  - [x] N9b-5. Run `zkm convert zkm-ner`, re-run `scripts/pilot.sh`, compare top-N before/after, document delta. Prerequisite for N9c — confirms classes 1–3 are clean before tackling class 4. **Delta:** textfilter-v1 blocked new stoplist emissions but set-union merge preserved 52,334 historical dirty entities. `zkm scrub ner --apply` (new core CLI) removed them. Before: Subject ×16k, Thread ×12k, Re ×2.9k, Betreff ×2k at top of person list. After: Tobias Kienzler ×11k leads; Subject/Thread/Re/Betreff absent. Total mentions: 771,831 → 719,504. Classes 2+3 confirmed clean — 2026-05-10.
- [x] **N9c.** spaCy common-noun false-positive gating. — all sub-items N9c-1 through N9c-9 done 2026-05-11. Design decided 2026-05-11 (see `docs/meeting-notes/2026-05-11-0946-ner-next-after-n9b.md`). Mechanism: hybrid POS-filter (`ent.root.pos_ == "PROPN"`) + `_COMMONNOUN_STOPLIST` for PROPN-tagged abbreviations. Applied to all spaCy NER types; pattern-overlay entities bypass.
  - [x] **N9c-1.** `_pos_filter(ent)` in `plugins/zkm-ner/src/zkm_ner/extract.py` — applied after `nlp(text)`, before pattern merge. 6 tests in `plugins/zkm-ner/tests/test_pos_filter.py` — covered by 86 zkm-ner tests passing 2026-05-11.
  - [x] **N9c-2.** `_COMMONNOUN_STOPLIST` = {Du, wünschen, Zeit, EUR, CHF, UTC, MESZ, CEST, Internet, CV, AGB, HRB} + `drop_commonnoun_stoplist` in `plugins/zkm-ner/src/zkm_ner/textfilter.py`. Parametrised tests added to `tests/test_textfilter.py` — covered by 86 zkm-ner tests passing 2026-05-11.
  - [x] **N9c-3.** Bump `model_version` in `plugins/zkm-ner/src/zkm_ner/version.py` to `+textfilter-v1+posfilter-v1` for cache invalidation — 2026-05-11.
  - [x] **N9c-4.** Extend zkm-ner `scrub()` in `plugins/zkm-ner/convert.py` — `_COMMONNOUN_STOPLIST` predicate (cheap) + isolated-POS-tag predicate (principled, German model, single-word only). 3 tests in `plugins/zkm-ner/tests/test_scrub.py` — covered by 86 zkm-ner tests passing 2026-05-11.
  - [x] **N9c-5.** Run `zkm convert ner` (cache bust) then `zkm scrub ner --apply`. Commit — 2026-05-11. Two passes: (1) pre-N9c convert (old code, ran before session) + N9c scrub = 249,911 entities removed across 47,271 files; (2) N9c convert (in-pipeline POS filter) + scrub = 16 entities removed across 4 files. Stable.
  - [x] **N9c-6.** Re-run `plugins/zkm-ner/scripts/pilot.sh`; compare person/org top-N; target <5% legit-ORG loss vs post-N9b baseline. Document delta here — 2026-05-11.
    **Final state (post two convert+scrub cycles):** 471,894 total mentions (-34.4% vs 719,504 post-N9b). Legit-ORG target MET: Google LLC ×3204, PayPal ×1892, Amazon WS ×1074, SBB ×542, ETH ×485 all intact. Person top is now Tobias Kienzler ×11,270. Second cycle stable (+18 net entities only).
    **Remaining FP classes found:**
    - *Class 5 (pipe cell artifacts):* `'| |'` ×2664, `'| | |'` ×679, `'|  |'` ×373 — inline empty table cells within data rows; N9b only strips full pure-pipe rows. Fix: post-extraction value filter rejecting `^[\s|]+$`. See N9c backlog below.
    - *English-noun limitation in isolated POS:* `'Learn'` ×1032, `'Link'` ×679, `'Actions'` ×430, `'Download'` ×357 — German model tags these PROPN/X (foreign word), passes isolated POS. Fix: try EN model when DE model returns PROPN for a foreign-looking value.
    - *Multi-word phrase FPs (N9d territory):* `'Hallo Tobias'` ×1930, `'Best Regards'` ×1139, `'Guten Tag Herr Kienzler'` ×444, `'Hello Tobias'` ×392 — bypass multi-word skip in isolated POS; need LLM verifier or phrase-pattern blocklist.
    - *Boilerplate legal text in ORG:* `'L-2449 Luxembourg RCS Luxembourg'` ×859, `'S.C.A. Société en commandite par actions'` ×854 — legitimate entity names but high-frequency boilerplate; defer.
    **Note:** this convert ran with pre-N9c code; in-pipeline POS filter not yet applied. A fresh `zkm convert ner` will bust cache (new version key) and re-extract with POS filter, which will prevent new FPs — required before calling N9c fully clean.
  - [x] **N9c-7.** Add N9d + N9e backlog entries to TODO.md (this item) — already present from previous session 2026-05-11.
- [x] **N9c-8.** Pipe-cell artifact filter — `drop_structural_artefacts()` in `textfilter.py` (`^[\s|]+$`); wired into `extract.py` post-filter chain; `textfilter-v1` → `textfilter-v2` cache invalidation; `scrub()` extended; 9 new tests (95 total). `zkm scrub ner --apply` removed 3938 entities across 2843 files. **Post-scrub pilot: 467,956 total mentions** (was 471,894 post-N9c). `| |`/`| | |`/`|  |` gone from top-N. Remaining: `| €` ×317 (partial cell with real content, not pure-pipe — deferred) — 2026-05-11.
- [x] **N9c-9 (backlog).** Bilingual isolated-POS in scrub — `_isolated_pos` now checks `en_core_web_sm` when DE returns PROPN/X; catches 'Learn' (VERB, ×1032) and 'Link' (NOUN, ×679); 'Actions'/'Download' remain PROPN in EN — accepted limitation. zkm-ner bumped 0.2.0→0.3.0, tagged v0.3.0 — covered by `test_scrub_bilingual_pos_drops_english_common_words` (96 tests) 2026-05-11.
- [x] **N9c-10.** Section-N] markdown link-target artifact filter — Class 7 pollution: `Section N]` fragments (broken `[Section 5](url)` → `Section 5]` when opening bracket is lost by zkm-eml). `_RE_SECTION_LINK_ARTIFACT = re.compile(r"^Section\s+\d+\]")` + `drop_section_link_artefacts()` in `textfilter.py`; wired into `extract.py` post-filter chain; `scrub()` extended; `textfilter-v4` → `textfilter-v5` cache key bump; 8 new tests (124 total). zkm-ner bumped 0.4.1→0.5.0, tagged v0.5.0. `zkm scrub ner --apply` expected to remove ≈936 entities. Re-run pilot to confirm `Section N]` absent from top-N. Root cause (zkm-eml broken link parser) deferred — would require 55k-mail re-render. See `docs/meeting-notes/2026-05-11-2316-n9c-10-section-link-artifact.md` — 2026-05-12.
- [x] **N9d-α.** GLiNER A/B — two-stage smoke-gate protocol (decided 2026-05-11-1531-ner-tangible-results.md). Measurement only; never touches frontmatter. — FAIL verdict (N9d-α-5); all sub-items done 2026-05-11.
  - [x] **N9d-α-1.** Patch `pilot.py` (~10 LOC) to dump top-30 multi-word (≥2-token) PERSON values; run once to capture salutation closed set — done 2026-05-11.
  - [x] **N9d-α-2.** Pre-flight: verify `zkm-ner[gliner]` installed; `uv sync --extra gliner` if not — done 2026-05-11.
  - [x] **N9d-α-3.** `plugins/zkm-ner/scripts/gliner_ab.py` (~50 LOC): file list → both backends → delta JSONL at `.zkm-state/gliner-ab-<ISO8601>.jsonl`. No amendments — done 2026-05-11.
  - [x] **N9d-α-4.** Smoke gate: 5-file run (one per top-4 FP + control); verify each FP dropped by GLiNER. **Finding:** 0 FP hits from both backends — but N9f was already implemented before the gate ran, so both pipelines apply `drop_salutation_blocklist`. Original moot question unanswerable from this test. Gate technically passes (0 FP hits from GLiNER). Gate reformulated for Stage 2 as broader quality comparison — 2026-05-11.
  - [x] **N9d-α-5.** Stage 2 (reformulated): 25-file targeted sample (FP-prone job-application emails + legit-entity files) + 30-file short-email-only run. **Key finding:** spaCy=364 vs GLiNER=261 on mixed (−28%), but spaCy=143 vs GLiNER=164 on short emails (<3KB, +14%). The apparent precision advantage on long emails is a truncation artifact — GLiNER model `urchade/gliner_multi-v2.1` truncates at 384 tokens (~2800 chars). On short emails both backends have comparable FP rates; GLiNER introduces different FP types (crypto addresses, role nouns). **Verdict: FAIL — GLiNER not suitable as default backend for mixed-length email stores.** Truncation note added to `plugin.yaml` + `gliner_backend.py` docstring — 2026-05-11.
- [ ] **N9e (backlog — no live trigger path).** Closed-loop verifier denylist — append-only JSONL at `<store>/.zkm-state/ner-verifier-denylist.jsonl`; one record per `(value, type)`: `{value, type, verdict, source, model_version, first_seen, heuristic_would, n_observations}`. `source ∈ {verifier, heuristic, manual}`; `verdict ∈ {drop, keep}` (drops-only direction designed; keeps-becoming-sticky deferred — precedence ambiguity). **Gate: (N9d shipped) AND (≥5 verifier-override cases observed in Stage 2 pilot).** **Status 2026-05-12: gate cannot fire — N9d closed via Gate C; verifier did not ship.** Entry remains in backlog for archival reference; no implementation path until/unless a successor verifier project replaces the gate condition. Conflict-resolution for allow+deny overlap unresolved — design meeting required if revived.
- [x] **N9f.** Salutation phrase blocklist — Class 6 pollution (multi-word greeting/sign-off FPs). zkm-ner v0.4.0→0.4.1. Scrub: 153730 entities removed across 36723 files (two passes: textfilter-v3 + textfilter-v4 for 3 missed variants). **Post-scrub pilot: 340,431 total mentions** (was 467,956 post-N9c-8 = **-127,525, -27.3%**). Salutation phrases gone from top-N; top-20 now leads with legitimate entities (`Tobias Kienzler` ×11279 = own-name/signature, Class C deferred) — 2026-05-11.
- [x] **N9d (CLOSED — Gate C fired 2026-05-12).** LLM verifier on residuals (aya-expanse-8b). Stage 2 pilot (n=100 mixed DROP+KEEP) returned **FP-drop = 20%** (4× the 5% close-out threshold) and **FN-keep = 37.5%** — both ends of the confusion matrix broken. Per-`suspicious_reason` breakdown shows category-correlated failure: 1-char and single-token-MISC drops at 0% FP, but person-lowercase (the original motivating class) at 50% FP and 2-char at 31% FP. **N9d-as-designed is closed.** Gate decision artefact: `docs/meeting-notes/2026-05-12-1242-n9d-gate-c.md` (covers N9d-10). N9d-9 (per-language lens) and N9d-11 / N9d-12 not pursued (gate closure pre-empts). Design history: `docs/meeting-notes/2026-05-11-2316-n9d-llm-verifier-design.md`; trigger spec: `docs/meeting-notes/2026-05-11-2218-n9d-n9e-warrant-check.md`.
  - [x] **N9d-β-1.** Patch `plugins/zkm-ner/scripts/pilot.py` (or `pilot.sh`) so review JSONL output path is timestamped (`ner-pilot-review-YYYYMMDD-HHMM.jsonl`); no overwrite of prior runs. Single-line change; verify by running pilot twice — done 2026-05-11.
  - [x] **N9d-β-2.** Run `plugins/zkm-ner/scripts/pilot.sh` against current 340k-mention store; capture artefact path — done 2026-05-11 (two runs: `ner-pilot-review-20260511-2305.jsonl` + `ner-pilot-review-20260511-2309.jsonl`).
  - [x] **N9d-β-3.** Eyeball top-50 per type; manually classify each into 5 buckets: `legit | own-name | boilerplate-legal | closed-set-FP | open-set-FP`; tally per-bucket volume — done 2026-05-11. Key finding: open-set-FP confirmed (person-lowercase German fragments ~3,847 occurrences = 1.1%; single-token MISC 10,932 suspicious = 3.2%). New closed-set class found: `Section N]` markdown link-target artifacts in misc (~571 occurrences).
  - [x] **N9d-β-4.** Apply trigger: **TRIGGER FIRED** — open-set FP class (person lowercase + single-token MISC) exists AND person-lowercase alone ≥0.5% of corpus (1.1%). N9d design meeting required; see `docs/meeting-notes/2026-05-11-2218-n9d-n9e-warrant-check.md` for trigger spec. New Section-N] artifact class to be addressed before or alongside N9d design — 2026-05-11.
  - [x] **N9d-1.** New module `plugins/zkm-ner/src/zkm_ner/verifier.py` (~100 LOC). Public API: `verify(value: str, type: str, *, model: str, endpoint: str, api_key: str, context: str | None = None) -> Literal["drop", "keep", "unclear"]`. Reuses httpx + llama-swap probe pattern from `src/zkm/expand.py`. Tier 1 prompt template hard-coded; Tier 2 takes `context` arg. Prompt hash baked into `_MODEL_VERSION_SUFFIX` for auto-invalidation — 2026-05-12.
  - [x] **N9d-2.** Cache integration. `verifier.py` imports `from zkm.extraction_cache import ExtractionCache` with `extractor_name="ner_verifier"`. Key construction: `body_sha256 = sha256(f"{value}:{type}").hexdigest()`. `model_version = f"prompt-v1+{_PROMPT_HASH}"` (auto-bumps on prompt edits via hash) — 2026-05-12.
  - [x] **N9d-3.** Scrub integration. `--with-verifier` flag on `zkm scrub` CLI (`src/zkm/cli.py`); `**extra_kwargs` forwarded via `src/zkm/scrub.py` to plugins with `**_ignored` in signature; `plugins/zkm-ner/convert.py::scrub()` extended with `with_verifier` param. Suspicious entities not caught by heuristics are sent to the verifier; "drop" → removed. `entities_dropped_by_verifier` in stats — 2026-05-12.
  - [x] **N9d-4.** Suspicious-predicate port. `_is_suspicious` moved to `plugins/zkm-ner/src/zkm_ner/suspicious.py` as `is_suspicious`; `pilot.py` imports from there — 2026-05-12.
  - [x] **N9d-5.** Control sample. `--with-verifier-control-pct=1.5` flag on `zkm scrub`. Per-file probabilistic sampling of non-suspicious entities; non-"keep" verdicts logged to stderr as CONTROL-SAMPLE ALERT; `control_sampled` + `control_alerts` in stats — 2026-05-12.
  - [x] **N9d-6.** 16 tests in `plugins/zkm-ner/tests/test_verifier.py`. Mock httpx; covers Tier 1 yes/no/unclear, Tier 2 escalation (YES/NO/UNCLEAR), cache hit short-circuit, timeout/error → "unclear", case-insensitive parsing, malformed response, independent cache keys, prompt-version format — 140 zkm-ner + 343 core tests passing — 2026-05-12.
  - [x] **N9d-7.** Stage 1 smoke gate. Run verifier on 5 hand-picked values (3 known-FP + 1 known-legit + 1 ambiguous control); require ≥4/5 match manual expectation. **5/5 PASS** (aya-expanse-8b, 2026-05-12). Bug found and fixed: `_parse_verdict` did not strip aya's `<|END_OF_TURN_TOKEN|>` suffix — all verdicts were returning "unclear". Fixed by adding `_CONTROL_TOKEN_RE` strip in `verifier.py`; 1 new test added (141 zkm-ner tests passing). Gate values: `'| €'` [person]→drop ✓, `'klicken Sie'` [person]→drop ✓, `'bin ich'` [person]→drop ✓, `'SBB CFF FFS'` [org]→keep ✓, `'IBAN'` [org]→drop (ambiguous, any ok) ✓.
  - [x] **N9d-8.** Stage 2 pilot — done 2026-05-12. `zkm scrub ner --with-verifier --dry-run` against full store; 100-value stratified DROP+KEEP subset hand-classified via `scripts/gate_classify.py` (4 entity-describing buckets + comments). **Gate C fired** (FP-drop=20%, FN-keep=37.5%). See gate artefact `docs/meeting-notes/2026-05-12-1242-n9d-gate-c.md` for per-`suspicious_reason` breakdown.
  - [~] **N9d-9.** Per-language accuracy lens — **not pursued** (gate closure pre-empts; reopen only if N9d is revived under a different model).
  - [x] **N9d-10.** Gate decision artefact — `docs/meeting-notes/2026-05-12-1242-n9d-gate-c.md` written 2026-05-12. Verdict: Gate C → close.
  - [~] **N9d-11.** N9e sketch into `docs/ner.md` — **not pursued** (N9e gate condition is moot; see N9e backlog entry).
  - [x] **N9d-12.** TODO.md updates — this commit (N9d marked closed; N9e backlog entry annotated "no live trigger path"; signature-block promoted to N9g-pre; N9g blocked on entity-vs-data meeting; methodology rider added).
- [x] **N10.** Docs: new `docs/ner.md` (pattern categories, amender-not-producer rationale, cache shape, scope boundary, name-is-not-UID assertion). Update `docs/entity-model.md` Phase 2.5 section + PII design note. Update `CLAUDE.md` Phase 2.5 sequencing — 2026-05-11.
- [x] **N11.** PII redaction: one-paragraph design note in `docs/entity-model.md` (config-driven entity-type denylist for export, deferred until first sharing scenario) — 2026-05-11.
- [x] **N13.** Update `docs/meeting-notes/meeting-style.md` "Past meetings" index — already done (entity-extraction entry present).
- [x] **CLAUDE.md cleanup**: drop `(currently X.Y.Z)` version literals from polyrepo table; add `zkm-ner` to repo list; update Phase 2 sequencing (NER landed in Phase 2.5, not Phase 3) — 2026-05-11 (orphan from 2026-05-11-0946 meeting, tracked here retroactively).

**Scope constraints (from meeting):**
- `value:` strings are *mention strings*, never UIDs. No `id:`, `same_as:`, cross-doc clustering.
- Name alone is NOT a UID — manual-merge tooling deferred to Phase 4.
- Co-reference within doc deferred to v2; intra-doc pronoun coref not in scope.
- GLiNER is opt-in only; sentence-level language routing out of scope.

- [x] **Meeting: NER scope vs. data-mining vs. search index** — held 2026-05-12. γ schema adopted: typed-slot list-of-records `entities[{scope,type,value,canonical?,standard?,unit?,valid?}]`. See `docs/meeting-notes/2026-05-12-1500-entity-vs-datamining.md`. E1–E14 action items below.
- [x] **E14.** TODO.md updates — meeting item resolved [x] above; E1–E13 promoted into Phase 2.5/3 sequencing; N9g-pre and N9g blocked annotations updated. (Orphan from 2026-05-12 meeting — tracked retroactively 2026-05-12.)

## Phase 2.5 — γ schema rollout (decided 2026-05-12-1500-entity-vs-datamining.md)

Sequencing: E1+E2+E3 (schema + amendments + normaliser lib) → E4 (suspicious dispatch) → E6 (`amount` pilot) → E7 (more value-types) → E8+E9 (P2 index integration + field-test). Each step rollback-able. ~6–8 sessions total.

- [x] **E1.** `plugins/zkm-ner/src/zkm_ner/_types.py` — `Entity` dataclass gains `scope: str = "body"`, `canonical: str | None = None`, `standard: str | None = None`, `unit: str | None = None`, `valid: bool = True`. Update `__post_init__` (canonical/value-must-differ guard). `as_dict()` emits `scope` always; optional fields only when set; `valid` only when False. 13 new tests (154 zkm-ner + 350 core passing) — 2026-05-12. zkm-ner bumped 0.7.0→0.8.0, tagged v0.8.0.
- [x] **E2.** `src/zkm/amendments.py` — dedup key for `entities[]` extends from `(type, value)` to `(scope, type, value)`. Graceful read: missing scope = `body`. 3 new tests (scope-included dedup, graceful read of pre-γ entries, cross-scope coexistence) — 2026-05-12.
- [x] **E3.** `src/zkm/canonical.py` (new) — `iban(s)->str`, `amount(s)->tuple[str,str]`, `email(s)->str` (domain lowercase), `phone(s)->str` (E.164 basic), `iso8601(s)->str`. Docstrings name the standard. 29 tests — 382 core passing, 2026-05-12. Shared by extractors AND planned redactor.
- [x] **E4.** `plugins/zkm-ner/src/zkm_ner/suspicious.py` — `_PREDICATES[type]` dispatch table; existing rules wrapped in `_name_predicate` (default fallback); stub predicates for future value types (iban, amount, invoice_id, tracking_id, registration_code); `social_handle.*` prefix short-circuit. 22 new tests in `tests/test_suspicious.py` — 176 zkm-ner passing 2026-05-12.
- [x] **E5.** `plugins/zkm-ner/scripts/verify_gamma_migration.py` (new) — re-extract corpus sample from scratch, diff against graceful-read migration result. Hard-gate for v1.x release. Gates: γ-collision=0, schema-errors=0 (agreement rate informational). 14 tests in `tests/test_verify_gamma_migration.py` — 190 zkm-ner + 382 core passing 2026-05-12.
- [x] **E6.** `amount` extractor end-to-end pilot — `extract_amounts` in `plugins/zkm-ner/src/zkm_ner/patterns.py`; DE/CH/EN regex with negative lookahead for Swiss `.-` suffix; canonical via `zkm.canonical.amount`; Entity fields type/value/canonical/unit/standard. 16 tests in `test_extract_amounts.py` — 206 zkm-ner passing; `zkm convert ner` verified on fixture. zkm-ner v0.9.0 — 2026-05-12.
- [x] **E7.** Second-round value-type extractors: ~~`iban`~~ ✓ (ISO 13616 + mod-97 checksum — 16 tests, v0.10.0), ~~`email`~~ ✓ (RFC 5321, v0.11.0), ~~`phone`~~ ✓ (raw value preserved; canonical=E.164; standard="E.164"; libphonenumber), ~~`url`~~ ✓ (standard="rfc3986" added), ~~`invoice_id`~~ ✓ (keyword-anchored regex), ~~`tracking_id`~~ ✓ (UPS 1Z…, DHL JD…, Swiss Post 99…), ~~`registration_code`~~ ✓ (HRB/HRA, ISBN-13, DIN, EAN-13 keyword). 20 new tests — 245 zkm-ner + 382 core passing. zkm-ner v0.12.0 — 2026-05-12.
- [x] **E8.** P2 index integration — `src/zkm/index.py:_tokenize_doc` and `src/zkm/embed.py:_chunk_texts` gain entity values + canonicals + participant addresses/names. `_PICKLE_VERSION` bumped to 3; `_STORE_SCHEMA_VERSION` bumped to 3 (forces rebuild). 8 new tests — 390 core tests passing — 2026-05-12.
- [x] **E9.** P2 field-test pilot — step 7 written + live results filled in `docs/field-test-bge-m3.md`. Bug found: `index.py:78` stored participant address as a raw string token instead of tokenizing it — query tokens never matched. Fixed: `tokenize(address)` on both sides; `_PICKLE_VERSION` 3→4; test updated; index rebuilt (219 MB, +12.6%). Participant search confirmed working (rank 20 for participants[]-only address). 7c deferred: `entities[]` not yet populated with amounts/IBANs in corpus — re-test after next `zkm convert ner` — 2026-05-12.
- [x] **E10.** Redactor scope expansion — design note in `docs/entity-model.md` PII section: redactor operates on BM25/dense input stream too; `zkm.canonical.<type>` is the integration point — 2026-05-12.
- [x] **E11.** Docs contract tables — `docs/entity-model.md`: (a) valid types table (`type`, canonical yes/no, `standard:` value, expected `scope:` values, PII sensitivity); (b) provenance scopes table (per-plugin, `plugin.yaml`-declared, open-vocabulary). Update `docs/ner.md` with per-type extractor contract — 2026-05-12.
- [x] **E12.** N9g-pre under γ — signature + salutation block extraction emitting `scope: signature/salutation` typed entries. Sequenced after E1+E2+E3. Owner: `plugins/zkm-eml/src/zkm_eml/render.py`. Quoted-reply stripping separate TODO if valuable. Shipped as part of N9g-pre: `render.split_body_sections()` + zkm-ner._process_file assigns `scope:` per block — 2026-05-13.
- [x] **E13.** N9g re-evaluation — after γ + per-type extractors + P2 land, re-audit residual body-NER FPs. **Confirmed moot for value-type FPs** (2026-05-12): 20-file invoice sample shows old ORG-with-digits 6→~2 (residuals are legitimate org names). New typed entities added: ~2.25 amounts + ~0.85 emails per invoice-type file; overlap suppression confirmed. **Requires `zkm convert ner`** (cache busted by new model_version key) to apply E6–E7 extractors corpus-wide (~20 min). N9g item also resolved — see below.

- [x] **E15. Apply E6–E7 extractors corpus-wide** — `zkm convert ner` ran 2026-05-13 (55433 docs, ~25 min). (a) E9 step 7c verified: canonical IBAN `CH5380808004209921855` searchable at rank 7 from entities[]-only (lower score than body matches — expected). (b) Pilot post-E15: 658,528 total mentions (+318k from typed extractors); new types: `email_address` 52k, `amount` 30k, `phone_number` 28k, `iban` 517; E13 confirmed (no ORG-with-digits mislabels in top-20). Remaining FPs deferred: `'Kienzler' ×2306` as ORG (own surname), `'Europe' ×1344`, `'Physicist' ×955` — 2026-05-13.

**Named deferrals (with triggers):**
- P3 typed query language — defer until γ + P2 live ≥1 month AND ≥1 concrete typed-query request.
- PII redaction implementation — defer until sharing scenario lands. Architectural design in E10.
- Entity-DB checksum-fail "ignore / correct?" policy — defer until ≥50 `valid: false` entries accumulate.
- `valid: false` forward-flag: re-evaluate dropping the per-type suspicious heuristic (Option 3) after ≥1 month observation.
- Crypto/stock-ticker domain scope — defer; revisit if real use case lands.
- WebUI typed-query hint UX — Phase 3 design concern.

- [x] **N9g-pre. zkm-eml signature + salutation block extraction** — `render.split_body_sections()` (RFC 3676 `-- ` + sign-off regex + greeting regex); `frontmatter.write_message_md` stores `signature_block` / `salutation_block`; `zkm-ner._process_file` extracts from each block with the correct `scope:`; model version bumped to `+scope-blocks-v1`; cache key extended to include sig+sal content. 16 zkm-eml + 4 new zkm-ner tests (133/254 passing) — 2026-05-13. Run `zkm convert ner` to enrich corpus-wide.

- [x] **N9g. General body-NER cleanup follow-up** *(closed 2026-05-12 — E13 verdict: moot)*. Value-type spaCy mislabels (amounts as ORG, IBANs as ORG, emails as PERSON) suppressed by γ typed extractors via overlap. Residual ORG-with-digit cases (~10%) are legitimate org names. Run `zkm convert ner` to apply enrichment corpus-wide. See E13.

- [x] **Methodology rider: future pilot gates need ≥1 paragraph context per item** — documented in `docs/ner.md` § "Quality pilot methodology": ≥500 chars centred on entity span (or full body), concrete `context` field spec. Recorded as decision in `docs/meeting-notes/2026-05-12-1242-n9d-gate-c.md` — 2026-05-12.

- [ ] **Entity alias / synonym linking (Phase 4 backlog)** — `SBB CFF FFS` (DE/FR/IT names for Swiss Federal Railways) highlights that the same real-world entity can appear under multiple mention strings (abbreviations, translations, official variants). Likewise, persons appear under nicknames, maiden names, or initials. Deferred to Phase 4 alongside manual-merge tooling; design note needed in `docs/entity-model.md` before implementation. No heuristic auto-merge — human-confirmed alias pairs only.

- [ ] Session 15 (scoping, not implementation): meeting on zkm-whatsapp core gaps — (a) non-git source state / `zkm.state` helper, (b) per-store YAML config replacing long env-var lists, (c) stable-ID synthesis contract; deliverable: `docs/meeting-notes/YYYY-MM-DD-whatsapp-scope.md`

## Phase 2 housekeeping — repo reorg (decided 2026-05-08-repo-reorg.md)

- [x] **Reorg**: `mv ~/src/zkm-{eml,pdf,photo,scan} ~/src/zkm/plugins/`; deleted dangling symlinks `plugins/zkm-zkm-{eml,photo}`; fievel: `mkdir ~/src/zkm-plugins && mv ~/src/zkm-{eml,photo}.git ~/src/zkm-plugins/` + `git init --bare` for pdf + scan; updated local remote URLs; pushed to verify. 285 tests passing — completed 2026-05-08
- [x] **`add_plugin()` double-prefix** (`src/zkm/convert.py:119`): use `dir_name = name if name.startswith("zkm-") else f"zkm-{name}"`. Covered by `test_add_local_plugin_zkm_prefixed_name` (24 plugin tests passing) — 2026-05-08
- [x] **`add_plugin()` self-link guard** (`src/zkm/convert.py:119`): check `src_path.parent == pdir.resolve()`; return manifest + print "already in the plugins directory"; no symlink created. Covered by `test_add_self_link_guard` (25 plugin tests passing) — 2026-05-08

## Phase 2 session 8 — doc chunking (core)

- [x] Session 8a: `embed.py` — char-window chunker replacing single truncation; `chunk_index` column in `EmbedStore`; store version bump (`_STORE_SCHEMA_VERSION=2`) with rebuild-on-mismatch; env knobs `ZKM_EMBED_CHUNK_CHARS` (default 2000), `ZKM_EMBED_CHUNK_OVERLAP` (default 200); `ZKM_EMBED_MAX_CHARS` deprecated — covered by tests/test_embed.py (31 tests) on 2026-05-08
- [x] Session 8b: `query.py` — `_dense_search` aggregates chunk rows to `max`-per-path before RRF; `_CHUNK_OVERSAMPLE=3` widens topk fetch to handle chunk multiplicity; CLI output unchanged — covered by tests/test_query_recall.py on 2026-05-08
- [x] Session 8c: tests — `test_embed.py` chunk count, overlap, env overrides, legacy deprecation, round-trip, schema rejection, cache reuse + invalidation; `test_query_recall.py` long-document recall (chunk 1 of a doc surfaces via dense), max-per-path aggregation correctness — 259 tests passing on 2026-05-08
- [x] Session 8d: docs — added step 6 to `docs/field-test-bge-m3.md` (long-document recall probe); updated `docs/hybrid-search.md` (removed "first 2000 chars" caveat, added chunk aggregation section + env knob table rows, schema version note) — 2026-05-08

## Phase 2 session 1 — zkm-eml hot-fix

- [x] `originals.py:_merge_inbox_sidecar` + `_merge_cas_sidecar` — change producer dedup key from rendered `.md` path to producer's source-content `sha256` (`raw_sha256` for messages). Source content is stable across runs; rendered paths are not — 2026-05-07
- [x] `thread_index.py:41` — replace bare `except Exception: continue` with narrow `except (OSError, yaml.YAMLError)` + `logger.warning(...)`. A load failure must never silently become a `_1.md` duplicate — 2026-05-07
- [x] Regression tests in zkm-eml: `test_inbox_sidecar_stable_under_message_path_drift`, `test_cas_sidecar_dedup_by_sha256` — assert `producers[]` length stable under path drift — 2026-05-07

## Phase 2 session 2 — embed index fixes

- [x] `embed.py:save_embed_store` — make checkpoint write atomic (write to tmp path + `os.replace`) so an interrupted embedding run cannot corrupt the NPZ file — covered by `test_save_embed_store_atomic_under_interrupt` (test_embed.py) on 2026-05-07

## Phase 2 session 3 — core library

See `docs/object-storage.md` for the spec contract.

- [x] `src/zkm/atomic.py` — `write_atomic(path, content)` (tmp + rename) — covered by tests/test_atomic.py on 2026-05-07
- [x] `src/zkm/hashing.py` — `sha256_file(path)`, `git_blob_sha1(path)` — covered by tests/test_hashing.py on 2026-05-07
- [x] `src/zkm/cas.py` — `write_object(store, subdir, path_or_bytes) -> Path`, idempotent, returns `<subdir>/_objects/<aa>/<rest>` — covered by tests/test_cas.py on 2026-05-07
- [x] `src/zkm/sidecar.py` — read / `merge_producer` / rebuild `.origin.json` per spec v1; atomic write; producer dedup on `sha256`; sort by `message` — covered by tests/test_sidecar.py on 2026-05-07
- [x] `src/zkm/inbox.py` — `symlink_with_sidecar(cas_object, link_dir, producer)` implementing one-canonical-symlink-per-CAS-object — covered by tests/test_inbox.py on 2026-05-07

## Phase 2 session 4 — plugin migration

(Only after session 3 core library is complete and field-tested.)

- [x] `examples/zkm-notes/convert.py` — adopt `zkm.atomic.write_atomic` (currently writes non-atomically, contradicts plugin-spec.md) — covered by tests (164 zkm tests passing) on 2026-05-07
- [x] `zkm-eml` — replace in-plugin atomic/CAS/sidecar/symlink helpers with imports from core; delete the copied implementations in `originals.py` — covered by tests (103 zkm-eml tests passing, originals.py 481→294 lines) on 2026-05-07
- [x] All existing plugin tests still pass; `zkm-eml/originals.py` shrinks — 103 passed, 294 lines on 2026-05-07

## Phase 2 session 5 — hygiene commands

(Only after one week of session 4 in real use, per `docs/phase2-plan.md`.)

- [x] `zkm rm <path>` — remove a managed `.md`; decrement sidecar `producers[]`; if last producer, remove the inbox symlink; if CAS object now unreferenced, remove it. Dry-run by default; `--apply` to commit (with `--no-commit` to skip). Single file only — covered by tests/test_hygiene.py on 2026-05-07
- [x] `zkm gc` — scan all sidecars; CAS objects with empty/missing producers are reported (dry-run) or removed (`--apply`, with `--no-commit` to skip) — covered by tests/test_hygiene.py on 2026-05-07

## `zkm store` — git-like store management

The store is a git repo; zkm should expose a thin wrapper that handles
git-annex / git-lfs automatically so the user doesn't have to think about it.

- [x] `zkm remote add <name> <url>` — `git remote add` on the store — covered by tests/test_store_commands.py on 2026-05-07
- [x] `zkm remote list` — list store remotes — covered by tests/test_store_commands.py on 2026-05-07
- [x] `zkm clone <url> [path]` — clone a store; auto-detect annex/lfs from `.zkm-config` and re-initialise — covered by tests/test_store_commands.py on 2026-05-07
- [x] `zkm push [remote]` — push store commits; if annex: `git annex sync --content <remote>`; if lfs: `git lfs push --all <remote>`; else plain `git push` — covered by tests/test_store_commands.py on 2026-05-07
- [x] `zkm pull [remote]` — pull/rebase store commits; if annex: `git annex sync <remote>`; if lfs: `git lfs pull`; else plain `git pull --rebase` — covered by tests/test_store_commands.py on 2026-05-07
- [x] `--content` flag for `zkm push/pull` with annex: sync actual file content to/from remote (default: metadata only) — covered by tests/test_store_commands.py on 2026-05-07

Design note: these commands read `.zkm-config` to know the backend and dispatch accordingly. The user never has to type `git annex` directly.

## Incremental processing (backlog)

- [x] **zkm-eml: git-commit watermark** — state file `<store>/.zkm-state/zkm-eml.json` keyed by source repo path; `iter_messages_since` fast-enumerates via `git diff`; full-scan fallback when watermark absent/unreachable or source not a git repo — covered by tests (111 zkm-eml tests passing) on 2026-05-07
- [x] **zkm index: git-commit watermark** — watermark at `<store>/.zkm-index/last-commit`; `build_index` fast path via `git diff --name-status`; `--full` flag for forced rescan; `write_watermark` called from `cmd_index` after `save_index` — covered by tests (193 zkm tests passing) on 2026-05-07

## Phase 2 — mbsync auto-trigger (decided 2026-05-08-mbsync-hook.md)

- [x] A1: `src/zkm/devcheck.py` + `cli.py` integration; `tests/test_devcheck.py` — dirty-tree guard (core + invoked plugin), `ZKM_BYPASS_DIRTY_CHECK=1` opts out, non-editable install no-ops. 13 tests passing — 2026-05-08
- [x] A2: `docs/install.md` — documents `uv tool install --editable ~/src/zkm` for `zkm` on PATH; pointer added to `CLAUDE.md` Quick start. 2026-05-08
- [x] A3: `plugins/zkm-eml/hooks/post-commit` + `Makefile` (`install-hook`/`uninstall-hook`); README "Auto-trigger from mbsync" section. 2026-05-08
- [x] A3 fix: renamed `MAIL` → `MAIL_REPO` in Makefile — `$MAIL` is a standard Unix env var inherited by make, overriding `?=` default — verified by user on 2026-05-08
- [x] Python 3.14 pin: added `.python-version`, bumped `requires-python = ">=3.14"` — `uv tool install` was defaulting to 3.11 (requires-python floor) causing needless re-downloads — verified by user on 2026-05-08
- [x] Hook live: `make install-hook` → symlink in `~/mail/.git/hooks/`; empty mail commit triggered convert (27 msgs) + index; journald confirms — verified by user on 2026-05-08
- [x] Hook fix: `zkm index` → `zkm index --no-embed` — bare index was hitting GPU on every sync; embed belongs on separate timer (A5) — verified by user on 2026-05-08
- [x] A5: `contrib/systemd/zkm-embed.{service,timer}` — 30-min user timer running `zkm embed && zkm doctor`; `docs/install.md` "Periodic embed + doctor timer" section with install/drop-in/log instructions — 2026-05-08
- [ ] from 2026-06-05: review journald evidence for convert-overlap; decide on lock if observed.
- [x] **Status observability:** PID file visibility confirmed by user 2026-05-11.
- [~] **zkm-eml signature stripping** — promoted 2026-05-12 to first-class action item: see **N9g-pre** above. (Original framing 2026-05-10-1640-n9b: heuristic detection of email signature blocks before markdown render; addresses popularity skew of personal contact details. Re-scoped from "stripping" to "typed extraction" in N9g-pre.)

## Phase 2 — SIGUSR1 progress + `zkm status` (decided 2026-05-08-1913-sigusr1-status.md)

Scope: `convert` and `index` (BM25 + embed phases) only. `query`, `clone`, `push`, `pull` explicitly out. Daemon/supervisor model deferred (N<2 background callers). Host-wide multi-store registry, historical run log, `--kill`, `--watch`, live-tail all deferred.

- [x] **S1.** `src/zkm/runstate.py` (new): `RunSession` context manager — PID file lifecycle (`<store>/.zkm-state/running/<pid>.json`, atomic write via tmp+rename) + SIGUSR1 handler (forces immediate file write + dd-style stderr line). Fibonacci backoff via `_should_write(count)` helper. Schema: `{command, pid, started_at, args, phase, current, total, message, last_updated}`. 15 tests passing — 2026-05-08
- [x] **S2.** Wire `RunSession` into `cmd_convert` (`src/zkm/cli.py`). PID file appears at start, updated via `session.tick()` alongside tqdm (tqdm guards `if not show_progress`), unlinked on exit. progress callback always passed to run_convert/run_reprocess — 2026-05-08
- [x] **S3.** Wire `RunSession` into `cmd_index` (`src/zkm/cli.py`). Single session spans BM25 + embed phases; `phase` flips `"bm25"` → `"embed"` via `session.set_phase("embed")`. With `--no-embed`, stays in `"bm25"` phase only. progress callback always passed — 2026-05-08
- [x] **S4.** New `cmd_status` subcommand (`src/zkm/cli.py`). Lists `<store>/.zkm-state/running/*.json`, drops stale PIDs (stderr notice), sends SIGUSR1 to live ones, sleeps 50ms, re-reads, prints human table (`pid`, `cmd`, `phase`, `started`, `progress`, `message`). `--json` flag emits JSON array. Empty store prints "no running zkm processes" — 2026-05-08
- [x] **S5.** Updated `docs/plugin-spec.md` cancellation section: SIGUSR1 reserved by core; plugins must not install their own SIGUSR1 handler — 2026-05-08
- [x] **S6.** TODO.md updated with verification checklist (see below) — 2026-05-08
- [x] **S7+S8.** Updated `docs/meeting-notes/meeting-style.md` "Past meetings" index: added mbsync-hook + sigusr1-status entries — 2026-05-08

- [x] **`zkm status --follow` / watch mode** — ANSI-redraw loop, `--leave-if-done` exits when table empty, 2 s poll interval, non-TTY/JSON safe. `_take_status_snapshot` + `_format_status_lines` extracted as helpers. — covered by 5 tests in test_runstate.py (395 passing) on 2026-05-12.
- [x] **`zkm status` ETA column** — `eta_seconds` in PID file schema; `RunSession.tick()` accepts optional `eta_seconds` kwarg (callers can forward tqdm's ETA directly); fallback computes from phase elapsed / current * remaining; SIGUSR1 handler includes ETA in dd-style stderr line; `zkm status` table shows `ETA ~Xm`/`~Xs`, suppressed when unknown or `current == 0`. 7 new tests (350 core passing) — 2026-05-12.
- [x] **`zkm status --follow` SIGUSR1 spam** — `--follow` loop was sending SIGUSR1 every 2 s, breaking tqdm bars in watched processes; `_take_status_snapshot` gains `send_sigusr1=False` param for follow-loop calls; amender commit message fixed (`"amend frontmatter"` not `"ingest 0 file(s)"`); "Staging changes..." notice added before `git add -A`. 1 new test (396 passing) — 2026-05-13.
- [x] **`zkm status --wait`** — alias for `--follow --leave-if-done`; exits when the table is empty (all processes done). `--wait` sets both flags; 1 new test (397 core passing) — 2026-05-13.
- [x] **Scrub continuability / resume-on-restart** — (a) pilot JSONL opened in append mode, each record flushed immediately; (b) `on_file_done` callback from `run_scrub` writes `.zkm-state/scrub-<plugin>-watermark.json` atomically after each file; `--resume` CLI flag reads watermark + passes `resume_after_file` to plugin; watermark deleted on clean completion. 3 core + 5 zkm-ner tests; 400 core + 250 zkm-ner passing — 2026-05-13.
- [ ] **Concurrent-run guard** — `zkm status` already tracks live PIDs via `.zkm-state/running/`; use that to refuse (exit 1 with clear message) a duplicate same-command+plugin launch, and refuse any other store-mutating command (convert/scrub/index) while one is running. Two dimensions: (a) same plugin twice = always refuse; (b) different plugins concurrently = refuse until a scheduling/queue model is in place. **Note:** this is a stepping-stone toward a daemon/supervisor model that aligns with Phase 3 WebUI plans — the daemon would own the run queue and the WebUI would replace manual `zkm status` polling. Design meeting before implementation (daemon scope is non-trivial).

**Verification checklist** (313 tests passing, 2026-05-08):
1. `zkm convert zkm-eml` in terminal A → `zkm status` in terminal B shows one row with fresh `last_updated`.
2. `kill -USR1 <pid>` directly → dd-style line on convert's stderr.
3. `zkm index` → `phase` toggles `bm25` → `embed`; `zkm index --no-embed` stays at `bm25`.
4. SIGKILL the process → next `zkm status` drops stale file with stderr notice.
5. `zkm status --json | jq` → valid JSON array.

## Plugin backlog — conversation / AI session sources

- [ ] **`zkm-claude-code`** — import Claude Code session transcripts (`.claude/projects/*/transcripts/*.json` or similar). Key fields: session ID, timestamp, project path, messages. Stable ID: session ID + message index. Source state: git-commit watermark on transcript dir or mtime-based. Scope and trigger path need a scoping session before implementation.
- [ ] **`zkm-claude-ai`** — import claude.ai conversation exports (JSON or markdown). Same stable-ID and amendment concerns as zkm-claude-code; likely shares core parsing logic. **Scoping note (2026-05-10 meeting):** the interesting corpus is `conversations.json` + per-project conversation IDs (not `docs[]` — those are a round-trip backup of disk content, see `~/.claude/projects/-home-tobias-src-zkm/memory/zkm_claude_plugin.md`). Hold a dedicated scoping meeting before implementation to decide start order (zkm-claude-ai vs zkm-claude-code first).
- [ ] **Other AI provider sessions** (ChatGPT exports, Gemini, etc.) — deferred until zkm-claude-code lands and the session-import pattern is proven. N=2 for a shared `zkm.session` helper module requires at least two providers implemented.

## Plugin backlog — social networks

- [ ] **Meeting: social-network profile scraping scope** — LinkedIn profile photo + resume/CV export, and equivalent for other networks (Instagram, Twitter/X, Mastodon, GitHub bio, etc.). Two distinct sub-questions: (1) *identity card* — profile data as a per-person entity page (photo, headline, current employer, skills); (2) *activity feed* — posts, reactions, comments, tags. Both have legal/TOS constraints that differ by network (takeout export vs. API vs. scraping). Needs a scoping meeting before any implementation. Key design questions: which networks are in scope, what the canonical markdown shape is, and whether profile data goes into `entities[]` (γ schema) or its own document type.
- [ ] **Meeting: takeout / export archive import** — personal data exports from Google Takeout, Facebook "Download Your Data", Instagram, LinkedIn, Twitter/X, etc. are structured archives (ZIP + JSON/HTML). Distinct from live scraping: deterministic, offline, privacy-safe. Sub-questions: (1) which export formats to support first (LinkedIn most structured); (2) shared `zkm.takeout` extraction helper vs. per-network plugins; (3) "being tagged" in others' posts as a distinct entity-mention type (requires cross-document resolution). Warrants a scoping meeting; likely a prerequisite for the live-scraping meeting above.

## Encoding / text quality (backlog)

- [x] **Text file encoding issues — implementation** — refactored `_decode_part` and `_decode_header_str` in `plugins/zkm-eml/src/zkm_eml/parse.py`; added `charset-normalizer` detection + `ftfy` mojibake repair; 6 new fixtures + 6 tests; 21 zkm-eml + 315 core tests passing — 2026-05-08
- [x] **Text file encoding issues — live reprocess** — 29 mojibake messages corrected; grep count confirmed 0; embed running via systemd timer — verified by user on 2026-05-08

## Versioning — retroactive tags (decided 2026-05-08-2318-tagging-cadence.md)

Convention: bump-and-tag + loose-0.x + plain `vX.Y.Z` per repo. See `CLAUDE.md` "Versioning".

- [x] `plugins/zkm-eml/`: tagged `9d06d1a` as `v0.1.0`; HEAD (`daf9ab4`) as `v0.6.0`. Pushed to fievel — 2026-05-08
- [x] `plugins/zkm-photo/`: tagged HEAD as `v0.1.0`. Pushed to fievel — 2026-05-08
- [x] `plugins/zkm-pdf/`: tagged HEAD as `v0.1.0`. Pushed to fievel — 2026-05-08
- [x] `plugins/zkm-scan/`: tagged HEAD as `v0.1.0`. Pushed to fievel — 2026-05-08
- [x] `plugins/zkm-notmuch/`: added fievel remote `fievel:src/zkm-plugins/zkm-notmuch.git`; pushed main + v0.1.0 tag — 2026-05-09
- [x] Backfill `zkm>=X,<Y` requires-clauses in all plugin pyprojects — `zkm>=0.2.0,<0.3.0` added to zkm-eml, zkm-photo, zkm-pdf, zkm-scan, zkm-notmuch; `uv sync` verified in all five — 2026-05-10.

## Amendment contract backlog

- [ ] **Meeting: amendment replace-mode** — set-union merge (current) is correct for additive enrichment but cannot remove stale entities when extractor quality improves. `zkm scrub <plugin>` is the current workaround (N9b + future N9c). Trigger for meeting: a third amender wants single-producer-per-field semantics, OR N9c surfaces a need not solvable by scrub. See `docs/meeting-notes/2026-05-10-2142-n9b-scrub-cli.md` for design context.

## Plugin dependency loading (backlog)

- [ ] **Plugin-specific deps when loaded via importlib** — when `zkm convert` loads a plugin via `importlib.util.spec_from_file_location` into the main process, the plugin runs in the main zkm venv which lacks plugin-only deps (e.g. `ftfy`, `charset-normalizer` in zkm-eml). Current workaround: `convert.py` injects `.venv/lib/python*/site-packages` into `sys.path` at import time. Explore proper solutions: (a) subprocess isolation per plugin, (b) uv-run-in-plugin-venv wrapper, (c) declare plugin deps as optional extras in core and install them together. Warrants a scoping meeting before changing the plugin loading model.
- [x] **Broken `uv.sources` paths after repo reorg** — fixed `../zkm` → `../..` + `requires-python` bumped to `>=3.14` in zkm-pdf, zkm-photo, zkm-scan; zkm-notmuch was already correct. `uv sync` verified in all three on 2026-05-10.
- [ ] **Meeting: derivable-but-expensive data in git** — extraction cache and amendment queue are gitignored as "derived". But re-deriving is expensive (NER over 55k mails ~20 min). Decide: (a) keep gitignored + accept re-run cost on fresh clone, (b) track extraction-cache in git (cheap writes, big repo), (c) separate annex/LFS sidecar for cache, (d) remote cache (S3/Minio). Warrants a design meeting before first multi-machine sync.
- [x] **`zkm init` missing `.zkm-state/` in default `.gitignore`** — fixed in d157b1c (watermark commit); `.zkm-state/` added to `_GITIGNORE` in `store.py`.
- [x] **`zkm scrub` has no progress indicator** — wired tqdm + RunSession progress_cb into `cmd_scrub`; added `--no-progress` flag; `scrub()` in zkm-ner already called progress — 2026-05-11.
- [x] **`zkm convert` reports "Converted 0 file(s)" for amenders** — suppressed the line when `plugin.kind == "amender"` (moved `find_plugin` call before the echo) — 2026-05-11.
- [x] **`zkm status` CMD column hides plugin** — display `command(args[0])` (e.g. `convert(ner)`) in CMD column; `args` already stored in PID file — 2026-05-11.
- [x] **Plugin name convention** — bare manifest names (eml/pdf/photo); `find_plugin()` strips `zkm-` prefix for compat; β migration (no store rewrite); dir names stay `zkm-*`. See `docs/meeting-notes/2026-05-11-1401-plugin-name-prefix.md`.
- [ ] **Meeting: verb order** — `zkm convert <plugin>` vs `zkm <plugin> convert` / `zkm <plugin> run`; the latter matches git-plugin style and disambiguates status display. Scoped separately after prefix-naming decision landed.
- [x] **Hook output swallowed by journald rate-limiting** — `tee -a` to `<store>/.zkm-state/hook-zkm-eml.log`; journald still receives output for quick queries; systemd-cat has no rate-limit flag — 2026-05-11 (zkm-eml ef28df3).
- [x] **`docs/object-storage.md` extraction-cache section stale** — split into two subsections: per-document NER cache (shipped Phase 2.5, `src/zkm/extraction_cache.py`) vs per-CAS-object content cache (design only, Phase 3+); added pointer to `docs/ner.md` — verified by /meeting Class 1 dispatch 2026-05-11
- [ ] **Dirty-check guard interacts badly with `git stash`** — stashing uncommitted source changes to satisfy the guard, then running `zkm index`, rebuilds the index with the pre-stash (old) code. Correct escape hatch is `ZKM_BYPASS_DIRTY_CHECK=1`. Investigate: should the guard detect that the stash contains source changes and warn, or is the doc fix sufficient?
- [ ] **`docs/object-storage.md` reconciliation (low priority)** — full cross-check of the spec against the current implementation; confirm which sections are shipped vs. design-only; update any stale promises. Orphan from 2026-05-11-1506-n10-n11-docs-bundle meeting.

## Publishing / distribution (backlog — from 2026-05-12-0844-publish-plugins.md)

- [x] **zkm-eml: backfill missing semver tags** (cosmetic) — tagged v0.2.0 (837130a), v0.2.1 (47a4650), v0.3.0 (e1c3808), v0.4.0 (524bb60), v0.5.0 (b1a3f2a) from commit-message milestones (pyproject.toml stayed at 0.1.0 until v0.6.0). Pushed to both fievel and GitHub — 2026-05-13.

**Orphaned publish-plugins items (A1–A9 from 2026-05-12-0844-publish-plugins.md) — done vs. pending:**
- [x] A1 — LICENSE files: MIT applied to core + all plugins (confirmed present)
- [x] A4 — Generality fixes for zkm-ner: `tobias`/`kienzler` removed from textfilter.py + tests
- [x] A7 — Canary publish zkm-eml to GitHub (`zommuter/zkm-eml` live)
- [x] **A2 — MVP READMEs**: `plugins/zkm-ner/README.md` (+ γ schema output section), `plugins/zkm-notmuch/README.md` (fixed `NOTMUCH_TAGS_EXCLUDE` typo + added `NOTMUCH_CONFIG` row), `plugins/zkm-scan/README.md` (fixed `SCAN_LANG` default `deu+eng`, `SCAN_MIN_TEXT_CHARS` default `10`); `examples/zkm-notes/README.md` already uniform — 2026-05-13.
- [ ] **A3 — Sweep existing READMEs**: update `plugins/zkm-eml/README.md`, `plugins/zkm-pdf/README.md`, `plugins/zkm-photo/README.md` — append uniform license footer; replace `~/src/zkm-<name>` paths with `plugins/zkm-<name>` (relative); fix `Zommuter/zkm` → `zommuter/zkm`.
- [ ] **A5 — Strip personal headers from eml CLAUDE.md**: remove `Repo: ~/src/zkm/plugins/zkm-eml/` and rewrite dev-setup commands to relative paths. Contract: `grep -E '~/src|/home/' plugins/zkm-eml/CLAUDE.md` returns empty.
- [ ] **A6 — Add `.gitignore` to zkm-scan**: use the same template as `plugins/zkm-eml/.gitignore`. Contract: `git -C plugins/zkm-scan check-ignore __pycache__/foo.pyc` succeeds.
- [ ] **A8 — Batch publish 5 remaining plugins to GitHub**: `zommuter/zkm-ner`, `zommuter/zkm-notmuch`, `zommuter/zkm-pdf`, `zommuter/zkm-photo`, `zommuter/zkm-scan`. Add `zkm-plugin` topic. Contract: `gh repo list zommuter --topic zkm-plugin` returns all 6 (including eml).
- [ ] **A9 — Cross-link from core README**: add "Plugins" section to `~/src/zkm/README.md` listing all 6 plugin repos. Contract: `grep -c 'github.com/zommuter/zkm-' README.md` ≥ 6.

- [ ] **ASAP: PyPI publishing** — investigate publishing core `zkm` + 6 plugins to PyPI; issues: account + name-reservation, `uv build` / `uv publish` workflow, classifier metadata, version-bump-and-publish cadence. Coordinate with bump-and-tag rule: each pyproject version bump should trigger both a git tag and a PyPI release.
- [ ] **Runtime user-identity config for zkm-ner** — spec a `ZKM_NER_USER_NAMES` env var (or per-store `.zkm-config` entry) so users can extend the greeting-salutation stoplist at runtime without editing source. Default: empty (no built-in personal names). See `gazetteers/orgs.yaml` for the config-file pattern.
- [ ] **Meeting: per-plugin TODO topology** — decide where plugin-scoped TODOs live now that plugins have independent GitHub repos. Options: (1) keep central `TODO.md` in core, (2) each plugin gets its own `TODO.md` + central for cross-cutting, (3) GitHub Issues for larger items + central for tactical. Option 3 would require /meeting-skill modifications to emit GH issue refs as action items. Schedule a dedicated design meeting.
- [ ] **git post-commit hook: auto-tag on pyproject.toml version bump** — after each commit that changes `version =` in any plugin's `pyproject.toml`, automatically create the matching `vX.Y.Z` tag in the same repo. Avoids the current manual tag step. Scope: per-plugin `.git/hooks/post-commit` (or a shared script under `contrib/`). Contract: `git tag --list` shows the new tag immediately after a version-bump commit.
