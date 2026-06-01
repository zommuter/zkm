# 2026-06-01 — Contacts & calendar plugin(s): fetch vs process

**Started:** 2026-06-01 13:34
**Session:** 4226ed8d-b848-4024-992c-933c3efec45a
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🔐 Dario (E2E-PIM/DAV/fetch lens), 🗺️ Flora (content-type vs file-format routing), 🧬 Nora (IE/NER typology lens)
**Topic:** Should zkm gain contacts/calendar plugin(s), and where is the fetch-vs-process boundary — does a calendar plugin provide Proton/Gmail integration or expect iCal files?

## Agenda
1. Fetch-vs-process boundary: ingest-only or bundled source integration?
2. One plugin or two: `zkm-vcard` + `zkm-calendar` or combined?
3. zkm-vcard document shape & NER support
4. zkm-calendar (deferred build) + eml interface + temporal NER 3-layer design
5. Sequencing, phase placement, naming, prefixes

## Discussion

### Prior art surfaced at audit
- proton-moresync (2026-05-29) already decided the fetch-vs-ingest split: a Go CLI (`go-proton-api`) plays the mbsync role — fetch + decrypt + emit a git-versioned tree of vanilla RFC 6350 `.vcf` / RFC 5545 `.ics` files + a `.meta/<uid>.json` Proton-specifics sidecar. zkm plugins play the zkm-eml ingest role. Contract is the directory tree, source-agnostic ("Proton today, exported Google tomorrow"). Producer is design-complete but not built (spike not yet run).
- `docs/messaging-spec.md:41-53` already maps iCal `ORGANIZER`/`ATTENDEE`/`PARTSTAT`/`ROLE` to participant roles `organizer`/`attendee`/`optional`/`invitee`. Calendar events were anticipated as message-like.
- `TODO.md:81` (social-network scoping) flagged: does profile/identity data go into `entities[]` (γ schema) or its own document type? Contacts answer this question.

### Agenda 1 — Fetch-vs-process boundary

🔐 **Dario:** The fetch layer is irreducibly per-source and often non-Python. Proton has no CalDAV — E2E-encrypted, server-blind, only viable client is Go. Google CalDAV needs OAuth. Generic CalDAV needs DAV auth. Bundling fetch in a zkm plugin commits zkm to maintaining 3+ auth/transport stacks — one impossible in Python. The standard-file boundary is the only contract stable across all sources.

🗺️ **Flora:** File-format is the interface, source is an implementation detail behind it. zkm has never fetched — mbsync→zkm-eml was always the pattern.

✂️ **Petra:** Ingest-only means no credentials, tiny plugin, one-session build. Bundling fetch turns it into an open-ended maintenance sink.

🏗️ **Archie:** The decision is ingest-only. The plugin reads a `source_dir` tree of `.vcf`/`.ics` files.

**Tobias's refinement:** The plugin is ingest-only, but fetch is not forbidden at the system level — it just doesn't belong in individual plugins, nor should it require per-source systemd sprawl. A future **core `zkm fetch`** command orchestrates configured external tools (proton-moresync / Takeout / vdirsyncer / CalDAV). Config maps `source → external command + output dir`; `zkm fetch <source>` shells out, deposits standard files, `zkm convert` ingests. This is the mbsync-equivalent lever lifted into core.

### Agenda 2 — One plugin or two?

🏗️ **Archie:** Same source tree, two content-types, two document shapes — calendar is message-like (participants, threads), contacts are person records. proton-moresync names them `zkm-vcard` and `zkm-calendar`.

🗺️ **Flora:** One plugin *can* fan out by extension. Shared surface is only: parser dependency (vobject parses both), UID dedup, PHOTO/ATTACH→CAS.

✂️ **Petra:** Two repos = 2× git/pyproject/test suite/version/prefix overhead for a solo author.

😈 **Riku:** Calendar mapping is settled; contacts shape is the open agenda item. Bundling them drags calendar release cadence. Also: user may want calendar-only.

🗺️ **Flora:** Clean middle: build the settled one first, defer the open one — without committing to "one combined plugin." Personas converged on zkm-calendar first (settled), zkm-vcard second.

**Tobias flipped the order:** vcard first — contacts supply *authoritative* person/email/org data, structural-first material that strengthens NER immediately (production recipe per n9d-gate-c SOTA finding). Calendar gained an open interface question (eml overlap). The maturity argument inverting.

**Calendar↔eml interface flag (load-bearing):** event-invitation mails carry `.ics` parts (`METHOD:REQUEST`) — overlap with zkm-eml attachment handling. Plus a fuzzier class: implicit deadlines / upcoming events mentioned in mail bodies but never formally registered as VEVENTs — NER territory, not iCal parsing.

### Agenda 3 — zkm-vcard contact shape

🧬 **Nora:** zkm has no standalone entity store — entities live in documents. So a contact must be a document.

🗺️ **Flora:** `contacts/<slug>.md`, one per vCard `UID`. Body = human-readable card (FN, ORG, TITLE, emails, phones, ADR, NOTE) → BM25/dense-searchable. `PHOTO` blob → CAS. dedup on vCard UID.

