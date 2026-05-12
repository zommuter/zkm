# 2026-05-12 — Entity vs. data-mining scope

**Started:** 2026-05-12 15:00
**Session:** f474a639-b226-4b4b-b8e8-25906ac72865
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🧬 Nora (IE / NER typology, re-onboarded), 📬 Pim (PIM engineering, re-onboarded), 🧠 Mira (ML lens — PII / classifier-cost concerns)
**Topic:** Where does the line fall between "named entity worth storing in `entities[]`" and "structured data value to be searchable but not entityised"? Resolve before designing N9g (general body-NER cleanup) and any successor verifier.

## Grounding (load-bearing facts, verified before meeting)

- **Current entity type set** (`plugins/zkm-ner/src/zkm_ner/_types.py`, `docs/ner.md:27-39`): Pattern overlay: `email`, `phone`, `url`, `org_hint`, `social_handle.<platform>`, `linkedin_profile`, `github_profile`, `org` (gazetteer). spaCy NER (POS-filtered): `person`, `org`, `place`, `misc`. **No value types**: no `amount`, `currency`, `iban`, `invoice_id`, `reference_number`, `registration_code`, `date_literal`, etc.
- **Suspicious heuristic is name-centric** (`plugins/zkm-ner/src/zkm_ner/suspicious.py:13-33`): `"no alphabetic content"` flags pure digits/punctuation → currency/IBAN/refnum would be flagged as suspicious if ever emitted. The heuristic encodes the assumption that values are noise.
- **Indexes ignore frontmatter** (`src/zkm/index.py:63-68`, `src/zkm/embed.py:372-398`): BM25 tokenises `post.content + title + tags`; dense embeds `title + tag_str + body`. Neither sees `entities[]` or `participants[]`. Extracting a value to frontmatter without retaining it in body makes it unsearchable.
- **`zkm-eml` body never contains raw headers** (`plugins/zkm-eml/src/zkm_eml/render.py:21-46`): From/To/Subject/Date live in frontmatter only. Body-NER does not re-extract header content. Pollution sources are signatures, salutations, inline quoted text.
- **PII redaction model is already typed-denylist** (`docs/entity-model.md:57-61`): config-driven `entity.type` denylist replaces values at render/export time. Adding new types directly extends this lever.

## Agenda

1. **Scope (a):** Should value-type strings (currency amounts, reference numbers, IBANs, registration codes) be extracted into `entities[]` at all, filtered pre-store, or treated as a separate dimension?
2. **Index coverage (b):** Does the existing BM25 + dense pipeline cover these adequately without NER? Where are the gaps?
3. **Suspicious-heuristic confusion (c):** Does the current `is_suspicious` predicate conflate value-type noise with name-type noise?
4. **Schema evolution (d):** Move toward typed slots with provenance, or keep flat `entities[]` and add types within it?
5. **Forward implications:** N9g design, PII denylist, `participants[]` blind spot in search.

## Discussion

### Item 1 — Scope: are values entities?

🏗️ **Archie** listed three options: α (names-only + value filter), β (flat schema with value types, no structured-slot semantics), γ (typed-slot frontmatter redesign with provenance).

🧬 **Nora** distinguished three IE kinds: (1) named entities with KB identity (`person`, `org`, `place`) — belong in `entities[]`; (2) temporal/numeric expressions (`amount`, `date`, `duration`) — literals attached to relations, not entities; (3) domain identifiers (`iban`, `invoice_id`) — identity-by-exact-match, not fuzzy name disambiguation. β is "extended flat schema," not real typed slots. γ is the structured-slot semantics.

😈 **Riku** flagged: "values out of scope" only holds if the pipeline guarantees no value-shaped string reaches `entities[]` as a name-type entity. spaCy currently mislabels `'14,98 EUR'` as ORG. "Out of scope" means *filter pre-store*, not ignore the problem.

🧠 **Mira** raised the PII argument for typed values: the planned `entity.type` denylist (`entity-model.md:57-61`) needs typed entries to match on. Values in body-only means the redactor must operate on regex over rendered markdown — the brittle thing the typed denylist was designed to replace.

🏗️ **Archie** initially recommended α + named deferrals for value-PII and γ-migration. 😈 **Riku** pushed back: "out of scope for PII" must be a *named deferral*, not silently bundled.

**[Human — Zommuter]:** "I see little value in deferring γ — who cares if this blocks N9g-pre when we're dealing with a significant schema / scope problem? But we should definitely use simple RegEx etc extraction for the well-formatted values (ideally with e.g. RFC/ISO/... links, which goes again back to my other traceability-tracking project idea). So let's dive into 3 / γ."

