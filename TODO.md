
# zkm — Phase 2 TODO

See `CLAUDE.md` for architecture overview. See `docs/phase2-plan.md` for sequencing.
Completed Phase 1 tasks archived in `docs/phase1-done.md`.

## Cross-project

- [ ] **[MEETING] `--cross` git-add CAS objects during scans** so the commit is faster afterwards — though that might require worktrees like `/relay` uses to permit concurrency. *Design-judgment (two approaches: eager-add-during-scan vs. worktree-per-scan); a `/meeting` candidate, not executor-ready. Reverse-handoff qualified 2026-06-23.* <!-- id:40d5 -->

- [ ] **bugfix — some objects in `knowledge` were left uncommitted (observed 20260623 07:05).** Raw incident note: a scan/convert run left CAS objects unstaged/uncommitted in the knowledge store. *Needs triage before it's executor-ready: no repro, no acceptance criterion yet — identify which code path (scan? convert? amender?) leaves the working tree dirty without committing, then a red spec can be written. May relate to id:40d5 (eager git-add) and id:b7e2 (processed-tracking). Reverse-handoff qualified 2026-06-23.* <!-- id:dab8 -->

- [ ] **Cross-project (triad) — `/meeting`:** discuss the potentially connecting dots between **zkm
  infrastructure** (embeddings / semantic retrieval / knowledge-mgmt) and the `.mw`/toesnail/collAIb triad.
  toesnail is the documented triad hub (`toesnail/docs/dependencies.md`); a session would decide whether/how
  zkm becomes a node in that dependency map. **MIRRORED in `toesnail/TODO.md` under the same `id:4159`** — keep
  both copies in sync MANUALLY (no automated cross-PROJECT sync; relay `--cross-ledger` is intra-repo only,
  inbox routing is one-way). Wherever worked/closed, tick the twin. Likely a manual `/meeting`. <!-- id:4159 -->

- [ ] **Polyrepo plugin-ROADMAP ↔ core-TODO drift — shared-`id:` ledgers go out of sync.** This repo's
  central TODO.md is the single ledger for all plugin-scoped work (`W`/`V`/`C`/… prefixes), and each plugin
  repo's `ROADMAP.md` declares "items reuse the `id:` tokens of their counterparts in `~/src/zkm/TODO.md`".
  But relay executors tick the **plugin ROADMAP** checkbox in the *plugin* repo; nothing reaches back to tick
  the shared-`id:` twin here. **Concrete instance (reconciled manually 2026-06-21):** W6f/W-key/W8/W10/W11a
  (ids w6f/w-key/f5b7/d058/w11) were `[x]` in `plugins/zkm-whatsapp/ROADMAP.md` for weeks while still `[ ]`
  here. `orphan-scan --cross-ledger` does NOT catch this — it only compares TODO↔ROADMAP *within one repo*,
  and zkm core + plugin repos are separate repos. **Mechanism home already exists:** dotclaude-skills `id:69f4`
  (cross-PROJECT bidirectional sync / proposed `orphan-scan --cross-project`) + `id:3947` (routed dead-letters)
  cover this class — do NOT build a parallel mechanism here. **This item's job:** (a) ensure the zkm core repo +
  its plugin repos are in whatever repo-set `id:69f4`'s scanner ends up using; (b) until that lands, the relay
  reviewer/`/meeting` close-out should reconcile the core W-/V-/C- twins when ticking a plugin ROADMAP item.
  Relates to dotclaude-skills id:69f4, id:3947; the manual-sync `id:4159` above is the same pattern for triad repos. <!-- id:1d41 -->

## OpenPGP key & signature tracking (decided 2026-06-04-1002-pgp-keys-signature-validity.md)

D1: vCard KEY → pgpy fingerprint entity + CAS bytes. D2: zkm-eml Tier A (signed: pgp-mime/smime) + Tier B (auth_results: dkim/spf/dmarc from provider headers). D3: fingerprint = join-grade value-type, NOT person-merge license. Build order: core → eml → vcard.

## Phase 2.5 — NER (decided 2026-05-10-1148-entity-extraction.md)

NER lands before whatsapp. `zkm convert <plugin>` runs amenders default-on (`--no-amenders` to skip). Session 9d extraction-cache transitions from design-only to implementation alongside zkm-ner.

    **Final state (post two convert+scrub cycles):** 471,894 total mentions (-34.4% vs 719,504 post-N9b). Legit-ORG target MET: Google LLC ×3204, PayPal ×1892, Amazon WS ×1074, SBB ×542, ETH ×485 all intact. Person top is now Tobias Kienzler ×11,270. Second cycle stable (+18 net entities only).
    **Remaining FP classes found:**
    - *Class 5 (pipe cell artifacts):* `'| |'` ×2664, `'| | |'` ×679, `'|  |'` ×373 — inline empty table cells within data rows; N9b only strips full pure-pipe rows. Fix: post-extraction value filter rejecting `^[\s|]+$`. See N9c backlog below.
    - *English-noun limitation in isolated POS:* `'Learn'` ×1032, `'Link'` ×679, `'Actions'` ×430, `'Download'` ×357 — German model tags these PROPN/X (foreign word), passes isolated POS. Fix: try EN model when DE model returns PROPN for a foreign-looking value.
    - *Multi-word phrase FPs (N9d territory):* `'Hallo Tobias'` ×1930, `'Best Regards'` ×1139, `'Guten Tag Herr Kienzler'` ×444, `'Hello Tobias'` ×392 — bypass multi-word skip in isolated POS; need LLM verifier or phrase-pattern blocklist.
    - *Boilerplate legal text in ORG:* `'L-2449 Luxembourg RCS Luxembourg'` ×859, `'S.C.A. Société en commandite par actions'` ×854 — legitimate entity names but high-frequency boilerplate; defer.
    - *HTML-entity quoted-reply markup:* `&gt;&nbsp;` runs extracted as `org` because zkm-eml renders bodies with HTML entities undecoded pre-NER; not caught by `_BASE64_FRAGMENT_RE` in `scrub()`. Fix: `drop_html_entity_artefacts()` pattern in `scrub()` OR `html.unescape()` in zkm-eml render path. See `docs/meeting-notes/2026-05-29-0859-embed-oversized-chunk-timeout.md`.
    **Note:** this convert ran with pre-N9c code; in-pipeline POS filter not yet applied. A fresh `zkm convert ner` will bust cache (new version key) and re-extract with POS filter, which will prevent new FPs — required before calling N9c fully clean.
    **Note on multi-word phrase FPs (`'Hallo Tobias'` ×1930 etc.):** decided 2026-05-19 to accept these as-is. Deduped under `(scope,type,value)` they are a closed handful of distinct values; escape hatch = add to `_STOPLIST` if ever annoying. See `docs/meeting-notes/2026-05-19-1610-ner-user-names-drop.md`.