🧬 **Nora:** The NER-support value is authoritative structured data. Plugin populates `entities[]` directly under `scope: contact`: `email_address` (canonical/rfc5321), `phone_number` (canonical/E.164), `org`, `person` (FN), `url`, `social_handle.<platform>` / `linkedin_profile` / `github_profile` from X-SOCIALPROFILE/IMPP/URL. This IS structured-first extraction — the production recipe.

😈 **Riku:** Hard wall: NO auto-linking contact identity to NER mentions or mail participants. Phase 4 manual-merge, human-confirmed pairs only. Same constraint as person-identity.

🧬 **Nora:** Distinguish identity-merge (forbidden) from gazetteer/recognition-overlay (legitimate but out of v1). The contact stands as its own document.

✂️ **Petra:** V1: parse vCard → write `contacts/<slug>.md`, body + authoritative `scope: contact` entities + PHOTO→CAS + UID dedup. `tags: []` empty for amenders. zkm-ner may later add `scope: body` entities from NOTE. That's it.

🏗️ **Archie:** Plugin emits POPULATED entities[], not empty. `scope: contact` vs `scope: body` — clean coexistence under `(scope,type,value)` dedup.

🔐 **Dario:** Social/profile fields (X-SOCIALPROFILE, IMPP, URL) map straight to existing γ types. zkm-vcard front-runs the social-network "identity card" meeting (`TODO.md:81`) for the structured-export case — note it so they don't collide.

### Agenda 4a — zkm-calendar constraints (deferred build)

🏗️ **Archie:** VEVENT → message-like md per `messaging-spec.md`. `message_id`=iCal `UID`, `date`=`DTSTART`, `participants[]` from `ORGANIZER`/`ATTENDEE` (roles already defined), body=SUMMARY+DESCRIPTION+LOCATION+time, `RRULE` series → one `thread_id`, ATTACH → CAS.

🔐 **Dario:** The eml overlap is real: an event you're invited to exists in both the CalDAV `calendar/` tree AND as a `METHOD:REQUEST` `.ics` part in the invitation email.

😈 **Riku:** The iCal **UID** is globally unique by RFC 5545. Same event from mail invite and calendar tree carries the same UID. Cross-source double-ingest **dedups for free** — no eml↔calendar coupling needed.

🗺️ **Flora:** Routing stays clean via existing inbox fan-out. zkm-eml detaches `text/calendar` parts as attachments to `inbox/`. zkm-calendar claims them by content-type. No cross-plugin coupling.

✂️ **Petra:** All of this as constraints carried forward into the zkm-calendar build, not work to do now.

🧬 **Nora:** Implicit deadlines / upcoming events mentioned in mail text: NOT iCal parsing. That's a zkm-ner concern — a new γ entity type, a temporal extractor. Keep zkm-calendar a standards parser only, never NLP.

### Agenda 4b — Temporal NER, 3 layers

🧬 **Nora:** Layer 1 (buildable): spaCy already emits `DATE`/`TIME` spans. Map those to new γ `type: datetime`, `canonical` = ISO 8601 resolved against the document's `date` as anchor (relatives via `dateparser`, bilingual DE/EN). A `zkm.canonical.datetime` normaliser in the γ pattern. Deterministic, no LLM.

😈 **Riku:** Layer 1's hazard is noise — newsletters have many incidental dates ("subscriber since 2019", "© 2026"). Pure DATE extraction has low actionable-signal ratio.

🧬 **Nora:** That's Layer 2 — actionability (which datetimes are events/deadlines worth surfacing). Requires understanding, not typing → LLM-shaped, research-grade per n9d-gate-c, gated and deferred exactly like N9d.