γ adopted. N9g-pre blocked until migration. Value-types extracted via regex/pattern only (never spaCy). Standard-spec links in `standard:` field. Forward-flag: `standard:` field is the join point for a separate traceability-tracking project.

### Item 2 — γ schema shape, provenance, standards links

Three sub-questions: provenance taxonomy, slot type taxonomy, YAML shape.

🏗️ **Archie** proposed list-of-records: `entities: [{scope, type, value, canonical?, standard?, unit?}]`. Two arguments against dotted-key flat fields: YAML readers don't deconstruct `signature.email` as a path; all existing list conventions in zkm use list-of-records (`entities[]`, `participants[]`, `producers[]`).

📬 **Pim** endorsed: Schema.org/JSON-LD compatible; `scope` field directly answers the position-signal question.

🧬 **Nora** refined: `scope` is plugin-controlled (each plugin declares its valid scopes in `plugin.yaml`); `standard:` is open-vocabulary (rfc5322, iso13616, iso4217, iso8601, e164, iso3166, iso639, din276, isbn, ean13...). Connects to traceability project.

😈 **Riku** flagged: `canonical` inflates corpus (emit only when `canonical != value`); migration cost (graceful-read preferred over one-shot script); `emitted_by` duplicates the amendment sidecar channel (keep in sidecar, not inline).

🧠 **Mira**: PII redaction must operate on `value`, not `canonical`. Canonical is for dedup/programmatic use; redaction needs the as-written form.

✂️ **Petra** confirmed graceful-read matches the `_PARSER_VERSION` precedent.

**[Human — Zommuter]:** Shape = list-of-records (1). "scope shouldn't affect entity meanings, right?" Migration = graceful read. "Before v1.x we'll re-extract from scratch anyway to compare migration vs scratch output." Canonical/privacy: "doable by using the extraction and canonicalization procedure in a back-linking way, right?"

### Item 3 — Scope semantics + canonical/redaction back-link

🧬 **Nora** answered: same value across scopes is the same thing in the world, but scope is a provenance-confidence signal (signature > body > quoted). Three sub-positions on dedup:
- (A) Scope-included dedup `(scope, type, value)` — preserves position signal; same email in signature and body are two distinct mentions.
- (B) Scope-excluded dedup `(type, value)` — entity-level dedup with provenance flattening.

📬 **Pim** and 🏗️ **Archie** argued (A) aligns with the existing "mentions, not UIDs" convention. Same email in signature AND in a quoted-reply is a meaningful structural signal.

😈 **Riku** added: downstream consumers must `GROUP BY (type, value)` and aggregate scope — document explicitly so joins don't break on multiplicity.

🧠 **Mira** on canonical/redaction: **shared normaliser library** at `zkm.canonical.<type>(value) -> str`. Extractors write `canonical`; redactor imports the same function and matches on `canonical`. No `normaliser:` metadata field needed.

🧬 **Nora** refined: `canonical` only for standards-defined normalisations (IBAN whitespace, ISO-8601 date, amount-to-decimal). Skip for soft-identity types (person, org, place, email local-part — RFC 5321 case-sensitivity ambiguity).

📬 **Pim** added: document canonical-omitted types in `docs/entity-model.md` to prevent future amenders from inventing ad-hoc canonicalisations.

### Item 4 — Suspicious heuristic under the typed model

🏗️ **Archie** noted: the current predicate (`suspicious.py:13-33`) was designed for the pre-γ flat-type world. Under γ, value-types legitimately trigger current rules: IBAN = "no alphabetic content"; DIN/HRB = "all-caps."

🧬 **Nora** introduced three-tier split: name-type predicate (existing rules for person/org/place/misc), value-type predicate (shape/checksum validation — near-zero FP), identity-strong-type predicate (RFC/regex shape validation for email/url/phone).

🏗️ **Archie** proposed `_PREDICATES = {amount: _amount_predicate, iban: _iban_predicate, ...}` dispatch table with `_name_predicate` as default fallback.

😈 **Riku** confirmed no N9d/verifier dependency — pure shape-validation feeding the existing pilot.py review queue.

**[Human — Zommuter]:** Option 1 (per-type dispatch). Riders:
- Checksum failure: for anonymisation, fail-safe (redact even on checksum fail). For entity DB, checksum-fail-but-shape-match needs a "store as invalid / ignore / correct?" policy decision at some point.
- "Locale-aware" is dangerous in mixed-context corpora. Use structure, not locale assumption.
- Currency codes must include crypto tickers (BTC, ETH, USDT); stock labels deferred.
- Consider Option 3 (drop heuristic entirely) after ≥1 month observation under per-type model.

