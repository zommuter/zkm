# 2026-05-10 — Entity extraction scoping

**Started:** 2026-05-10 11:48
**Session:** 3b353114-67fb-4020-b454-2f05f3372827
**Attendees:** Archie (architect), Riku (devil's advocate), Petra (productivity), Mira (multimodal ML, registry)
**Topic:** When and how does NER land in zkm — timing, trigger model, library choice, amendment wiring.

## Relevant discoveries
- Face detection ≠ face recognition (2026-05-08, zkm/information-flow): without enrolment, recognition gives clusters not names. **Directly applies here**: NER (span extraction) and entity resolution (canonical-ID linking) are two distinct problems. Phase 2 likely scopes extraction only; resolution is later.

## Agenda
1. **Timing & sequencing** — promote NER to Phase 2.5 (before whatsapp), keep at Phase 3, or carve out a new slot? What does it block / unblock?
2. **Trigger model** — where does NER run: each converter inline, a core `zkm enrich` post-processor, or a dedicated amendment plugin (zkm-ner)?
3. **Library / model choice** — spaCy multi-lingual (`de_core_news_sm` + `en_core_web_sm`), GLiNER (zero-shot transformer, multilingual), or pattern-based bootstrap?
4. **Scope boundary** — extraction only, or also resolution (clustering "Frank Müller" ≈ "F. Müller" ≈ "frank.mueller@proton.me")?

## Discussion

### Item 1 — Timing & sequencing

**Archie:** The amendments contract (`docs/plugin-spec.md`, `src/zkm/amendments.py:26 tests passing`) was *already* designed with `entities` as a multi-producer field. zkm-notmuch is the first amender, writing into `tags` set-union. Adding an `entities` amender plugs into the same `merge_records` pipeline — no new core surface needed. The plumbing is paid for. Promoting NER to Phase 2.5 is mechanically cheap.

**Petra:** N=2 check. NER consumers right now: (a) the WebUI entity pages (Phase 3, not yet built), (b) … what else? "Better search" via entity-tagged BM25 is hand-wavy. If the only real consumer is the WebUI, NER ships *with* the WebUI in Phase 3 — that's cheaper to validate end-to-end than building the extraction half blind. **Question for Tobias**: what surfaces NER *now*, before WebUI exists?

**Riku:** Disagree on "blind". The corpus-shape question — *do entity counts even look reasonable on this store?* — is answerable today and only today. If you wait for Phase 3, you'll discover that German NER misclassifies "Stadtwerke" at the same moment you're trying to demo the WebUI. The empirical-pilot heuristic in CLAUDE.md ("observe before preventing") cuts the same way: ship the extractor first, look at the output for two weeks, *then* build the consumer.

**Mira:** Cost angle. spaCy `de_core_news_sm` is ~13MB, ~1ms/sentence on CPU. GLiNER-multi is ~600MB, ~50ms/doc on CPU. Across 55125 docs (current store size) one-shot: spaCy ≈ 1 minute, GLiNER ≈ 45 minutes. Re-runs for new docs are negligible either way. Cost is not a blocker for either.

**Archie:** One more sequencing constraint: `zkm-notmuch` already lands `tags` via amendments. If NER also lands via amendments, we should land it *before* whatsapp — whatsapp messages are a high-NER-yield corpus (every contact is a person), and processing them without NER means re-running NER on the whole whatsapp shard later. Doing NER first lets every plugin's output be enriched on first ingest.

**Petra:** Concedes the corpus-shape pilot point. But she's allergic to "build it before there's a consumer" — wants the pilot to land as a one-off `zkm enrich` command (CLI-driven, not auto-triggered), so that the *cost of being wrong* is low. If NER quality is bad, you delete the entities field; you didn't bake it into every plugin.

**Tobias:** Phase 2.5, before whatsapp.

**Decision:** NER lands in Phase 2.5 *before* the whatsapp scoping session (Session 15). Whatsapp deferred behind NER.

### Item 2 — Trigger model

Three candidate trigger models:

- **(A) Plugin-side inline**: each converter calls NER as the last step, populates `entities:` in frontmatter directly.
- **(B) Core post-process command**: `zkm enrich` walks the md tree, runs NER, writes back via `zkm.amendments`.
- **(C) Dedicated amendment plugin (zkm-ner)**: NER ships as an amender, mirrors zkm-notmuch's shape.

**Archie:** (A) is wrong on aesthetic and contract grounds. The plugin-spec.md "single-producer body, multi-producer frontmatter" rule means converters own the body and a *minimal* frontmatter; enrichment is what amenders are for. Inlining duplicates the dependency, the model loading cost, and the failure surface. Hard pass on (A).

**Petra:** Agrees, with a caveat. (B) only earns its spot if NER is the only enrichment we'll ever want. If we expect to add LLM-based summary, sentiment, or topic classification later, then `zkm enrich` becomes a registry of enrichers and we've reinvented plugins poorly. (C) is just *plugins, the way we already do plugins* — N=2 already met (notmuch + ner = two amenders). Vote (C).

**Riku:** Presses on (C). What does "auto-trigger" look like? After a `zkm convert zkm-eml` run, does NER run automatically, or does the user have to remember `zkm convert zkm-ner`? If manual, every fresh ingest leaves the store in a half-enriched state until the user remembers. If auto, what's the trigger contract?

**Archie:** A modest extension: the existing mbsync hook (`plugins/zkm-eml/hooks/post-commit`) already chains `convert → index`. We add NER to the same chain (`convert → ner → index`). For non-mbsync plugins, the user runs `zkm convert <plugin> && zkm convert zkm-ner` themselves, or we add a `--with-amenders` flag on `zkm convert` that runs all installed amenders after the body producer. Auto-chaining is a small, contained extension.

**Mira:** NER cost is dominated by *first-run* on the whole corpus (~1 min spaCy / ~45 min GLiNER on 55k docs). Auto-chain on every `convert` re-runs only on *new* docs (assuming watermark honoured). That's the right shape — incremental enrichment, full-store catch-up via `zkm convert zkm-ner --full`.

**Riku:** Watermark honour is the load-bearing assumption. zkm-notmuch already has a watermark concern (notmuch tags can change on existing messages). NER is *more* stable — once extracted, entities for a given content hash don't change until you change the model. Cache key: `(sha256_of_body, model_name, model_version)`. Same cache shape as the deferred extraction-cache (Session 9d note in `docs/object-storage.md`).

**Petra:** And — bonus — the extraction-cache design (deferred Session 9d) gets its first concrete N=2 if we wire NER as an amender. Notmuch tags don't fit the cache (they change), but NER does. So zkm-ner unblocks the extraction-cache decision *empirically* rather than speculatively.

**Tobias:** Option 1 (zkm-ner amender + `--with-amenders`), but default-on with opt-out — this is core functionality. Land the extraction-cache alongside zkm-ner.

**Decision:**
- Build `zkm-ner` as a dedicated amendment plugin (mirrors zkm-notmuch shape).
- `zkm convert <plugin>` runs amenders by default; opt-out flag (e.g. `--no-amenders`) for callers who want body-producer-only.
- Mbsync hook `convert → amenders → index` falls out of default-on behaviour.
- Land the extraction-cache (Session 9d design) as part of this work; zkm-ner is its first consumer.

### Item 3 — Library / model choice

Candidates:

- **(L1) spaCy per-language**: `de_core_news_sm` + `en_core_web_sm`, with langdetect to route. Mature, fast, label set: PERSON, ORG, LOC, MISC.
- **(L2) spaCy multilingual**: `xx_ent_wiki_sm` (~11MB, language-agnostic). Single model, weaker on email-style text and conversational German.
- **(L3) GLiNER multilingual**: ~600MB, transformer, zero-shot label-list driven. 30–50ms/doc CPU. Custom label sets without retraining.
- **(L4) Pattern-based bootstrap**: regex for emails/URLs/phone + a hand-curated gazetteer for known orgs. Zero ML overhead, brittle, but a good *baseline*.

**Mira:** Label set: spaCy's German labels are PER, ORG, LOC, MISC. GLiNER lets you specify labels at runtime, so you can ask for `[person, organisation, place, product, support_role]` and get role-tagged spans the amendment contract already supports. Real architectural fit.

**Archie:** Hold on — read the spec carefully. `entities` set-union with role-tagged dedup means each entity carries a role tag (`{type: person, value: Frank}`). spaCy's PER tag maps cleanly. The GLiNER advantage is *finer* labels, but that's not the contract — the contract uses the spaCy label set basically verbatim. So GLiNER's flexibility is unused unless we extend the contract.

**Riku:** Per-language routing with langdetect is fragile in mixed-language corpora — Tobias has emails 80% German with English signature blocks, English cloud bills with German VAT footers. Doc-level langdetect gets it wrong on the boundary → wrong language model on half the entities → garbage output. *Sentence-level* routing is the fix, but it doubles the model-loading footprint and adds complexity.

**Petra:** Reframes: this is a pilot. L1 + L4 in parallel — patterns catch the deterministic stuff, spaCy catches the rest. No multi-model routing, no GLiNER tax. Run for 2 weeks. *Then* decide if GLiNER's flexibility is worth 600MB.

**Mira:** Pushes back. spaCy small models on conversational German drop to ~70% F1 — the pilot will look bad and you'll blame the framing. GLiNER on the same text holds ~85% because transformer-based.

**Riku:** Cache angle: with the extraction-cache landing, model swaps are cheap — cache key includes model_name+version, so swapping spaCy → GLiNER later is "rerun on full corpus, cache fills, done in 45 min". Argues *against* over-thinking the choice. Pick something. Switch later.

**Archie:** Concrete proposal:
- Default: spaCy `de_core_news_sm` for body lang=de, `en_core_web_sm` for body lang=en.
- Trust `lang:` frontmatter if zkm-eml writes it (doesn't yet — would need to). Fall back to `langdetect` doc-level (accept 70%-on-mixed limitation explicitly).
- Pattern overlay: extract emails (`type: email_address`), URLs (`type: url` + domain → `org_hint`), small gazetteer of known orgs. Run before NER, dedupe spans.
- Model knob: `ZKM_NER_MODEL=spacy|gliner` env var, defaults spaCy. GLiNER as `zkm-ner[gliner]` optional extra.

**Mira:** Sensible MVP. Withdraws GLiNER push for v1.

**Petra:** Two weeks of spaCy. Then decide.

**Tobias:** spaCy + patterns + GLiNER opt-in. Pattern overlay also includes phone numbers, social handles (discord/telegram/steam), LinkedIn URLs, GitHub profiles.

**Decision:**
- v1 model stack: spaCy `de_core_news_sm` + `en_core_web_sm`, doc-level langdetect routing, accept mixed-language weakness explicitly.
- GLiNER multilingual ships behind `ZKM_NER_MODEL=gliner` and `zkm-ner[gliner]` optional extra; same amendment output schema.
- Pattern overlay (`type: <kind>`):
  - `email_address` (email regex)
  - `phone_number` (libphonenumber via `phonenumbers`, default region CH)
  - `url` + `domain` (extract domain → `org_hint`)
  - `social_handle.<discord|telegram|steam|...>`
  - `linkedin_profile`, `github_profile` (URL patterns → identity-strong)
  - `org_gazetteer` (Proton, Stadtwerke, Konstanz utilities, banks; user-editable in zkm-ner repo)
- Pattern overlay runs before NER; NER spans overlapping pattern spans are dropped (patterns win for those types).

### Item 4 — Scope boundary: extraction vs. resolution

**Riku (opening):** Tobias's pattern list crosses a line. `linkedin_profile` and `github_profile` are *identity-strong* — their explicit purpose is "this URL identifies one specific human". Extracting them as untyped strings leaves signal on the floor. But *using* the signal means resolution, a much bigger problem. Where do we draw the line?

**Mira:** The face-detection vs face-recognition discovery applies exactly. Three sub-problems:
1. **Span normalisation**: "Frank Müller" / "F. Müller" / "Müller, Frank" → canonical string.
2. **Cross-mention clustering**: same name across docs, same person? Often yes, sometimes no.
3. **Identity-strong linking**: linkedin URL X + github profile Y → `person_42`. Requires user enrolment.

(1) in scope for any sensible v1. (2) and (3) out of scope for Phase 2.5. (3) is Phase 4.

**Archie:** Concrete contract for v1: NER emits one entity record per *mention*, no cross-document linking:

```yaml
entities:
  - {type: person, value: "Frank Müller"}
  - {type: email_address, value: "frank.mueller@proton.me"}
  - {type: linkedin_profile, value: "https://linkedin.com/in/fmueller"}
```

`value` is a normalised string (lowercase emails, canonical URL form). No `id:` field, no cross-doc linking, no `same_as:`. The amendment contract's role-tagged dedup handles set-union *within* a doc; *across* docs is the WebUI's problem (Phase 3 entity-model.md live-aggregation).

**Petra:** Hard cap on pattern scope. Each pattern = one regex + one optional library. No country-of-origin disambiguation. No "github org vs user" detection. If the pattern fires, capture verbatim; the WebUI / future Phase 4 figures out semantics.

**Riku:** Pushes once more — what about the *gazetteer*? If gazetteer has "Proton" and the body mentions "Proton", the entry resolves the mention to a canonical org name. Mini-resolution. In scope?

**Archie:** Yes, but bounded: gazetteer match → emit `{type: org, value: "<canonical>"}` from gazetteer. Typed dictionary lookup, not entity resolution proper. Petra's hard cap holds.

**Mira:** Forward-looking note: once we have `linkedin_profile` and `github_profile` as identity-strong signals, Phase 4 memory compaction will need them to build canonical person files. We should write entities with stable `value:` strings (canonical URL form, lowercase email) so later clustering can do exact-match grouping without re-parsing. **Don't normalise lossily**.

**Petra:** Signs off on extraction-only scope.

**Riku:** Explicit out-of-scope flag: **PII redaction**. Entities will surface phone numbers, emails, GitHub usernames in a git-tracked, eventually-public-or-shared knowledge store. Tobias' privacy-audit position is low-paranoia for personal projects, but worth a TODO + design note.

**Tobias:** Option 1 (extraction + gazetteer only) for now. But three constraints carried forward:
1. **Name alone is NOT a UID** — Tobias knows multiple people with identical first+last names.
2. **Manual merge over heuristic merge** — uncertain identity matches should be a manual review later, not an automatic clustering pass.
3. **Co-reference within a doc** is interesting (e.g. "Mr. Smith, please reach out to Mr. Anderson…"; "@Neo … when *he* contacts you" reveals Neo ≡ Thomas Anderson within one message) — *not* in scope for v1, but should not be designed away.

PII redaction: TODO + design note.

**Decision:**
- v1 = extraction + gazetteer canonicalisation only.
- Entity records carry no identity. `value` is a *mention string*, not a UID. No `id:` / `same_as:` / cross-doc clustering.
- The schema permits a future identity layer: an opt-in sidecar (`<doc>.entities.json` or store-level `<store>/.zkm-state/entity-merges.jsonl`) can later record manual merges (`mention X in doc Y == person_42`) without re-touching the per-doc `entities:` list. Manual merge tooling deferred to Phase 4.
- Co-reference resolution (intra-doc pronoun → name) explicitly out of scope for v1. spaCy has experimental coref support; revisit after pilot.
- PII redaction: open TODO + one-paragraph design note in `docs/entity-model.md` framing the question (config-driven entity-type denylist for export? per-share-target redaction? defer concrete decision until first sharing scenario).

## Decisions

1. **Phase placement**: NER promoted to Phase 2.5, lands *before* whatsapp scoping (Session 15 deferred behind it).

2. **Trigger model**: dedicated amendment plugin `zkm-ner` (mirrors zkm-notmuch shape). `zkm convert <plugin>` runs amenders by default; `--no-amenders` flag opts out. Mbsync hook chain becomes `convert → amenders → index` via the default-on behaviour.
   *Out of scope*: inline NER in body-producer plugins; core `zkm enrich` command.

3. **Extraction-cache**: lands alongside zkm-ner (Session 9d design becomes implementation). Cache key: `(sha256_of_body, extractor_name, model_name, model_version)`. Per-CAS-object, multi-stage cache as designed in `docs/object-storage.md`. zkm-ner is first cache consumer; future content extractors (zkm-receipt, etc.) reuse.
   *Out of scope*: making notmuch tags use the extraction-cache (notmuch tags mutate; not a fit).

4. **Library / model stack**:
   - Default: spaCy `de_core_news_sm` + `en_core_web_sm`, doc-level `langdetect` routing. Mixed-language weakness accepted.
   - Optional extra: GLiNER multilingual via `pip install zkm-ner[gliner]` + `ZKM_NER_MODEL=gliner`.
   - Pattern overlay (runs before NER, patterns win on overlap): `email_address`, `phone_number` (libphonenumber, default region CH), `url`, `domain` (→ `org_hint`), `social_handle.{discord,telegram,steam,...}`, `linkedin_profile`, `github_profile`, user-editable gazetteer (`zkm-ner/gazetteers/orgs.yaml`) with canonical-form mapping.
   *Out of scope*: country-of-origin disambiguation, github-org-vs-user detection, sentence-level language routing, fine-grained ML labels beyond the spaCy PER/ORG/LOC/MISC vocabulary.

5. **Scope boundary**: extraction + gazetteer canonicalisation only.
   - One entity record per mention. `value` is a *mention string*, never a UID.
   - **Hard architectural assertion**: name alone is NOT a unique identifier — known cases of identical first+last name persons.
   - **Manual-merge over heuristic-merge** for identity resolution (Phase 4 tooling, design only here).
   - Co-reference within doc deferred to v2; spaCy experimental coref evaluated post-pilot.
   *Out of scope*: cross-doc clustering, identity-strong linking, intra-doc pronoun coref.

6. **PII**: open TODO + one-paragraph design note in `docs/entity-model.md`. No concrete redaction policy yet.

## Action items

- [ ] **N1.** New plugin repo `plugins/zkm-ner/` (mirrors zkm-notmuch layout). `plugin.yaml` declares `creates_dirs: []` (amender, no body output), `kind: amender`. Initial `pyproject.toml` `version = "0.1.0"`, `requires zkm>=0.2.0,<0.3.0`. Bump-and-tag rule applies. Contract: `convert(store, config) -> []` for any input; emits amendment records via `zkm.amendments`. (file: `plugins/zkm-ner/`)
- [ ] **N2.** Implement extractor pipeline in `plugins/zkm-ner/src/zkm_ner/extract.py`:
  - `extract(body: str, lang: str | None) -> list[Entity]`
  - Pattern overlay first (`patterns.py`: email/phone/url/social/linkedin/github + gazetteer loader)
  - spaCy NER second (`spacy_backend.py`); GLiNER backend behind optional import (`gliner_backend.py`)
  - Span-overlap dedup: pattern wins on overlap. Contract: deterministic output for same `(body, model_name, model_version)`. (file: `plugins/zkm-ner/src/zkm_ner/extract.py`, ~250 LOC + tests)
- [ ] **N3.** Wire extraction-cache (Session 9d design implementation). New `src/zkm/extraction_cache.py` in core: per-store cache at `<store>/.zkm-state/extraction-cache/`, keyed by `(sha256_of_body, extractor_name, model_name, model_version)`, JSON value = entity list. Atomic write, schema version field. Contract: zkm-ner reads cache before running extractor; cache miss runs extractor and writes back. Tests cover hit/miss/version-bump invalidation. (file: `src/zkm/extraction_cache.py`, ~150 LOC + tests)
- [ ] **N4.** zkm-ner amendment writer: for each md, build amendment record `{key: {sha256: ...}, fields: {entities: [...]}, emitted_by: "zkm-ner", emitted_at: <iso8601>}`, hand to `zkm.amendments.merge_records`. Set-union dedup on `(type, value)` tuple. Contract: re-running zkm-ner on already-enriched corpus → 0 new amendments (cache hit + idempotent merge). (file: `plugins/zkm-ner/src/zkm_ner/convert.py`, integrates with `zkm.amendments`)
- [ ] **N5.** Default-on amender chain in core `zkm convert`. New flag `--no-amenders` (default: amenders on). Discovery: `plugin.yaml` with `kind: amender` is auto-included after the body-producer plugin in `convert.py`. Existing `zkm convert <plugin>` runs body producer + all amenders by default. (file: `src/zkm/convert.py:cmd_convert`, ~30 LOC + tests)
- [ ] **N6.** Update mbsync hook (`plugins/zkm-eml/hooks/post-commit`) — no change needed if `--no-amenders` is opt-out (default-on inherits). Verify in journald that hook now runs zkm-ner after zkm-eml convert. (file: `plugins/zkm-eml/hooks/post-commit`, verify only)
- [ ] **N7.** Pattern overlay tests: emails, phone numbers (DE/CH formats), URLs, domains-to-org-hint, all six social handle subtypes, LinkedIn profile, GitHub profile, gazetteer canonicalisation. (file: `plugins/zkm-ner/tests/test_patterns.py`, ~20 cases)
- [ ] **N8.** spaCy backend tests: round-trip on a German fixture, round-trip on an English fixture, mixed-language fallback (accept doc-level routing limitation). (file: `plugins/zkm-ner/tests/test_spacy_backend.py`)
- [ ] **N9.** End-to-end pilot script (`plugins/zkm-ner/scripts/pilot.sh`): runs against the live ~/knowledge store, prints histogram of entity types + counts + top-N by frequency, dumps low-confidence spans to a review file. Two-week pilot window logged. (file: `plugins/zkm-ner/scripts/pilot.sh`)
- [ ] **N10.** Documentation: `docs/ner.md` covering the architectural decisions from this meeting (pattern overlay categories, amender-not-producer rationale, cache shape, scope boundary, name-is-not-UID assertion). Update `docs/entity-model.md` Phase 2.5 section. Update `CLAUDE.md` Phase 2.5 sequencing. (files: `docs/ner.md` (new), `docs/entity-model.md`, `CLAUDE.md`)
- [ ] **N11.** PII redaction TODO + design note paragraph in `docs/entity-model.md` framing the question. No implementation. (file: `docs/entity-model.md`)
- [ ] **N12.** TODO.md update: add Phase 2.5 NER section with N1–N11 broken into checked-off-able items; reorder so NER precedes Session 15 (whatsapp scoping). (file: `TODO.md`)
- [ ] **N13.** Update `docs/meeting-notes/meeting-style.md` "Past meetings" index with this meeting note.

## Out of scope (explicit)

- Inline NER in body-producer plugins (zkm-eml, zkm-photo, zkm-pdf, zkm-scan).
- Core `zkm enrich` command as alternative to amender plugin model.
- Cross-document entity clustering, automatic identity resolution, fuzzy person merging.
- Intra-doc pronoun co-reference resolution.
- Concrete PII redaction policy (TODO only).
- GLiNER as default; sentence-level language routing; fine-grained ML labels beyond spaCy's vocabulary.
- Manual-merge tooling (Phase 4, design only here).
- Country-of-origin disambiguation, github-org-vs-user detection.
