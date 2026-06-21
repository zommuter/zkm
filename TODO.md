
# zkm — Phase 2 TODO

See `CLAUDE.md` for architecture overview. See `docs/phase2-plan.md` for sequencing.
Completed Phase 1 tasks archived in `docs/phase1-done.md`.

## Cross-project

- [ ] **Cross-project (triad) — `/meeting`:** discuss the potentially connecting dots between **zkm
  infrastructure** (embeddings / semantic retrieval / knowledge-mgmt) and the `.mw`/toesnail/collAIb triad.
  toesnail is the documented triad hub (`toesnail/docs/dependencies.md`); a session would decide whether/how
  zkm becomes a node in that dependency map. **MIRRORED in `toesnail/TODO.md` under the same `id:4159`** — keep
  both copies in sync MANUALLY (no automated cross-PROJECT sync; relay `--cross-ledger` is intra-repo only,
  inbox routing is one-way). Wherever worked/closed, tick the twin. Likely a manual `/meeting`. <!-- id:4159 -->

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

- [ ] **W6-follow-up: manifest media persistence.** `_reconstitute()` sets `media_path=None`/`mime_type=None`, so when a day file is rewritten for new messages, earlier media lines lose their `[media: … → …]` body text (CAS object is safe, symlink stays). Fix: persist `media:{mime,sha256}` in the `messages:` manifest entries — a W1 doc-type schema extension. Gate: becomes noticeable in practice (day file rewrites with mixed text+media messages). <!-- id:w6f -->
- [ ] **W-key.** Secret management for WhatsApp backup key: support Bitwarden CLI (`bw get password`) and/or OS keyring (secret-service, same pattern as zomni SSH setup) as sources for the 64-char hex key passed to wa-crypt-tools. Gitignoring `.zkm-secrets.yaml` + `*.key` blocks automation. Plugin config key `whatsapp_backup_key_source` (e.g. `bitwarden:<item-id>` or `keyring:<service>:<account>`). <!-- id:w-key -->
- [ ] **W7 (deferred design note).** Smarter segmentation (burst/temporal-density or per-thread) as additive re-segmentation; MUST NOT rewrite chat-level thread_id. Trigger: v1 live + concrete retrieval pain from day-boundaries. See `docs/meeting-notes/2026-06-03-0952-zkm-whatsapp-scope.md`. <!-- id:367f -->
- [ ] **W8. Owner JID auto-detection.** `owner_jid` can be derived from the db: `SELECT user || '@' || server FROM jid WHERE _id = (SELECT sender_jid_row_id FROM message WHERE from_me=1 AND sender_jid_row_id IS NOT NULL GROUP BY sender_jid_row_id ORDER BY COUNT(*) DESC LIMIT 1)`. Make `owner_jid` optional in config; fall back to this query when absent. Keep explicit config as override for multi-account edge case.
- [ ] **W10. Auto-decryption trigger from Syncthing.** Syncthing delivers updated `msgstore.db.crypt15` to `~/knowledge/inbox/whatsapp/`; need a systemd `.path` unit (or inotifywait hook) that runs wa-crypt-tools decrypt on change, then optionally triggers `zkm convert whatsapp`. Design note: where does the decryption key come from (W-key) + how to avoid re-decrypt when crypt15 is unchanged (checksum gate). Depends on W-key.
- [ ] **W11. Phone number change tracking.** `message_system_number_change` table records WA-internal number migrations. Additionally, "hey here's my new number" plaintext messages are a common informal signal. Design: (1) parse `message_system_number_change` → emit a system-event entity or annotation linking old→new JID; (2) heuristic detection of informal "new number" messages (patterns in multiple languages) → flag for human confirmation. Relates to entity alias/synonym linking (Phase 4). <!-- id:w11 -->

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
- [ ] **STT3 — Multi-model voting/agreement eval harness.** Run multiple ASR models over real voice
  messages; compare/vote on (dis)agreement to judge quality (bench template: helferli `asr_bench.py`).
  Separate quality tool, not v1 ingest. Gate: STT1 shipped. See
  `docs/meeting-notes/2026-06-21-2207-zkm-stt-scope.md`. <!-- id:4ab4 -->
- [ ] **STT4 — zkm-stt roadmap enrichments.** Speaker labels / diarisation, background-noise
  identification + filtering, sentiment analysis, word-level timestamps, streaming. Each gated on a
  concrete need + (ML-shaped ones) evidence before infra. See
  `docs/meeting-notes/2026-06-21-2207-zkm-stt-scope.md`. <!-- id:fa7b -->

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