### Item 5 — Index integration

🏗️ **Archie** grounded: `participants[]` is invisible to BM25/dense today (pre-existing bug). γ without index integration is "schema overhaul for redaction only."

🧬 **Nora** introduced dual-mode IE: lexical index over natural text + structured index over typed fields. zkm has only the first.

Three options: P1 (no change), P2 (BM25 sees frontmatter values as plain tokens), P3 (typed query language).

🏗️ **Archie** cost: P2 = ~30-50 LOC + tests in `index.py`/`embed.py`; ~5MB extra on 55k docs (negligible); folds into γ `model_version` rebuild; P3 is purely additive on top of P2 (no rework).

🧬 **Nora** on query-canonicalization: needs a type to dispatch on — P3 feature, not P2 alternative. For P2 era: index both `value` and `canonical` when they differ.

**[Human — Zommuter]:** P2 + pilot. Forward-flag for WebUI: query input should subtly hint typed query syntax (`iban:...`, quoted raw, etc.); default behaviour to be discussed at WebUI design time.

### Item 6 — Forward implications

🏗️ **Archie:**
1. **N9g largely moots.** Under γ, value-type spaCy mislabels (like `14,98 EUR` as ORG) are caught upstream by the typed extractor; spaCy never sees them. Residual body-NER FPs reduce to name-type errors addressed by N9c. Re-evaluate N9g after γ lands.
2. **N9g-pre stays valuable, schema changes.** Signature/salutation extraction now emits `scope: signature/salutation` typed entries. Same work, γ-shape output. Sequenced after γ migration (E1–E3).
3. **PII denylist architecturally unblocked.** Typed `entities[]` enables the denylist to fire as designed. Implementation still deferred to a sharing scenario.
4. **WebUI typed-query UX** — Phase 3 design concern.
5. **Cross-project traceability** — `standard:` field is the join point.

😈 **Riku** flagged sequencing: don't ship γ + P2 + per-type extractors as one bundle. γ schema → per-type predicate refactor → `amount` extractor pilot → more value-types → P2 index integration.

✂️ **Petra:** ~6–8 sessions for full γ rollout.

## Decisions

- **γ adopted** — typed-slot frontmatter via list-of-records `entities: [{scope, type, value, canonical?, standard?, unit?, valid?}]`. Dedup key `(scope, type, value)`. Mentions, not entities — preserves position signal. Out of scope: nested-objects shape, dotted-key shape.
- **`scope` field** — plugin-controlled open vocabulary, declared in `plugin.yaml`. Graceful read: missing scope treated as `body`. Core scopes documented in `docs/entity-model.md`.
- **`canonical` field** — emitted only when `canonical != value`, only for standards-defined normalisations (IBAN whitespace, ISO-8601, amount-to-decimal). Skipped for soft-identity types (person, org, place, email local-part).
- **`valid: false` field** — entities with passing shape but failing checksum carry `valid: false`. Redactor treats `valid: false` as still-redact (fail-safe). "ignore / correct / store-as-invalid" policy deferred until ≥50 `valid: false` entries accumulate.
- **Provenance attribution stays in amendment sidecar** — no inline `emitted_by:` on entity records.
- **Migration = graceful read** — code treats missing `scope` as `body`; cache-bust via `model_version` triggers re-extraction on next convert. Pre-v1.x verification: re-extract from scratch and diff against graceful-read migration output.
- **Shared normaliser library** at `zkm.canonical.<type>(value) -> str` — imported by both extractors and redactor. No `normaliser:` per-entity metadata field.
- **Per-type suspicious dispatch** — `_PREDICATES[type] = predicate` in `suspicious.py`; default `_name_predicate` (existing rules); each predicate co-located with its extractor.
- **Extractor contract per type** — only emit values that pass a type-specific shape+validation gate. Garbage doesn't reach `entities[]`.
- **Amount predicate is structure-aware, not locale-aware** — accepts multiple separator/grouping conventions; canonical = period-decimal + separate `unit:`. No `locale:` field.
- **`unit:` is open-vocabulary** — fiat with `standard: iso4217`; crypto tickers with `standard: crypto_ticker`. Stock tickers deferred.
- **P2 index integration** — BM25 and dense embed tokenise `entities[].value` + `canonical` (when differs) + `participants[].address`/`name`. Pilot via field-test before lock-in.
- **Redactor scope expands to BM25/dense input stream** — shared-normaliser library is the integration point.
- **Sequencing** — γ schema → per-type predicate refactor → `amount` extractor pilot → more value-types → P2 index integration + field-test pilot. Each step rollback-able.

