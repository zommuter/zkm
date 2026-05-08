# 2026-05-08 — Information flow, content classification, and photo enrichment

**Attendees:** Tobias (product owner), Archie (architect), Riku (devil's advocate), Petra (productivity), **Mira (multimodal ML, new)**, **Flora (information flow, new)**
**Topic:** Resolve where content-type classification ("is this a receipt?") and photo enrichment ("who is in this photo? are these slides?") live — and whether last meeting's fan-out abstraction survives.

## Agenda

1. Onboard Mira and Flora; state their lenses.
2. Is "receipt" (or "vacation photo", or "talk slide") a *tag* on a format-plugin's md, a *peer plugin* in the fan-out, or a new abstraction layer?
3. For photos with people / slides on screen: does enrichment land in `zkm-photo` now, or is it Phase 3 entity work?
4. Does last meeting's "fan-out, plugins self-gate" survive content-classification, or do we need plugin-to-plugin handoff after all?

## Discussion

**Tobias:** Last meeting we picked fan-out: every plugin scans `inbox/`, decides whether to emit md, dedupes via CAS. But we sidestepped a real question. A JPEG of a receipt is a *receipt*, not a "photo". A PDF of a receipt is also a receipt. A JPEG of a vacation is a photo. A JPEG of a talk speaker + slides is *two* useful things — a person, and slides that maybe match a PDF I already filed. EXIF won't tell me that. So: do format-plugins (jpeg, pdf) emit content-tags? Do they route to content-plugins? Or is "receipt" just a tag that any plugin can stamp on?

**Mira:** [new — multimodal ML lens] Three things to frame this, since classification cost varies by 100× across the questions you're asking:

- *"Is this a receipt?"* — 95%+ zero-shot accuracy with a 2B VLM (Qwen2-VL-2B, Florence-2). ~1–2 s/image on CPU, <100 ms on GPU. Cheap.
- *"Who is in this photo?"* — two problems. Face *detection* is cheap and deterministic. Face *recognition* needs a per-user enrollment set; without one you get clusters ("person_A appears in 12 photos"), not names. Privacy axis is non-trivial.
- *"Are these slides, and do they match a PDF I have?"* — perceptual hash of the slide region + OCR overlap with the PDF text. Different stack from VLM classification — closer to image search.

Lumping these as "AI photo enrichment" is a category error. Different costs, different failure modes, different privacy stories.

**Flora:** [new — information-flow lens] Two reference patterns from analogous systems:

- *MIME / Postfix* — content-type is metadata on the message; multiple consumers subscribe to types. Routing is still fan-out, but the *type* is set upstream by a typed parser.
- *Apache Tika / unstructured.io* — one component does extract + classify and emits a typed record; consumers filter by type. "Parse once, classify many."

zkm's last meeting picked fan-out *without* a content classifier. That's fine for *format-disjoint* consumers (zkm-photo writes EXIF md; zkm-pdf writes text md — they don't overlap because they read disjoint extensions). It doesn't extend to *content-overlapping* consumers, where a `zkm-receipt` wants the same source whether it's a JPEG or a PDF.

**Riku:** Hold. "VLM classifier in the pipeline" is a big claim. Two challenges:

1. *Asymmetric error cost.* Mira says 95% — what's the 5%? A vacation photo flagged as receipt is tag-noise. A receipt flagged as vacation costs the user a tax document. The error is asymmetric and the user pays it.
2. *Dependency footprint.* `CLAUDE.md` says "minimize dependencies, stdlib > small lib > framework." A VLM dep is the opposite of that — model files, GPU optionality, version pinning. Are we sure this is now-work and not Phase 3?

**Archie:** Anchoring in current code:

- `zkm.cas.write_object` + `zkm.sidecar.merge_producer` already support multiple producer-plugin names per CAS object (last meeting's decision). So "zkm-photo + zkm-receipt both reference the same JPEG" is already legal.
- There's no extraction-cache. If `zkm-pdf` extracts text from a PDF and `zkm-receipt` later needs that same text, today `zkm-receipt` would re-extract.
- There's no plugin-to-plugin handoff. Plugins read `inbox/`, write to their owned dir, exit. `zkm-photo` cannot say "I think this is a receipt — `zkm-receipt`, take it from here."

Three options:

| Option | Where classifier lives | New abstraction | Cost |
|---|---|---|---|
| **A. Tag-only** | Inside each format plugin (zkm-photo, zkm-pdf each call a classifier) | None — frontmatter `tags` carries content-type | Classifier dep duplicated in every format plugin |
| **B. Peer content-plugin (fan-out extended)** | `zkm-receipt` is a peer plugin scanning inbox; runs its own classifier; emits `documents/receipts/.../md` regardless of source format | None *new* control-layer; data-layer needs an extraction cache on the CAS sidecar so peers don't re-OCR | Lightest if extraction-cache lands; without it, O(plugins × inbox) |
| **C. Pipeline with declared edges** | Format plugins emit "candidate" records; content plugins consume those; core orchestrates ordering | New: plugin DAG, candidate-record schema, ordering rules | Heavy — last meeting deferred this on N=2 |

**Mira:** Note on Option B's hidden cost. Re-OCR is the obvious one, but the deeper issue is that "extraction" is graded — `pdfplumber` text → `pypdf` fallback → `tesseract` OCR → `Qwen2-VL` description. Each is more expensive and each is something a downstream content-plugin might want. Without a cache, every content-plugin re-runs the ladder.

**Flora:** Which means Option B isn't "no new abstraction" — it's "no new *control-layer* abstraction, but a new *data-layer* one: an extraction cache on the CAS sidecar." That's actually a lighter answer than Option C.

**Petra:** N=2 check on extraction-cache:

- `zkm-pdf` text + `zkm-receipt` re-using it = pair 1.
- `zkm-scan` OCR + `zkm-receipt` re-using it = pair 2.
- `zkm-photo` EXIF + `zkm-talk-photo` re-using it = pair 3.

Passes N=2. Real abstraction, not speculation. But — extraction-cache is *data layer* (lives in the CAS sidecar). Plugin-pipeline is *control layer* (deferred). Don't conflate.

**Tobias:** I'm leaning C, but not 100%. And — connected — does zkm-eml track tags from notmuch? `tags.dump`, the `anew` workflow?

**Archie:** Just checked. zkm-eml does NOT pull notmuch tags. `zkm-eml/src/zkm_eml/source.py:10` explicitly prunes `.notmuch` directories during the maildir walk. `zkm-eml/src/zkm_eml/frontmatter.py:32` initializes `tags: []` empty for every message. The `tags` field is a placeholder zkm-eml never fills.

So a notmuch-indexed mailbox has rich tags in `~/mail/.notmuch/xapian/` that never reach the markdown. That is a real gap — and it's *not* a content-classifier gap.

**Flora:** This is exactly the case my Tika/MIME parallel was poorly fitted to. notmuch is an *external indexer* with its own state; the user re-tags *after* zkm-eml runs. None of A/B/C in their current form addresses this cleanly:

- **A** (tag-only-in-format-plugin) → zkm-eml reads notmuch's xapian DB at convert time. But user re-tags later; re-running zkm-eml is heavy.
- **B** (peer + extraction-cache) → a `zkm-notmuch` peer plugin. But it would need to *mutate the md frontmatter of files zkm-eml already wrote*. zkm has no contract for that. Today, plugins write their own dirs; nobody amends another plugin's output.
- **C** (pipeline + DAG) → a strict DAG doesn't model this either: notmuch's tag state *evolves* after the DAG runs once.

What's actually missing is a *frontmatter-amendment* contract: a plugin declares it emits **amendments** to existing md (keyed by `message_id`, `sha256`, or path), and core merges them at convert/index time.

**Mira:** If amendment exists, every classifier I described becomes an amendment too. "I think this is a receipt" → amend `tags: [receipt]`. "I see person X" → amend `entities: [person_X]`. Phase 3 NER → amendments. The amendment contract is a unified pipe; the classifier is just one user of it.

**Riku:** Two challenges to amendment-as-abstraction:

1. *Mutation of existing md* breaks an invariant from `docs/messaging-spec.md` — md is the source of truth, written by exactly one plugin. If multiple plugins amend, who wins on conflict? What's the version / audit story? Frontmatter-merge looks lightweight in conversation and gnarly in implementation (yaml round-trip is famously lossy).
2. *N=2 on amendment*: notmuch→eml = pair 1. Phase 3 NER → any md = pair 2. classifier → format-plugin's md = pair 3. Passes — but the *contract* is non-trivial. I want it written before any amender ships.

**Petra:** This changes the meeting's shape. We're no longer picking A/B/C for the *content classifier*. We're identifying **two independent additive abstractions**:

| Abstraction | Layer | What it does | N=2 evidence |
|---|---|---|---|
| **Extraction cache** | Data — CAS sidecar | Multi-stage extraction stored per CAS object; peers reuse upstream extraction (pdfplumber → tesseract → VLM ladder) | pdf+receipt; scan+receipt; photo+talk-photo |
| **Frontmatter amendment** | MD — key-matched merge | Plugin emits amendments to existing md keyed on `message_id` / `sha256` / path; core merges with declared per-field rules | notmuch→eml; NER→any; classifier→format-plugin |

Both pass N=2. Both are **additive** to last meeting's fan-out — neither overrides it.

**Flora:** Under this lens, "C: declared edges" becomes unnecessary. Plugins still fan out; the *outputs* (extracted text, frontmatter amendments) flow through well-typed sidecar / frontmatter merges. No DAG. No control-layer abstraction at all. The information-flow problem dissolves into two narrow data-shape contracts.

**Archie:** Concretely:

- `zkm-receipt` is a peer plugin (B). Reads inbox, classifies, emits *either* its own md *or* a tag-amendment to zkm-photo / zkm-pdf — TBD per content.
- `zkm-notmuch` is a peer that reads `~/mail/.notmuch` and emits **amendments** keyed by `message_id` → `tags`.
- Phase 3 NER is a peer that reads md, runs entity extraction, emits **amendments** keyed by md path → `entities` / `tags`.

Three consumers of amendment. Strong N=2.

**Riku:** I'll buy this *iff* the amendment merge semantics are drafted in `docs/plugin-spec.md` **before** the first amender ships. Per-field rules: `tags` is set-union; `entities` is set-union (with role-tagged dedup); scalars are last-write-wins-with-source-attribution; lists with structure (e.g. `participants`) need explicit merge keys.

**Tobias:** Accept the reframe — extraction-cache + amendment, drop C.

**Archie:** Moving to agenda item 3 — photo enrichment. Under the new lens, what's `zkm-photo`'s first-ship scope?

**Mira:** Three enrichment dimensions, three separate stacks:

1. *Content tag* (`vacation`, `receipt`, `screenshot`, `whiteboard`, `talk-slide`) — VLM zero-shot classification. ~1–2 s/image CPU. One model dep.
2. *People* (`entities: [person_A, person_B]`) — face detection (MediaPipe / RetinaFace, deterministic, no enrollment) → face recognition (needs enrollment + privacy story). Two-stage.
3. *Slide ↔ PDF match* (`slide_match: documents/slides/…`) — perceptual hash of slide region + OCR overlap with stored PDF text. Cross-document join. Different stack entirely.

None of these belong inside `zkm-photo` if amendment is the contract. Each becomes a peer plugin: `zkm-img-classify`, `zkm-faces`, `zkm-slide-match`. They emit amendments to whichever md the source ended up in.

**Riku:** We just defined a `zkm-photo` and you're already saying "ship it minimal, the real value is in three downstream plugins that don't exist yet." Smell of premature decomposition. What's the minimal `zkm-photo` first-ship that's actually useful on its own?

**Petra:** Scope-cut for `zkm-photo` first ship:

- EXIF date → `date`
- EXIF GPS → `location` (string only, no reverse-geocoding — deferred last meeting)
- EXIF camera model → `tags: [<camera-model-slug>]`
- sha256 + CAS dedup
- Thumbnail link in md body

No classifier, no faces, no slide-match. Useful on its own as "every photo I have, searchable by date/place/camera, dedup'd."

**Mira:** Agreed for first ship. But amendment as a contract needs at least one amender to test it. Propose `zkm-img-class` v0.1 — rule-based, no model dep (aspect ratio, file size, EXIF flash, RGB histogram). ~80% on easy cases. Ships as test-mule amender; VLM upgrade is v0.2, no contract change.

**Archie:** Cost: amendment contract (~1 spec section) + `zkm.amendments` helper (~200 LOC) + `zkm-img-class` v0.1 (~150 LOC). Total ~400 LOC + 1 spec section over last meeting's plan.

**Tobias:** Amendment contract empty-handed; first amender is `zkm-notmuch`. Skip `zkm-img-class` for Phase 2.5 — content classifiers are Phase 3 alongside NER and slide-match.

**Archie:** Clean. Sketch of `zkm-notmuch`:

- Reads `~/mail/.notmuch/` xapian DB via the `notmuch` Python binding (or `notmuch dump --format=batch-tag` subprocess fallback for portability).
- For each tagged message: looks up the corresponding md in `mail/messages/` by `message_id`.
- Emits an amendment record: `{key: {message_id: "<id>"}, fields: {tags: [<tag1>, <tag2>, ...]}}`.
- `zkm.amendments` merges via set-union into the existing md's `tags` frontmatter field.
- Idempotent: re-running re-applies the current xapian tag state.

**Mira:** Note: zkm-notmuch reads xapian, not content — no extraction-cache needed. The three Phase 2.5 format plugins (photo, pdf, scan) read disjoint formats — no shared extraction in Phase 2.5 either. Extraction-cache **stays as a design note in `docs/object-storage.md`, not implementation**, until the first content-plugin (zkm-receipt) lands in Phase 3.

**Petra:** Net Phase 2.5 increment over last meeting: 1 new pre-flight spec (amendment contract), 1 design note (extraction-cache, spec-only), 1 new core lib (`zkm.amendments`), 1 new plugin (`zkm-notmuch`), 1 scope-cut (`zkm-photo` shrinks). ~350 LOC + 2 spec sections. No model deps. No control-layer abstractions.

**Riku:** Last challenge — invariant break. zkm-eml writes `tags: []` empty today. `zkm-notmuch` mutates that. Are we OK with "two plugins write to the same md"?

**Archie:** The contract evolves: **md body** stays single-producer (zkm-eml owns the body). **md frontmatter** is multi-producer via amendments, with explicit per-field merge rules. The amendment record carries an `emitted_by` attribution stored in a sidecar so you can trace which plugin wrote which field.

**Flora:** It generalizes the existing `producers[]` story on the CAS sidecar: binary-side multi-producer was already legal; we're now legalising md-frontmatter-side multi-producer with the same hygiene (attribution + merge rules).

**Petra:** Out of scope for this meeting:

- VLM-based content classification (Phase 3 with NER).
- Face detection / recognition (Phase 3, with privacy story).
- Slide ↔ PDF perceptual-hash matching (Phase 3 cross-doc joins).
- Extraction-cache *implementation* (design note Phase 2.5; implementation when first content-plugin lands).
- Plugin DAG / declared edges / pipeline orchestration — fully dissolved by amendment + extraction-cache combo, no longer a live question.
- WhatsApp / Threema / Signal / Telegram / chatlog plugins — still deferred to own scoping session.

## Decisions

- **Drop the A/B/C framing** — replaced by two additive abstractions on top of last meeting's fan-out:
  1. **Extraction cache** on CAS sidecar (data-layer). *Design only* in Phase 2.5; implementation when the first content-plugin (zkm-receipt) lands in Phase 3.
  2. **Frontmatter amendment** contract (md-layer, key-matched merge). Lands in Phase 2.5 with `zkm-notmuch` as first amender.
- **No control-layer abstraction** (no plugin DAG, no declared edges, no candidate-record schema). C is dissolved, not just deferred.
- **`zkm-photo` first-ship scope cut**: EXIF date, EXIF GPS string (no reverse-geocode), EXIF camera-model → tag, sha256 / CAS dedup, thumbnail link in body. No classifier. No face detection.
- **`zkm-notmuch` as first amender**: reads xapian DB, looks up md by `message_id`, emits set-union amendment to `tags`. Idempotent on re-run.
- **md frontmatter is multi-producer** under the amendment contract; **md body remains single-producer**. Per-field merge rules are part of the spec.
- **Phase 3 absorbs**: VLM content-classification, face detection / recognition, slide ↔ PDF perceptual-hash matching, and extraction-cache implementation.
- **WhatsApp deferred** unchanged from last meeting (its own scoping session).
- **zkm-eml notmuch tags gap confirmed**: `zkm-eml/src/zkm_eml/source.py:10` prunes `.notmuch`; `frontmatter.py:32` emits `tags: []` empty. xapian tag state never reaches the md. `zkm-notmuch` closes this gap.

## Action items

- [ ] **Session 9c (pre-flight)**: write the amendment contract section in `docs/plugin-spec.md`. Contract: per-field merge rules (`tags` set-union; `entities` set-union with role-tagged dedup; scalars last-write-wins-with-`emitted_by`-attribution; structured lists need explicit merge keys); amendment record schema (`{key: {message_id|sha256|path: ...}, fields: {...}, emitted_by: <plugin-name>, emitted_at: <iso8601>}`); core merge engine semantics; queue-if-md-missing behaviour. Round-trip test: zkm-eml writes md with `tags:[]`; an amendment with `tags:[bill]` lands; merged md shows `tags:[bill]` with attribution sidecar entry. (file: `docs/plugin-spec.md`)
- [ ] **Session 9d (pre-flight)**: design note for extraction-cache in `docs/object-storage.md`. Contract: cache shape (per-CAS-object, multi-stage, per-extractor), planned merge with `producers[]` sidecar, deferred until first content-plugin. No implementation. (file: `docs/object-storage.md`)
- [ ] **Session 10 (core lib)**: `zkm.amendments` module — read amendment records, key-resolve against md tree, merge per field rules, write back, track attribution sidecar. ~200 LOC + tests. (file: `src/zkm/amendments.py`)
- [ ] **Session 11**: build `zkm-photo` per Petra's scope-cut list. Contract: `convert(store, {PHOTO_SOURCE_DIR}) -> [photos/...md]`; idempotent; uses only `zkm.{atomic,cas,sidecar,inbox,hashing}`; emits no semantic tags beyond camera-model. (separate repo `~/src/zkm-photo/`)
- [ ] **Session 12**: `zkm-pdf` (text-only). Unchanged from last meeting. (separate repo)
- [ ] **Session 13**: `zkm-scan` (OCR). Unchanged from last meeting. (separate repo)
- [ ] **Session 14**: `zkm-notmuch` — first amender. Contract: reads `~/mail/.notmuch` xapian DB, emits `{key: {message_id}, fields: {tags: [...]}}` amendments per message; merges via `zkm.amendments`; idempotent on re-run; round-trip test against a fixture xapian DB. (separate repo `~/src/zkm-notmuch/`)
- [ ] **Session 15 (scoping, not implementation)**: `zkm-whatsapp` scoping meeting. Unchanged from last meeting. (file: `docs/meeting-notes/YYYY-MM-DD-whatsapp-scope.md`)