🏗️ **Archie:** Layer 3 (Tobias's flag): informal `datetime` mention → formal VEVENT after registration. Same no-auto-merge wall → Phase 4 manual-merge, matching on canonical ISO + fuzzy summary, provenance-preserving (link, never overwrite; informal→formal is additive). Extends `TODO.md:47` alias-merge from person-aliases to event-promotion.

🗺️ **Flora:** The direction is informal→formal, a provenance chain, not a conflict. The newsletter mention and the VEVENT are different documents; linking is additive.

🧬 **Nora:** **Taxonomy guard:** `datetime` is a value-type (canonicalizes to ISO). "Deadline"/"event"/"appointment" are intent labels, NOT value-types. Don't overload `type` with intent; intent is a separate L2 dimension.

**Tobias extended:** an NER-extracted date might LATER yield an actual VEVENT — e.g. a newsletter mentioning an event to which one THEN registers. The informal mention and the formal event are the same real-world thing at two stages of formalization. The Phase-4 manual-merge should preserve this provenance chain.

### Agenda 5 — Sequencing, phase, naming, prefixes

- **Build order:** (1) `zkm-vcard` → (2) `zkm-ner` L1 `datetime` (parallel) → (3) `zkm-calendar` (own meeting/build when vcard ships).
- **Names:** `zkm-vcard`, `zkm-calendar` (match proton-moresync docs).
- **Phase:** Phase 3 by roadmap, but **buildable now** — ingest-only means no fetch dependency; test against hand-exported `.vcf`/`.ics` fixtures. Do NOT wait for proton-moresync. The `zkm fetch` orchestrator is the genuinely Phase-3 piece.
- **Prefixes:** `V` = zkm-vcard, `C` = zkm-calendar, `N` = temporal-NER (existing). `zkm fetch` = core/cross-cutting (no prefix).
- **Collision note:** zkm-vcard front-runs `TODO.md:81` for the structured-export case — cross-link both items.

## Decisions

1. **Fetch boundary:** contacts/calendar plugins are **ingest-only, source-agnostic** — read a local tree of standard `.vcf`/`.ics` via `source_dir`, never authenticate/fetch. Fetch is deferred to a future **core `zkm fetch`** orchestrator that runs configured external tools per source (NOT in-plugin, NOT per-source systemd sprawl). *Out of scope:* any in-plugin Proton/Gmail/CalDAV auth or Python fetch-client reimplementation.

2. **Two repos, sequenced, vcard first:** `zkm-vcard` then `zkm-calendar`, each its own gitignored git repo under `plugins/zkm-<name>/`, independently `vX.Y.Z`-tagged. Calendar mapping settled but gained eml-interface question, so contacts (clearer NER-leverage) lead.

3. **zkm-vcard contact = document:** `contacts/<slug>.md` per vCard UID; human-readable body (BM25/dense-searchable); PHOTO→CAS (`zkm.cas.write_object`); UID dedup; **populated, authoritative `entities[]` under `scope: contact`** (email_address/rfc5321, phone_number/E.164, org, person/FN, url, social_handle.<platform>, linkedin_profile, github_profile). `tags: []` placeholder; zkm-ner may amend `scope: body` from NOTE. **No identity-merge** (Phase 4 manual-merge). *Out of scope (forward-flags):* gazetteer/recognition-overlay, email-exact-clustering.

4. **zkm-calendar (deferred build):** VEVENT→message-like md per messaging-spec; dedup-on-UID (RFC 5545 globally unique) merges mail-invite + calendar-tree copies for free — no eml↔calendar coupling; mail `.ics` routed via existing inbox fan-out (content-type claim); standards-parser only, never NLP.

5. **Temporal NER (3 layers):** L1 `type: datetime` (buildable — ISO 8601, anchored on doc `date`, DE/EN via `dateparser` + spaCy DATE/TIME) in zkm-ner; L2 actionability gated like N9d (candidate-only, deferred); L3 mention→VEVENT promotion Phase-4 manual-merge on canonical ISO, provenance-preserving (additive link, never overwrite). `datetime` is a value-type; intent stays out of `type`.

6. **Phase 3 by roadmap, buildable now** against hand-exported fixtures; no proton-moresync dependency.

## Action items

- [ ] **[V]** Create `zkm-vcard` plugin repo (`plugins/zkm-vcard/`): ingest-only vCard→md converter — `contacts/<slug>.md` per UID, searchable body, PHOTO→CAS (`zkm.cas.write_object`), UID dedup, populated `scope: contact` `entities[]`, `tags:[]` placeholder, hand-exported `.vcf` fixtures. Contract: no fetch, no identity-merge. <!-- id:e5f9 -->
- [ ] **[N]** zkm-ner L1 temporal (`plugins/zkm-ner/`): γ `type: datetime` + `zkm.canonical.datetime` normaliser (ISO 8601, anchored on doc `date`, DE/EN via `dateparser`) + spaCy DATE/TIME mapping. Contract: relative-date fixture resolves to correct ISO against known anchor. <!-- id:805f -->
- [ ] **[C]** (deferred) `zkm-calendar` plugin (`plugins/zkm-calendar/`): VEVENT→message-like md, dedup-on-UID cross-source, inbox fan-out for mail `.ics`, standards-parser only. Own meeting/build when zkm-vcard ships. <!-- id:cca0 -->
- [ ] (core, deferred) `zkm fetch` orchestrator (`src/zkm/cli.py`): config maps source → external fetch command + output dir; shells out, deposits standard files, then `zkm convert` ingests. mbsync-equivalent lever in core, not systemd sprawl. <!-- id:473c -->
- [ ] **[N]** (deferred) Temporal L2+L3 design note (`docs/entity-model.md`): L2 actionability classifier (gated like N9d); L3 Phase-4 manual-merge mention→VEVENT promotion on canonical ISO, provenance-preserving (additive link). <!-- id:6f3a -->
- [ ] Cross-link zkm-vcard ↔ social-network "identity card" meeting (`TODO.md:81`) so they don't collide. <!-- id:2638 -->
- [ ] Add `V` (zkm-vcard) and `C` (zkm-calendar) to TODO-prefix table in `CLAUDE.md`. <!-- id:0604 -->