- [x] **[core] Declarative-set retract primitive in `src/zkm/amendments.py`** — shipped + merged (494f1f9, 578 tests green); `v0.15.0` tag pushed to origin+github 2026-06-21. **`uv publish` deferred indefinitely** (pip account recovery; `zkm` not currently on PyPI) — see Stage 2 OIDC item. Design: `docs/meeting-notes/2026-06-18-1944-f103-tag-removal-core-semantic.md`. <!-- id:25ec -->
- [ ] **Meeting: amendment replace-mode** — set-union merge (current) is correct for additive enrichment but cannot remove stale entities when extractor quality improves. `zkm scrub <plugin>` is the current workaround (N9b + future N9c). Trigger for meeting: a third amender wants single-producer-per-field semantics, OR N9c surfaces a need not solvable by scrub. See `docs/meeting-notes/2026-05-10-2142-n9b-scrub-cli.md` for design context.

## Plugin dependency loading (backlog)

- [ ] **Plugin-specific deps when loaded via importlib** — option (d) shipped as SB2 (2026-06-03): `_inject_plugin_venv` now called inside `_load_plugin_module` for dev-symlink plugins. Remaining open question: options (a)/(b)/(c) (subprocess isolation / uv-run wrapper / optional extras) for the entry-point install path where `.venv` is absent. Low urgency — entry-point installs already resolve deps via `uv tool install zkm --with zkm-<name>`. Warrants a scoping meeting only if this remaining gap causes problems in practice.
- [ ] **Re-open derivable-data meeting trigger** — re-open `docs/meeting-notes/2026-05-13-1950-derivable-expensive-data-in-git.md` decision if: first real `zkm clone` to second host makes re-derive wait painful; OR re-derive budget exceeds ~2 h (today: ~50 min).

## Publishing / distribution (backlog — from 2026-05-12-0844-publish-plugins.md)

**Orphaned publish-plugins items (A1–A9 from 2026-05-12-0844-publish-plugins.md) — done vs. pending:**

- [~] **ASAP: PyPI publishing** — Stage 1 complete (2026-05-13): core `zkm` 0.5.0 published; 6 plugin names reserved as 0.0.1 stubs. Stage 2 (OIDC) + Session B (real plugin code) remaining. See `docs/meeting-notes/2026-05-13-1325-pypi-publish-canary.md`.
- [~] **Session B (Class 3 meeting): plugin discovery via entry-point groups** — design meeting held 2026-06-03, decisions recorded. See `docs/meeting-notes/2026-06-03-1403-session-b-plugin-entry-points.md`. Implementation items SB1–SB6 below.
- [ ] **Stage 2: OIDC Trusted Publisher + `.github/workflows/release.yml` in all 7 repos** — tokenless CI publish; closes auto-publish loop with the post-commit auto-tag TODO. Per-project tokens available (created after first publish).
  - [~] **Ambiguity: bare first/last names in user_names are not unique** — Resolved 2026-05-19: `user_names` mechanism dropped entirely (N15a). See `docs/meeting-notes/2026-05-19-1610-ner-user-names-drop.md`.

## zkm-eml backlog (M-prefix) — migrated from plugins/zkm-eml/TODO.md 2026-05-13

Items migrated from the orphan per-plugin TODO file (pre-polyrepo-split artefact). Prefix convention documented in `CLAUDE.md`.

- [ ] **M1.** Decoration vs inline-photo classification — heuristics to distinguish logos/banners from informational inline images (size, repeated cid across senders, alt-text, tracking domains). Currently all attachments treated uniformly.
- [ ] **M4.** Drafts — optional "follow draft updates" mode (Message-ID/content changes on each save). YAGNI for now.

## Test corpus / fixture infrastructure (decided 2026-05-29-1112-synthetic-test-corpus.md)

**Status: COMPLETE (2026-06-01).** Committed `.md` corpus (`tests/fixtures/corpus/`, 6 docs + CORPUS_MANIFEST.json), three pathological anchors (`tests/fixtures/pathological/`), `scripts/seed_dev_store.py`, `tests/conftest.py` `store`+`make_note` fixtures, corpus README with regen procedure, zkm-eml generator (`generate_corpus.py`) + roundtrip test (`test_corpus_roundtrip.py`), `zkm test <plugin>` conformance validator. See `docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md`.