- [ ] **(deferred) Temporal NER L2+L3 design note.** L2 = actionability classifier (which datetimes are real events/deadlines vs incidental noise) — LLM-shaped, research-grade per n9d-gate-c, gated like N9d (candidate-only, evidence before infra). L3 = Phase-4 manual-merge mention→VEVENT promotion (canonical ISO match + fuzzy summary, provenance-preserving, additive link — extends `TODO.md:47` alias-merge from person-aliases to event-promotion, covering the lifecycle: newsletter mentions event → user registers → formal VEVENT appears in calendar → link them). Design note in `docs/entity-model.md` first. **Gate for L2:** open-set noise confirmed (L1 ships and noise level measured). See `docs/meeting-notes/2026-06-01-1334-contacts-calendar-plugins.md`. <!-- id:6f3a -->
- [ ] **N9e (backlog — no live trigger path).** Closed-loop verifier denylist — append-only JSONL at `<store>/.zkm-state/ner-verifier-denylist.jsonl`; one record per `(value, type)`: `{value, type, verdict, source, model_version, first_seen, heuristic_would, n_observations}`. `source ∈ {verifier, heuristic, manual}`; `verdict ∈ {drop, keep}` (drops-only direction designed; keeps-becoming-sticky deferred — precedence ambiguity). **Gate: (N9d shipped) AND (≥5 verifier-override cases observed in Stage 2 pilot).** **Status 2026-05-12: gate cannot fire — N9d closed via Gate C; verifier did not ship.** Entry remains in backlog for archival reference; no implementation path until/unless a successor verifier project replaces the gate condition. Conflict-resolution for allow+deny overlap unresolved — design meeting required if revived.
  - [~] **N9d-9.** Per-language accuracy lens — **not pursued** (gate closure pre-empts; reopen only if N9d is revived under a different model).
  - [~] **N9d-11.** N9e sketch into `docs/ner.md` — **not pursued** (N9e gate condition is moot; see N9e backlog entry).

**Scope constraints (from meeting):**
- `value:` strings are *mention strings*, never UIDs. No `id:`, `same_as:`, cross-doc clustering.
- Name alone is NOT a UID — manual-merge tooling deferred to Phase 4.
- Co-reference within doc deferred to v2; intra-doc pronoun coref not in scope.
- GLiNER is opt-in only; sentence-level language routing out of scope.

## Phase 2.5 — γ schema rollout (decided 2026-05-12-1500-entity-vs-datamining.md)

**Status: γ rollout COMPLETE (E1–E13).** Typed-slot `entities[]`, `(scope,type,value)` dedup, `zkm.canonical`, suspicious dispatch, 8 value-type extractors, P2 index integration, docs contract tables, and zkm-eml signature/salutation γ-scopes all shipped (largely 2026-05-12). E13 (N9g re-eval) closed moot 2026-05-21 — see item below. E14 (TODO bookkeeping) was the only never-run item — reconciled 2026-05-21, see `docs/meeting-notes/2026-05-21-0816-gamma-schema-gap-audit.md` and `docs/field-test-bge-m3.md` step 7.

- [~] **E13: N9g re-evaluation** — CLOSED MOOT 2026-05-21. Audit confirmed: (1) pattern-overlay overlap filter prevents spaCy from mislabelling value-type strings (amounts, IBANs, etc.); (2) N9c POS filter + `_COMMONNOUN_STOPLIST` handles common-noun FPs; (3) `_SALUTATION_BLOCKLIST` covers sign-off/salutation FPs; (4) `drop_structural_artefacts` + `drop_section_link_artefacts` cover structural pollution; (5) E12 shipped signature-scope extraction. No standalone "general body-NER cleanup" workstream remains. See `docs/meeting-notes/2026-05-12-1500-entity-vs-datamining.md`.

**Named deferrals (with triggers):**
- P3 typed query language — defer until γ + P2 live ≥1 month AND ≥1 concrete typed-query request.
- PII redaction implementation — defer until sharing scenario lands. Architectural design in E10.
- Entity-DB checksum-fail "ignore / correct?" policy — defer until ≥50 `valid: false` entries accumulate.
- `valid: false` forward-flag: re-evaluate dropping the per-type suspicious heuristic (Option 3) after ≥1 month observation.
- Crypto/stock-ticker domain scope — defer; revisit if real use case lands.
- WebUI typed-query hint UX — Phase 3 design concern.

- [ ] **Entity alias / synonym linking (Phase 4 backlog)** — `SBB CFF FFS` (DE/FR/IT names for Swiss Federal Railways) highlights that the same real-world entity can appear under multiple mention strings (abbreviations, translations, official variants). Likewise, persons appear under nicknames, maiden names, or initials. Deferred to Phase 4 alongside manual-merge tooling; design note needed in `docs/entity-model.md` before implementation. No heuristic auto-merge — human-confirmed alias pairs only.

## Phase 2 — mbsync auto-trigger (decided 2026-05-08-mbsync-hook.md)

- [~] **zkm-eml signature stripping** — promoted 2026-05-12 to first-class action item: see **N9g-pre** above. (Original framing 2026-05-10-1640-n9b: heuristic detection of email signature blocks before markdown render; addresses popularity skew of personal contact details. Re-scoped from "stripping" to "typed extraction" in N9g-pre.)

## Phase 2 — SIGUSR1 progress + `zkm status` (decided 2026-05-08-1913-sigusr1-status.md)

Scope: `convert` and `index` (BM25 + embed phases) only. `query`, `clone`, `push`, `pull` explicitly out. Daemon/supervisor model deferred (N<2 background callers). Host-wide multi-store registry, historical run log, `--kill`, `--watch`, live-tail all deferred.

**Spawned follow-ups (from 2026-05-14 concurrent-run-guard meeting):**

- [ ] **Future re-evaluation trigger — local DB with git-tracked autoexport-on-write** — possible architectural pivot from sidecar-files-on-disk. Re-open if any one trigger fires: (a) concurrent-write bugs in sidecars become frequent; (b) WebUI read-write workload makes file-level locking visibly painful; (c) cross-machine sync stops being purely `git pull`-based. See `~/.claude/projects/-home-tobias-src-zkm/memory/project_db_pivot_trigger.md`.
- [ ] **`zkm queue` design meeting (Phase 3 daemon precursor)** — when attach semantics become a real ask (N=2 consumers wanting `--wait-for-busy`), open a meeting on a queue manager: PID-file → in-memory daemon queue; fail-fast → `attach/wait/wait-rerun` modes; `zkm status` polling → WebSocket push (Phase 3 WebUI alignment). Floor any successor must preserve: the v1 contract in `~/.claude/projects/-home-tobias-src-zkm/memory/project_concurrent_run_guard_contract.md`.

**Verification checklist** (313 tests passing, 2026-05-08):
1. `zkm convert zkm-eml` in terminal A → `zkm status` in terminal B shows one row with fresh `last_updated`.
2. `kill -USR1 <pid>` directly → dd-style line on convert's stderr.
3. `zkm index` → `phase` toggles `bm25` → `embed`; `zkm index --no-embed` stays at `bm25`.
4. SIGKILL the process → next `zkm status` drops stale file with stderr notice.
5. `zkm status --json | jq` → valid JSON array.

## zkm-vcard (V-prefix) — contacts plugin (decided 2026-06-01-1334-contacts-calendar-plugins.md)

Ingest-only, source-agnostic. Reads a local tree of standard `.vcf` files via `source_dir` (from proton-moresync / Google Takeout / vdirsyncer / any client export). Never authenticates or fetches. Phase 3 by roadmap, but buildable now against hand-exported fixtures.

**Scope constraints (from meeting):**
- Contacts are authoritative structured-first data — emit `entities[]` populated, not empty.
- `scope: contact` entities coexist with `scope: body` NER (zkm-ner amends NOTE field). Dedup key `(scope,type,value)`.
- NO identity-merge — no auto-linking contact identity to NER mentions or mail participants. Phase 4 manual-merge, human-confirmed pairs only.
- No fetch, no credentials, no gazetteer/recognition-overlay (forward-flags, not v1 scope).
- Cross-link with `TODO.md:81` social-network scoping meeting (zkm-vcard front-runs it for structured-export case). <!-- id:2638 -->

**v0.2.0 hardening shipped (2026-06-03):** V1 encoding (zkm.encoding.decode_bytes, latin1/cp1252 detection), V2 canonical consolidation (drop _canon_email, phone fallback), V3 reprocess() (re-derive scope:contact, preserve scope:body), V4 scope:contact in entity-model.md, V5 failure counter. See `docs/meeting-notes/2026-06-03-1603-vcard-hardening-series.md`.