**Out of scope (named deferrals with triggers):**
- P3 typed query language — defer until γ + P2 live ≥1 month AND ≥1 concrete typed-query request lands.
- PII redaction implementation — defer until a sharing scenario lands.
- Entity-DB checksum-fail "ignore / correct?" policy — defer until ≥50 `valid: false` entries accumulate.
- Crypto/stock-ticker domain scope — defer; revisit if real use case lands.
- Phase 4 KB-ID / manual-merge tooling — out of γ scope.
- WebUI typed-query hint UX — Phase 3 design concern.
- N9g (general body-NER cleanup) — re-evaluate after γ + per-type extractors land; expected to close as moot.

## Action items

- [ ] **E1.** `plugins/zkm-ner/src/zkm_ner/_types.py` — `Entity` gains `scope: str = "body"`, `canonical: str | None = None`, `standard: str | None = None`, `unit: str | None = None`, `valid: bool = True`. Update `__post_init__` (canonical/value-must-differ guard). Existing tests still pass.
- [ ] **E2.** `src/zkm/amendments.py` — dedup key for `entities[]` extends from `(type, value)` to `(scope, type, value)`. Graceful read: missing scope = `body`. New tests: scope-included dedup, graceful read of pre-γ entries, cross-scope coexistence.
- [ ] **E3.** `src/zkm/canonical.py` (new) — `iban(s)->str`, `amount(s)->tuple[str,str]`, `email(s)->str` (domain lowercase), `phone(s)->str` (E.164 basic), `iso8601(s)->str`. Each function docstring names the standard. Tests per function.
- [ ] **E4.** `plugins/zkm-ner/src/zkm_ner/suspicious.py` — `_PREDICATES` dispatch table. Move existing rules into `_name_predicate`. Stub predicates for future value types. 5+ new tests.
- [ ] **E5.** `plugins/zkm-ner/scripts/verify_gamma_migration.py` (new) — re-extract a sample from scratch, diff against graceful-read migration result. Hard-gate for v1.x release.
- [ ] **E6.** `amount` extractor pilot — `plugins/zkm-ner/src/zkm_ner/extract.py` gains `_extract_amounts(text) -> list[Entity]`. DE/CH/EN amount regex. Canonical via `zkm.canonical.amount`. Suspicious predicate co-located. Tests incl. `'CHF 1\'000.-'`, `'1.000,50 €'`, `'-0.01 USD'`.
- [ ] **E7.** Second-round value-type extractors (separate sessions per type): `iban`, `email` (γ-migration verify), `phone`, `url`, `invoice_id`, `tracking_id`, `registration_code` (HRB, DIN, ISBN, EAN13).
- [ ] **E8.** P2 index integration — `src/zkm/index.py:_tokenize_doc` and `src/zkm/embed.py:_chunk_texts` gain entity/participant tokenisation. Tests. Rebuild folds into γ `model_version` bump.
- [ ] **E9.** P2 field-test pilot — re-run `docs/field-test-bge-m3.md` with P2-on vs P2-off. Measure recall delta + index size. Record as step 7 in the field-test doc.
- [ ] **E10.** Redactor scope expansion — design note in `docs/entity-model.md` PII section: redactor must operate on BM25/dense input stream too; `zkm.canonical.<type>` is the integration point.
- [ ] **E11.** Docs contract tables — add to `docs/entity-model.md`: (a) valid types table (`type`, canonical yes/no, `standard:` value, expected `scope:` values, PII sensitivity); (b) provenance scopes table (per-plugin, plugin.yaml-declared, open-vocabulary). Update `docs/ner.md` with per-type extractor contract.
- [ ] **E12.** N9g-pre — re-promote in TODO.md with γ schema output (`scope: signature/salutation`). Sequenced after E1+E2+E3. Owner: `plugins/zkm-eml/src/zkm_eml/render.py`.
- [ ] **E13.** N9g re-evaluation — after γ + per-type extractors + P2 land, re-audit residual body-NER FPs. Expected outcome: close as moot.
- [ ] **E14.** TODO.md updates — resolve the "Meeting: NER scope vs. data-mining vs. search index" item; promote E1–E13 into Phase 2.5/3 sequencing; update N9g-pre and N9g blocked annotations.