## zkm-whatsapp (W-prefix) — chat plugin (decided 2026-06-03-0952-zkm-whatsapp-scope.md)

v1 = decrypted `msgstore.db` (SQLite) → per-chat-day transcript .md under `chat/whatsapp/`. Decryption is an out-of-scope fetch-role step (W-pilot is a hard gate). key_id-based stable IDs, WA-Web-mergeable. Source state = timestamp watermark + dedup-on-key_id.

- [ ] **`/meeting` — human-readable chat/entity paths (cross-cutting; whatsapp is the trigger).** Current chat paths are `chat/<network>/<thread_id>/YYYY-MM-DD.md` with `thread_id = sha256(chat_jid)[:16]` — opaque hex that directly contradicts the CLAUDE.md "Human-readable filenames, no hashes in filenames" convention. Want group names and contact/NER identities in the path so the tree is browsable. **Tensions to resolve (why it's a meeting, not a rename):** (1) **stability** — group subjects change, contacts get renamed, NER identities merge; a name-based canonical path churns + fragments git history + breaks cross-refs, whereas thread_id is stable; (2) **uniqueness** — duplicate contact names, group-name collisions, unnamed groups; (3) **identity resolution** — "name is not a UID" + manual-merge doctrine ([[project_name_not_uid]]): mapping a chat/sender to a person/group identity is the hard identity problem, and `entities[]` values are mentions not UIDs; (4) **privacy** — names in paths leak more than hashes. **Candidate approaches:** (A) human-readable slug + stable disambiguator `chat/whatsapp/<slug>-<short-thread-id>/`; (B) keep opaque thread_id as the **canonical** (stable) store + generate a derived, regenerable **human-readable view** (e.g. `chat/by-name/<group-or-contact>/ → thread_id`), mirroring the inbox CAS+symlink split — renames just regenerate the view, zero history churn, no identity-merge risk in the source of truth (likely preferred); (C) rename canonical path on identity resolution (rejected-leaning: churn + broken links). **Cross-cutting:** decide at the `messaging-spec.md` level (telegram/signal/threema share `chat/<network>/<thread_id>/`) and as a general path convention (calendar thread-index id:9fb8 uses the same opaque scheme). chat_name/participants are already in frontmatter to derive from. Decide canonical-vs-view, name-derivation + collision/rename policy, privacy posture. Filed 2026-06-23. <!-- id:3b8a -->
- [ ] **W7 (deferred design note).** Smarter segmentation (burst/temporal-density or per-thread) as additive re-segmentation; MUST NOT rewrite chat-level thread_id. Trigger: v1 live + concrete retrieval pain from day-boundaries. See `docs/meeting-notes/2026-06-03-0952-zkm-whatsapp-scope.md`. <!-- id:367f -->
- [ ] **W11b. Informal "new number" detection** [HARD]. Heuristic detection of "hey here's my new number" plaintext messages (patterns in multiple languages) → flag for human confirmation; never auto-merge identities (core "name is not a UID" policy). Gate: id:w11 shipped (done) + ≥1 real missed-number-change case. ROADMAP id:bf12. <!-- id:bf12 -->

## Messenger plugins: Telegram / Signal / Threema (decided 2026-06-22-1503-messenger-plugins-telegram-signal-threema.md)

Three new chat plugins, all conforming to `docs/messaging-spec.md` per-chat-day doc-type (`chat/<network>/<thread_id>/YYYY-MM-DD.md`). Decryption is an out-of-scope fetch-role step per plugin. Build order Telegram → Signal → Threema (difficulty). Prefixes **reserved** (allocate a row at ≥3 items): `T`=Telegram, `G`=Signal, `H`=Threema. Emit `participants:` only (no `entities[]`, matches zkm-whatsapp). Out of scope v1: secret/E2E device-local chats, live API sync, voice/OCR (→ zkm-stt).

- [ ] Core: lift WhatsApp `state.py` → `src/zkm/state.py` (`zkm.state`), behavior-preserving (keyed by source id, atomic write, watermark-speed-only); zkm-whatsapp imports it. Contract: existing whatsapp watermark tests pass unchanged; multi-account keying preserved. See `docs/meeting-notes/2026-06-22-1503-messenger-plugins-telegram-signal-threema.md`. <!-- id:f399 -->
- [ ] Core: shared byte-identical-reemit contract-test helper (`zkm.testing.assert_reemit_identical` or pytest fixture); document in `messaging-spec.md`. Contract: emit→re-emit from same snapshot asserts byte-identical. See `docs/meeting-notes/2026-06-22-1503-messenger-plugins-telegram-signal-threema.md`. <!-- id:ab8b -->
- [ ] zkm-telegram: `convert()` over Telegram Desktop `result.json` → per-chat-day transcripts; `message_id = telegram:<chat_id>:<msg.id>`, reply graph from `reply_to_message_id`, media → CAS. No decryption. Ship conformance fixture. See `docs/meeting-notes/2026-06-22-1503-messenger-plugins-telegram-signal-threema.md`. <!-- id:849f -->
- [ ] zkm-signal: decryption pilot (SQLCipher+keyring unwrap vs Android `.backup`/signalbackup-tools) is a hard gate; then `convert()` over decrypted SQLite (whatsapp skeleton). See `docs/meeting-notes/2026-06-22-1503-messenger-plugins-telegram-signal-threema.md`. <!-- id:b043 -->
- [ ] zkm-threema: resolve source artifact (Data Backup ZIP vs Safe) on the bench, then scrypt-decrypt fetch step + `convert()`. Forward-flag: `messaging-spec.md:303` likely wrong ("Safe"). See `docs/meeting-notes/2026-06-22-1503-messenger-plugins-telegram-signal-threema.md`. <!-- id:c89a -->
- [ ] Reserve prefix letters T/G/H in CLAUDE.md TODO-prefix table commentary; allocate a full row per plugin once it hits ≥3 unchecked items. See `docs/meeting-notes/2026-06-22-1503-messenger-plugins-telegram-signal-threema.md`. <!-- id:8cf8 -->

## PDF routing unification — `zkm.pdftext` (decided 2026-06-22-1546-pdf-routing-unify-pdftext.md)

Kills the zkm-pdf↔zkm-scan two-probe drift bug (whitespace-heavy PDF skipped by BOTH) by giving core one `zkm.pdftext` helper that owns the routing *decision* (`probe()` + `is_scanned_only()` + `resolve_threshold()`), consumed by both plugins. Char-count default `100` ships now; density-ratio discriminator deferred to a gated pilot. HARD cross-repo id:02bd (zkm-scan ROADMAP) decomposed into 3 ordered single-repo executor items (core → zkm-pdf → zkm-scan); id:02bd stays open until all three land + both ROADMAPs ticked + ARCHITECTURE updated. Renamed config keys keep a deprecated alias + warning for one release.

- [ ] **Core: add `zkm/pdftext.py`** — `PdfTextProbe(total_chars, n_pages)`, `probe(reader)`, `is_scanned_only(probe, threshold)`, `resolve_threshold(store_config)` (top-level `pdf_text_threshold:` > per-section > `DEFAULT_TEXT_THRESHOLD=100`; warn on per-section disagree), measurand pinned in docstring; update core `ARCHITECTURE.md` §Routing contract; minor bump (cascade plugin `uv.lock`s). See `docs/meeting-notes/2026-06-22-1546-pdf-routing-unify-pdftext.md`. <!-- id:9e13 -->
- [ ] **zkm-pdf: migrate to `zkm.pdftext`** — routing (`src/zkm_pdf/convert.py:389`/`:62`) calls `is_scanned_only`; rename `min_text_chars`→`pdf_text_threshold` (deprecated alias 1 release + warn); pin `zkm>=X.Y`; bump. Contract: whitespace-heavy fixture routed by exactly one plugin. After id:9e13. See `docs/meeting-notes/2026-06-22-1546-pdf-routing-unify-pdftext.md`. <!-- id:d3c9 -->
- [ ] **zkm-scan: migrate to `zkm.pdftext`** — routing probe (`src/zkm_scan/convert.py:403`/`:106`) calls `is_scanned_only` (negated); rename OCR floor `min_text_chars`→`ocr_min_chars` (alias 1 release + warn), kept separate from routing; pin `zkm>=X.Y`; bump. Contract: same fixture routed by one plugin; OCR floor independent. After id:9e13. See `docs/meeting-notes/2026-06-22-1546-pdf-routing-unify-pdftext.md`. <!-- id:1681 -->
- [ ] **Density-ratio pilot (gated, OPEN)** — supersedes zkm-pdf id:9475: per-page density/coverage discriminator vs char-count default; gated on "labeled PDF corpus built + ≥1 documented char-count misclassification". Needs `page_chars` on `PdfTextProbe` + a labeled corpus (MSA study). Not auto-fired. See `docs/meeting-notes/2026-06-22-1546-pdf-routing-unify-pdftext.md`. <!-- id:c63c -->
- [ ] **Update plugin ledgers** — rewrite zkm-scan ROADMAP id:02bd decision block + done-definition; reword zkm-pdf id:9475 to point at the gated pilot (id:c63c); both cite the note. See `docs/meeting-notes/2026-06-22-1546-pdf-routing-unify-pdftext.md`. <!-- id:835c -->

## zkm-calendar (C-prefix) — calendar plugin (decided 2026-06-01-1334-contacts-calendar-plugins.md)

**Deferred — own meeting/build when zkm-vcard ships.** Ingest-only, standards-parser only (RFC 5545), never NLP. Build order: zkm-vcard → zkm-calendar.

- [ ] **C3 (deferred): calendar thread-index files** — `calendar/threads/<thread_id>.md` per series. RRULE not expanded in v1, so threads are singletons; deferred to when multi-VEVENT series (override instances) are ingested or a retrieval pain point surfaces. See `docs/meeting-notes/2026-06-05-1300-c1-zkm-calendar-build.md`. <!-- id:9fb8 -->

## Plugin backlog — conversation / AI session sources

**Scoped (decided 2026-06-06-1617-zkm-claude-ai-claude-code-scoping.md):** claude-ai ✓; claude-code ✓ (v0.1.0, 2026-06-11); `zkm.session` extracted (N=2 done, `src/zkm/session.py`). Other providers deferred until session-import pattern proven with two real plugins.

- [ ] **Other AI provider sessions** (ChatGPT exports, Gemini, etc.) — deferred until zkm-claude-code lands and the session-import pattern is proven. N=2 for a shared `zkm.session` helper requires at least two providers implemented.

## Plugin backlog — social networks

- [ ] **Meeting: takeout / export archive import** — personal data exports from Google Takeout, Facebook "Download Your Data", Instagram, LinkedIn, Twitter/X, etc. are structured archives (ZIP + JSON/HTML). Distinct from live scraping: deterministic, offline, privacy-safe. Sub-questions: (1) which export formats to support first (LinkedIn most structured); (2) shared `zkm.takeout` extraction helper vs. per-network plugins; (3) "being tagged" in others' posts as a distinct entity-mention type (requires cross-document resolution). Warrants a scoping meeting. Cross-link: LinkedIn browser-save lane in SOC3 converges with LinkedIn-takeout ingest — shared parser opportunity; keep separate but note the overlap.

### zkm-social (new plugin — social-network profile identity cards)

- [ ] **SOC1.** Build `zkm-social` plugin skeleton: `plugin.yaml` (`creates_dirs: [contacts, originals/contacts]`), `convert(store_path, config) -> list[Path]` with per-network parser dispatch. Code at `plugins/zkm-social/` (fievel:src/zkm-plugins/zkm-social.git); needs GitHub remote + user review. <!-- id:56ac -->
- [ ] **SOC2.** GitHub parser module (lane B): fetch `api.github.com/users/<login>`, map login/name/bio/company/location/blog/avatar → `contacts/<slug>.md`, typed `entities[]` at `scope:profile.github`, avatar → CAS, dedup-keyed on profile URL. Code at `plugins/zkm-social/_github.py`; needs GitHub remote + user review. <!-- id:017f -->
- [ ] **SOC3.** LinkedIn parser module (lane A): parse a browser-saved LinkedIn profile (HTML/PDF/MHTML) for name/headline/current-employer/location/photo/profile-URL; emit `contacts/<slug>.md` at `scope:profile.linkedin`, photo → CAS, dedup-keyed on normalized profile URL. Code at `plugins/zkm-social/_linkedin.py`; needs GitHub remote + user review. <!-- id:7f55 -->
- [ ] **SOC4** (sequenced follow-on, after SOC1–3 prove the doc shape). Browser extension / bookmarklet capture front-end: one-click capture of the rendered profile into the `zkm-social` source dir. Contract: capture button → file in source dir → existing ingest path produces the note. <!-- id:dfa4 -->
- [ ] **SOC5** (deferred — separate scoping meeting). Activity-feed doc-type: posts/reactions/comments/being-tagged. Overlaps `messaging-spec.md`. Reopen when a concrete feed use-case appears. <!-- id:a580 -->
- [ ] **SOC6** (deferred — gated escalation). Bulk / lead-gen multi-subject capture. Gate: concrete use-case + ToS clearance + deliberate decision to cross the single-subject boundary. <!-- id:3de4 -->

## Plugin backlog — browser state (open tabs / bookmarks / history)

- [ ] **zkm-tabs (idea — salvaged from the retired `gtnsd` repo's "attach a list of open tabs to each commit"
  / TreeStyleTab thread; history preserved in `toesnail` branch `gtnsd-archive`).** A plugin to capture
  browsing context into the store: currently-open browser tabs (e.g. TreeStyleTab tree export), bookmarks, and
  possibly history — as timestamped knowledge snapshots / per-session context. Open Qs: capture mechanism
  (browser extension / bookmarklet / native-messaging vs. reading the browser's `places.sqlite` +
  session-restore files); cadence (on-demand vs. periodic); **dedup/diff** — tabs & bookmarks churn, so store
  deltas not full dumps (overlaps the inflownistration/staleness idea, `.mw` `id:aae4`); privacy posture (URLs
  can be sensitive — mirror zkm-claude-ai's deliberate-render stance). Relates to the SOC4 bookmarklet-capture
  front-end (id:dfa4). **Active-triage extension (added 2026-06-18):** beyond passive capture, a
  browser addon that lets you *triage* open tabs with per-tab actions — **keep** (snapshot into the
  store as durable knowledge), **archive** (store + close the tab), **close** (drop, no store),
  **forget** (close + suppress from future capture/dedup), **reminder** (store with a date-trigger /
  resurface later). This makes zkm-tabs a tab-hygiene workflow, not just a snapshotter — the triage
  *decision* becomes the captured signal (why a tab mattered), and "archive/forget" naturally feed
  the dedup/diff + staleness model already noted. Open Qs it adds: where the action verbs live
  (addon UI vs. a post-capture `zkm` triage command over a captured tab-list); whether "reminder"
  reuses a core date-trigger mechanism; how "forget" interacts with the delete/scrub semantics
  (cf. zkm-notmuch id:f103 tag-removal). Warrants scoping before build. <!-- id:301c -->

## Plugin backlog — audio / video transcription (STT)

- [ ] **zkm-stt (idea — Speech-to-Text transcription plugin).** Converts audio/video sources to
  timestamped transcript `.md` under `transcripts/`. Primary use cases: (1) **WhatsApp voice
  messages** — after zkm-whatsapp v1 ships, STT pass over attached `.opus`/`.m4a` files to
  embed spoken text in the chat transcript rather than leaving `[voice message]` stubs;
  (2) **YouTube / video transcription** — download + transcribe talks, lectures, podcasts
  (yt-dlp for audio fetch; Whisper / faster-whisper for local transcription). Shared design
  questions: backend choice (openai-whisper, faster-whisper, or OpenAI-compatible
  `/v1/audio/transcriptions` endpoint for remote offload); language detection vs. explicit
  per-source config; caching — transcription is expensive, so `.amendments.json`-style sidecar
  or CAS-keyed cache keyed on audio sha256; word-level timestamps vs. segment-level; speaker
  diarisation (deferred). WhatsApp integration: amender-style (runs as post-convert amender,
  scoped to `created` voice-message paths) vs. embedded in zkm-whatsapp itself. YouTube:
  separate `zkm fetch youtube <url>` subcommand or a standalone `zkm convert stt` over
  dropped audio files in `inbox/stt/`. **Scoped 2026-06-21** — see
  `docs/meeting-notes/2026-06-21-2207-zkm-stt-scope.md`; build items STT1–STT4 below. <!-- id:dcf8 -->
- [ ] **STT1 — Build zkm-stt v1 (standalone converter).** New repo `plugins/zkm-stt/` (new-plugin
  dispatch convention: remote-first, skeleton-first barrier). `plugin.yaml`
  (`creates_dirs: [transcripts, originals/transcripts]`; config `stt_endpoint`/`stt_model`/`stt_api_style`),
  `convert()` over `inbox/stt/` (.opus/.m4a/.wav/.mp3), `transcribe(audio_path, config) -> Transcript`
  reuse seam, whisper.cpp `/inference` (`verbose_json`), ffmpeg resample, CAS the audio original,
  `(audio sha256, backend, model, version)` cache sidecar, `transcripts/<name>.md` with segment-level
  `[mm:ss]` + detected language (never pinned), per-file graceful skip on backend error. Contract:
  mocked-`/inference` hermetic test + real `.opus` smoke test. See
  `docs/meeting-notes/2026-06-21-2207-zkm-stt-scope.md`. <!-- id:37aa -->
- [ ] **STT2 — zkm-stt v2 WhatsApp amender.** Reuse `transcribe()` as an amender scoped to `created`
  voice-note paths; enumerate zkm-whatsapp manifest `mime: audio/*`, resolve CAS by sha256, transcribe,
  augment the body line (optional zkm-whatsapp polish: render `[voice: …]` not generic `[media: …]`).
  Gate: zkm-whatsapp v1 shipped (W-pilot). Contract: a day file's voice line gains `[transcript: …]`.
  See `docs/meeting-notes/2026-06-21-2207-zkm-stt-scope.md`. <!-- id:489b -->
- [ ] **STT3 — ASR quality pilot: compare models/means on real voice notes** `/meeting` **(next session)**.
  ACTIVATED 2026-06-23: after the `language=auto`+`translate=false` fix (zkm-stt v0.2.0, id from
  whisper.cpp source), German transcripts are "better but still not good" on `ggml-small` — so run a
  proper pilot before picking a default. **Compare (means × models):** whisper.cpp `/inference` with
  `ggml-small` (current) vs **`ggml-large-v3-turbo`** (already on disk); **Gemma 4 E4B** multimodal
  (audio-in via llama-swap — helferli found this only *partial*, verify the path first); plus the
  whisper alternatives discussed for helferli (faster-whisper / whisper-large-v3 / distil-whisper, and
  any Swiss-German fine-tune). **Method:** reuse + extend helferli's harness
  (`~/src/helferli/tools/relay/scripts/asr_bench.py` + `asr_bench.results.md`) — but it scores *language-tag*
  accuracy; this pilot must score **transcription quality** (WER / human-rated) against a small
  ground-truth set. **Ground-truth + privacy:** the sample is real WhatsApp voice notes (PRIVATE) — the
  user transcribes/ranks a handful by hand (e.g. the 5-clip drop-zone sample + a few Swiss-German ones);
  the agent must NOT read transcript content. **Swiss German caveat:** helferli's bench showed even
  correct language-ID still garbles Schweizerdeutsch on small models — expect a quality ceiling; pilot
  should include CH-German clips explicitly and consider whether any model clears the bar.
  **Consolidated output + auto-compare:** emit all candidates **side-by-side per clip** (a model×clip matrix),
  and add a **local LLM** (llama-swap on :8080 — aya-expanse-8b / gemma4-e4b / …) as an automatic
  comparator/judge: diff candidates, score agreement/divergence, flag likely-best + suspicious spans — *in
  addition to* the user's supervision, not replacing it. **Privacy bonus:** a *local* judge keeps the private
  transcripts on-box — no cloud/agent egress (directly the chidiai egress lesson, id:f3e1 /
  `~/src/chidiai/docs/cases/2026-06-23-secret-leaked-to-model-context.md`); the agent still must not read
  content. The large-v3-turbo quick-try lives inside this pilot (not ad-hoc). **Output:** a
  `stt_model`/backend recommendation + whether to wire Gemma-E4B/large-turbo as a real backend (the
  `openai`/multimodal N=2 seam). Don't restart the helferli investigation from scratch — build on
  `docs/meeting-notes/2026-05-12-2036-asr-language-detection.md` + `2026-05-14-1011-asr-lang-bench-stage3.md`.
  See `docs/meeting-notes/2026-06-21-2207-zkm-stt-scope.md`. **DESIGN 2026-06-23** — see
  `docs/meeting-notes/2026-06-23-1425-stt3-asr-quality-pilot.md` (D1–D6): tiered-privacy harness
  (`plugins/zkm-stt/tools/asr_quality_bench.py` over `transcribe()` seam, scores-tier agent-readable +
  gitignored content tier, no egress); Tier-1 matrix {ggml-small, ggml-large-v3-turbo, Gemma-E4B-multimodal};
  WER+CER sliced by {de,de-CH,en} (sample ~90% de) + lang-tag secondary; aya-expanse-8b ref-aware soft-judge
  (advisory); asymmetric decision rule (cheap default-swap vs N=2-gated new backend, latency NOT a gate).
  **HANDED OFF 2026-06-23** (zkm-stt relay-ckpt-20260623-1551): split into P1 `transcribe` (id:b695,
  DONE+running — `uv run tools/asr_quality_bench.py transcribe`), P2 `score` (id:5148, RED spec), P3 `gemma`
  (id:4bf2, RED spec). P1 already transcribed the 5-clip sample (whisper-small); large-v3-turbo pending a
  :8090 server. **Umbrella stays open** — closed by the pilot recommendation after the user fills
  `references.json` + runs `score`. Run P2/P3 via relay executor in `plugins/zkm-stt`. <!-- id:4ab4 -->
- [ ] **STT4 — zkm-stt roadmap enrichments.** Speaker labels / diarisation, background-noise
  identification + filtering, sentiment analysis, word-level timestamps, streaming. Each gated on a
  concrete need + (ML-shaped ones) evidence before infra. **Forward-flag (2026-06-23, stt3 meeting):**
  WhatsApp speaker-ID / diarisation can use **contact/sender metadata** (manifest sender per message),
  not acoustic voiceprinting — a cheaper path for the WA case. See
  `docs/meeting-notes/2026-06-21-2207-zkm-stt-scope.md`. <!-- id:fa7b -->

## Store hygiene — processed-tracking + git-as-byte-source (design)

- [ ] **`/meeting` — CAS processed-by-version tracking + git-sourced bytes.** Two coupled problems: **(1) input clutter** — `inbox/<subdir>/YYYY/MM/` symlinks accumulate indefinitely as sources are ingested; over time the inbox stops being a "drop zone / unprocessed view" and becomes an ever-growing pile of already-processed items. **(2) reprocessing is working-tree-walk shaped** — `run_reprocess` (version-aware skip, cf. `test_reprocess_outdated_skips_current_version`) and amenders iterate filesystem paths, not the set of CAS objects-needing-work. **Idea:** track which CAS objects were processed by which **plugin version** directly (the per-object sidecar `producers[]` already records `plugin` + `message` + `sha256` but **NOT version** — `docs/object-storage.md` schema v1), so a converter/amender can enumerate CAS objects whose `(plugin, version)` provenance is missing/outdated and process those directly — decoupling "what needs work" from the cluttered inbox view; the inbox symlink can then be retired/pruned once an object is fully processed (relates to `zkm gc`/`hygiene.py` orphan sweep). **Further idea (harder):** stop keeping processed bytes in the working tree at all — read originals via `git show <blob>` on demand instead of working-tree files, so tools operate on git history as the byte store. **Open question (annex):** git-annex/lfs externalize bytes — `git show` on an annex pointer yields the pointer text, not the content, and annexed objects may be absent locally (availability/`annex get`), so the git-show path is clean only for `backend=none`; annex/lfs need a backend-aware resolve (`zkm.cas` already abstracts this for symlinks — extend, don't bypass). Decide: sidecar schema bump (add `version` to producers) vs. a separate processed-ledger; eager-prune vs. lazy-prune of inbox symlinks; git-show byte-source as opt-in per backend. Touches `zkm.cas` / `zkm.inbox` / `zkm.sidecar` / `hygiene.py` / `convert.run_reprocess`. Filed 2026-06-23. <!-- id:b7e2 -->
- [ ] **Git operations on `$ZKM_STORE` are now slow — store has outgrown plain git.** Observed 2026-06-23 on `~/knowledge`: **311,904 tracked files** (504,705 in the working tree) and a **21 GB `.git` that is *larger* than the 15 GB working tree** — the tell-tale sign that **binary media (CAS objects) is committed straight into git history** (`backend=none`), so every pack/clone/gc drags the full binary history, and `git status`/`add`/`commit` walk a half-million-file tree on each auto-commit. **Measure first** (per *observe-before-preventing*): time `git status`/`add`/`commit` and attribute cost (object-count walk vs. pack size vs. fs scan). **Cheap config wins:** `core.untrackedCache=true` + `core.fsmonitor=true` (huge for 500k-file `status`), `feature.manyFiles`/`index.version=4`, `git gc`/aggressive repack, split-index. **Two independent cost drivers — separate them:** (A) **versioned-object-store bloat** — binaries committed as git *blobs* live in the packs/history, so `gc`/`repack`/`clone`/commit-delta-compression churn the full 15 GB; (B) **500k-file working-tree walk** — `git status`/`add` stat half a million paths every auto-commit. **Mitigations differ:** (B) is fixed by `core.fsmonitor=true` + `core.untrackedCache=true` regardless of backend (annex does NOT help the walk — its symlinks are still files). (A) is fixed by moving CAS bytes out of the *versioned pack* into git-annex/git-lfs (store supports a backend; this one is `none`). **NB (correction):** annex content lives under `.git/annex/objects` (lfs under `.git/lfs`), so this does NOT shrink `.git` on disk — the win is binaries leave the *pack/history* (fast versioned ops, cheap clone, delta-free commits) and content becomes **droppable** to a remote (`git annex drop`) to reclaim local space; total footprint only drops once content is dropped. Ties into [[id:b7e2]] (git-as-byte-source) and the derivable-data/backend decisions; per-convert auto-commit also motivates commit batching. Decide: config quick-wins now (cheap, reversible) vs. an annex/lfs migration of existing CAS history (history rewrite — expensive, irreversible-ish). Filed 2026-06-23. <!-- id:8f1c -->
- [x] **Git operations on `$ZKM_STORE` slow — DECIDED 2026-06-23-2251-knowledge-git-bloat-annex-anchoring.md.** Root cause corrected: NOT `backend=none` — backend *is* annex, but `.gitattributes` `originals/**` is root-anchored so nested CAS `<subdir>/_objects/**` bypassed annex and were committed as plain git blobs (24 GiB .git / 20.36 GiB packs / 1.24M objects / 753 commits). Decision: fix the glob template ([[id:dbf2]]), recreate-lean + archive-old surgery ([[id:5636]]), establish a real 2nd annex copy ([[id:0b37]]), deferred bloat warning ([[id:5f61]]). **Disk nuance (from the original 8f1c note, carried forward):** recreate-with-annex shrinks the *pack/history* (fast git ops, cheap clone, delta-free commits) but the bytes still live under `.git/annex/objects` locally (~20 GiB) until `git annex drop`-ped to the 2nd copy — local footprint only drops after the drop. <!-- id:8f1c -->
- [x] **(core)** Fixed `.gitattributes` templates in `src/zkm/store.py:20-21` (`originals/**` + `**/_objects/** annex.largefiles=anything`, + lfs analogue). RED→GREEN: `tests/test_init.py::test_gitattributes_{annexes,lfs_covers}_nested_cas_objects` (git `check-attr`, hermetic, no annex binary). Full suite 597 green. Done 2026-06-23-2251 session. <!-- id:dbf2 -->
- [x] **(store, one-off — NOT a tool feature)** Recreate-lean surgery on `~/knowledge` — DONE 2026-06-24. **Deviated from plan (better):** instead of drop-history+single-baseline, *preserved full text history* — `git filter-repo` stripped `**/_objects/**` + `msgstore.db` from all commits (397-commit markdown history, **464 MB** vs 21 GB pack), then re-attached current binaries as annex symlinks in one commit on top (399 commits total). Archive = old `.git` moved to `~/knowledge/.git-archive` (gitignored, 24 GB) + BTRFS r/o snapshot `/home/.snap-knowledge-presurgery-20260624` + fievel `knowledge.git`→`knowledge-archive.git`. Verified **0 of 33,573 CAS binaries ever dropped** (history-vs-worktree hash diff; only `msgstore.db*` + a pilot `.py` differ, both recoverable). Markdown/json = true git (diffable history); `originals/`+`_objects/` = annex (23 GB, droppable once [[id:0b37]]). Pushed lean history to fresh `fievel:knowledge.git` (local `main` == `@{u}`). Caught+fixed a `git annex add .` misstep (it annexed *everything* incl. markdown; redone so only binaries annex). Pre-existing `**/_objects/**.json` annex-by-path nuance → [[id:6c4f]]; amendments-tracking/restore-completeness → [[id:3a7d]]. <!-- id:5636 -->
- [ ] **(store, after recreate — depends [[id:5636]])** Establish a real 2nd annex copy: `git annex copy --to <fievel-annex-remote | external-HDD>` so the store isn't single-copy ("one disk = total loss" is worse than bloat; also the prerequisite for reclaiming local disk via `git annex drop`). See 2026-06-23-2251 note. <!-- id:0b37 -->
- [ ] **(core, defer/low)** `zkm verify`/`doctor`: read-only warning when a committed blob >N MB is not an annex/lfs pointer. Reporter, not guard. Gated: build on a 2nd un-annexed-blob incident (observe-before-preventing). See 2026-06-23-2251 note. <!-- id:5f61 -->
- [ ] **`/meeting` — index/cache durability: back up or sync `.zkm-index/` (esp. embeddings) to fievel.** `.zkm-index/` (`bm25.pkl` + `embeddings.npz`) is gitignored derived data, but an embeddings rebuild is **12h+** — clearing the ">2h re-derive" re-open trigger in the derivable-data policy (so this is *warranted to reconsider*, not premature). **Annexing it is the wrong tool:** the index is mutable and rewritten on every `zkm index`, so each run mints a new annex key and orphans the prior version → `.git/annex` re-bloats over time (the opposite of annex's immutable-originals fit). Better options to weigh: **(a)** a BTRFS read-only snapshot of `@home` already captures it for free (on-disk recovery, zero churn — now that the store is on btrfs); **(b)** an off-machine **post-`zkm push` hook that rsyncs `.zkm-index/` to fievel** (or a systemd timer). **Caveat (raised 2026-06-24):** `embeddings.npz` is a **ZIP container** (`numpy.savez`), so rsync's delta-transfer is defeated — any change resends the whole file. Mitigations: store uncompressed `.npy`/raw arrays for rsync-delta friendliness; accept full-file rsync (fine for a periodic copy); or use `btrfs send` (block-level, container-agnostic). Decide: snapshot-only vs rsync-hook vs btrfs-send; eager (post-push) vs timer cadence; whether to change the `.npz` layout for rsync-friendliness. Touches `embed.py` + a hook/timer. Filed 2026-06-24. <!-- id:7e21 -->
- [ ] **(zkm-eml + core) Handle spam / source-deleted mail — FULL removal, not just untag.** zkm-eml is append-only: a converted mail's `.md` (+ thread `.md`), its CAS attachment objects, annex content, and index entries all persist even when the mail is **spam** or later **deleted from the mailbox**. Need a path to *fully drop* a mail: remove the `.md` + thread `.md`, decrement/remove its CAS attachment objects (orphan sweep via `zkm rm`/`zkm gc`), purge from BM25 + dense index, and **`git annex drop`** the now-orphaned annex objects. **Two coupled questions:** (1) **spam detection** — what signals spam (notmuch `spam`/`deleted` tag, a Junk/Trash folder, mbsync flag)? zkm-eml owns detect-and-signal. (2) **general source-deletion semantics** — when a mail disappears from the mailbox, should zkm mirror the deletion? This is the broader open "treat deleted mails / source-deletions" question. **Boundaries:** core owns the removal mechanics (`rm` `.md` + `gc` CAS + index purge + annex drop); zkm-eml owns detection. Relates to [[id:25ec]] (amendments declarative retraction), `zkm rm`/`zkm gc` (CAS orphan sweep), and undercuts the "store is effectively append-only" assumption this surgery just leaned on (id:5636 verified 0 CAS objects ever dropped — *because* nothing deletes today). **Decide:** opt-in (`zkm convert eml --drop-spam`) vs automatic; hard-delete vs tombstone; deletion-propagates-from-source-state vs explicit command. Filed 2026-06-24. <!-- id:9f3c -->
- [ ] **(core, defer/low) Refine CAS-zone gitattributes: type/size-gate so small text sidecars stay in git.** The recreate-lean surgery (id:5636) confirmed the `**/_objects/** annex.largefiles=anything` rule annexes by **path, not type** — sweeping ~6,787 tiny (~395 B) `_objects/<hash>.json` CAS metadata sidecars (`sha256`/`content_types`/`producers`) and `originals/**` JSON into annex. These never bloated the pack (the bloat was media); annexing them adds an annex symlink+object for zero space win and loses git-diffability. Option: `**/_objects/**.json annex.largefiles=nothing` (or a `largerthan=` size gate) to keep CAS *metadata* in git while annexing only real binary content. Trade-off: a less-uniform "CAS = annexed" model; and changing it re-triggers annex churn (re-adds those files). Gated/low — cosmetic, not a bloat driver. Filed 2026-06-24. <!-- id:6c4f -->
- [ ] **(core) Restore-completeness: `git clone` + `git annex get` + a derived-data sync must yield a usable zkm WITHOUT regeneration.** Principle (Tobias 2026-06-24): a fresh restore should be usable as fast as possible; regeneration (re-running NER/amenders, re-embedding) should be an **optional health check** that re-derives and **diffs** against the restored state (drift/corruption detector, cf. [[id:5f61]] `zkm verify`), never a *required* restore step. **Concrete gap:** `*.amendments.json` is `.gitignore`d as "derivable" — but rebuilding it means re-running ALL amender plugins (NER = expensive >2h class), and the per-producer `producer_sets` it holds are exactly what declarative retraction ([[id:25ec]]) needs; the `.md` frontmatter (in git) carries only the MERGED result, not the per-producer breakdown. (In this store ~46k `.amendments.json` are already grandfathered-tracked, so the ignore is half-violated — inconsistent: existing ones update, new md's don't get tracked.) Amendments are small incremental text → good git fit. **Decide per derived-artifact class** {amendments, `.zkm-index/` embeddings [[id:7e21]], extraction caches, other sidecars}: **track-in-git** (small text, versioned) vs **rsync/btrfs-send** (large/binary/churny — [[id:7e21]]) vs **regenerate-on-restore** (only if genuinely cheap). Likely: track amendments (drop from `.gitignore`), rsync the index, regenerate only cheap caches; add `zkm verify --rederive` that regenerates+diffs. Revisits the derivable-data policy [[project_derivable_data_policy]] (its own ">2h re-derive" re-open trigger fires here). Filed 2026-06-24. <!-- id:3a7d -->
- [ ] **`/meeting` — core: multiple source locations per plugin (retained sources for version-aware re-processing).** Today most plugins take a single source pointer (`source_db`, `source_dir`, …) and the watermark is keyed per absolute source path, so re-running a later plugin version only re-derives from the *current* source — older/archived sources (e.g. a previous phone's WhatsApp backup, an old mail export, a superseded calendar dump) aren't re-processed even though a newer plugin version could extract more from them. Generalize to a **list of source locations** per plugin (e.g. `sources: [<path-or-config>, …]`, back-compat with the singular key) that `zkm convert <plugin>` and especially `--reprocess`/`--reprocess-all` iterate — so a plugin-version bump can sweep ALL retained sources, oldest-first, with existing dedup (key_id / sha256 / url) collapsing overlaps. Cross-cutting: **core** owns the config-schema convention + reprocess iteration; each plugin keeps its own dedup + per-source watermark. The whatsapp multi-source merge (id:9e44, manual `source_db` swap per backup + `docs/merge-old-backup.md`) is the concrete prototype to generalize. Open Qs: where retained-source *bytes* live (in-store under `originals/` vs. external path registry — ties into [[id:b7e2]] git-as-byte-source + annex availability); per-source vs. per-plugin watermark map; whether "retain the source" is a fetch-role concern (decryption boundary) or core. Decide the config shape + reprocess contract before any plugin adopts it. Filed 2026-06-23. <!-- id:7c3f -->

## Workflow / process backlog

- [ ] **conformance.run_dynamic path-resolution bug** — `run_dynamic` resolves ALL `conformance.config` values as plugin-relative paths (conformance.py ~line 345), clobbering non-path values; zkm-social cannot declare `network: linkedin`, so `zkm test social` dynamic check is impossible. Fix: only path-resolve values whose resolved path exists, or mark path keys in plugin.yaml. Found during 2026-06-12 relay handoff (zkm-social child, also in shared inbox). <!-- id:a285 -->
- [ ] (Forward-flag, deferred — D4) Design a TODO-mutating script/tool that enforces the `@{u}` done-gate at `[x]`-write time. Gate: next todo-update skill revision OR second enforcement need. <!-- id:f1cf -->

## Frontmatter schema vocabulary (decided 2026-06-13-1413-frontmatter-schema-vocabulary.md)

- [ ] Add a **core-owned scalar registry** table to `docs/plugin-spec.md` (key/type/semantics/enum) seeded with `status` (enum confirmed/cancelled/tentative), `subject`, `project`, `tags`, `sha256`, `url_sha256`; document the flat `<plugin>_<key>` rule for plugin-private scalars; mirror the rule into `ARCHITECTURE.md` §Conventions. <!-- id:4431 -->
- [ ] `zkm test` (conformance.py): warn-level finding when an emitted `.md` carries a bare scalar key not in the core-owned registry and not in `<plugin>_*` form. <!-- id:e2c4 -->
- [ ] Implement D2/D3 across plugins: keep `status:` core-owned/enum in zkm-calendar (bdfb); rename WhatsApp `status: system` → `message_type: system` (w11, reconcile with `messaging-spec.md`); namespace `recurrence_id:` → `cal_recurrence_id` (92ce) and `ocr_confidence:` → `scan_ocr_confidence` (5d7d); register `subject:` (pdf 03c2) + `project:` (claude-ai 303a) as core-owned. <!-- id:cfd1 -->
- [ ] Implement D4: zkm-social writes `url_sha256:` (not `sha256:`) for source:social; dedup index (297a) keys on it; document `sha256:` vs `url_sha256:` in `plugin-spec.md`; one-off migration/reprocess to rename the key in existing social docs. <!-- id:f3c6 -->
- [ ] zkm-whatsapp `--full-resweep` (D6): watermark-less re-sweep to heal pre-fix blanked bodies with persisted manifest text. <!-- id:8d67 -->

## NER false-positive doctrine (decided 2026-06-13-1413-ner-false-positive-doctrine.md)

- [ ] Add a **§Precision doctrine** to `docs/ner.md` (three arms: unverifiable→precision-first / checksum-verifiable→recall+valid:false / closed-set→minimal+evidence-gated); annotate each type-table row with its class; new types declare class on add. <!-- id:b99e -->
- [ ] zkm-ner currency (4352): freeze allowlist at ISO-4217 ∪ {BTC, ETH}; document the census-logged extension bar in `ner.md`. <!-- id:f40c -->
- [ ] Apply the doctrine to the open REVIEW_ME boxes: 204c (drop org fallback, zkm-social), b081 (accept lowercase IBAN + valid:false, no penalty, zkm-ner) — verify the red tests encode the doctrine arm, then tick. <!-- id:346c -->

## Amendment contract backlog

- [ ] **Core: add `entities` to `_SET_FIELDS` so declarative set-retraction applies to entities.** The shipped `emit_set` / `_retractable_values` machinery (id:25ec) only retracts the `tags` field (`_SET_FIELDS = ("tags",)`). Entities are typed `{scope,type,value}` records keyed on that tuple (the dedup key `merge_fields` already uses), not bare strings, so adding `"entities"` requires keying the producer-set diff/ref-count by `(scope,type,value)`. Prerequisite for zkm-ner scrub↔cache coherence (id:7b4e). Core-runnable (ROADMAP). See `docs/meeting-notes/2026-06-23-1807-zkm-amendments-removal-coherence.md` D1. <!-- id:29ac -->
- [ ] **Meeting: amendment replace-mode** — set-union merge (current) is correct for additive enrichment but cannot remove stale entities when extractor quality improves. `zkm scrub <plugin>` is the current workaround (N9b + future N9c). Trigger for meeting: a third amender wants single-producer-per-field semantics, OR N9c surfaces a need not solvable by scrub. See `docs/meeting-notes/2026-05-10-2142-n9b-scrub-cli.md` for design context.

## Plugin dependency loading (backlog)

- [ ] **Plugin-specific deps when loaded via importlib** — option (d) shipped as SB2 (2026-06-03): `_inject_plugin_venv` now called inside `_load_plugin_module` for dev-symlink plugins. Remaining open question: options (a)/(b)/(c) (subprocess isolation / uv-run wrapper / optional extras) for the entry-point install path where `.venv` is absent. Low urgency — entry-point installs already resolve deps via `uv tool install zkm --with zkm-<name>`. Warrants a scoping meeting only if this remaining gap causes problems in practice.
- [ ] **Re-open derivable-data meeting trigger** — re-open `docs/meeting-notes/2026-05-13-1950-derivable-expensive-data-in-git.md` decision if: first real `zkm clone` to second host makes re-derive wait painful; OR re-derive budget exceeds ~2 h (today: ~50 min).

## Publishing / distribution (backlog — from 2026-05-12-0844-publish-plugins.md)

**Orphaned publish-plugins items (A1–A9 from 2026-05-12-0844-publish-plugins.md) — done vs. pending:**

- [~] **ASAP: PyPI publishing** — ~~Stage 1 complete (2026-05-13): core `zkm` 0.5.0 published; 6 plugin names reserved as 0.0.1 stubs.~~ **CORRECTION 2026-06-21:** the "published" claim is WRONG — `https://pypi.org/pypi/zkm/json` returns "Not Found"; `zkm` (and the plugin name stubs) are **not on prod PyPI at all**. The 2026-05-13 `uv build` succeeded but the `uv publish` evidently did not land on prod PyPI (TestPyPI? aborted on creds? never verified). All publishing is **deferred indefinitely** (pip account recovery). Stage 2 (OIDC) + Session B (real plugin code) remaining. See `docs/meeting-notes/2026-05-13-1325-pypi-publish-canary.md`.
- [~] **Session B (Class 3 meeting): plugin discovery via entry-point groups** — design meeting held 2026-06-03, decisions recorded. See `docs/meeting-notes/2026-06-03-1403-session-b-plugin-entry-points.md`. Implementation items SB1–SB6 below.
- [ ] **Stage 2: OIDC Trusted Publisher + `.github/workflows/release.yml` in all 7 repos** — tokenless CI publish; closes auto-publish loop with the post-commit auto-tag TODO. Per-project tokens available (created after first publish).
  - [~] **Ambiguity: bare first/last names in user_names are not unique** — Resolved 2026-05-19: `user_names` mechanism dropped entirely (N15a). See `docs/meeting-notes/2026-05-19-1610-ner-user-names-drop.md`.

## zkm-eml backlog (M-prefix) — migrated from plugins/zkm-eml/TODO.md 2026-05-13

Items migrated from the orphan per-plugin TODO file (pre-polyrepo-split artefact). Prefix convention documented in `CLAUDE.md`.

- [ ] **M1.** Decoration vs inline-photo classification — heuristics to distinguish logos/banners from informational inline images (size, repeated cid across senders, alt-text, tracking domains). Currently all attachments treated uniformly.
- [ ] **M4.** Drafts — optional "follow draft updates" mode (Message-ID/content changes on each save). YAGNI for now.

## Test corpus / fixture infrastructure (decided 2026-05-29-1112-synthetic-test-corpus.md)

**Status: COMPLETE (2026-06-01).** Committed `.md` corpus (`tests/fixtures/corpus/`, 6 docs + CORPUS_MANIFEST.json), three pathological anchors (`tests/fixtures/pathological/`), `scripts/seed_dev_store.py`, `tests/conftest.py` `store`+`make_note` fixtures, corpus README with regen procedure, zkm-eml generator (`generate_corpus.py`) + roundtrip test (`test_corpus_roundtrip.py`), `zkm test <plugin>` conformance validator. See `docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md`.
