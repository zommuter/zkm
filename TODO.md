# zkm — Phase 2 TODO

See `CLAUDE.md` for architecture overview. See `docs/phase2-plan.md` for sequencing.
Completed Phase 1 tasks archived in `docs/phase1-done.md`.

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
- [x] **N-datetime L1.** zkm-ner: new γ `type: datetime` + `zkm.canonical.datetime` normaliser (ISO 8601, resolved against doc `date` as anchor for relatives like "Thursday"/"30. Juni", bilingual DE/EN via `dateparser`) + spaCy DATE/TIME span mapping. Lives in `plugins/zkm-ner/`. Contract: a relative-date fixture in a doc with a known `date` resolves to the correct ISO 8601 canonical. Parallel track to V1, does not block it. See `docs/meeting-notes/2026-06-01-1334-contacts-calendar-plugins.md`. <!-- id:805f --> **Shipped zkm-ner v0.17.0 — 280 tests pass; active on EN docs (de_core_news_sm emits no DATE spans).**
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

- [ ] **E9 follow-up (field-test 7c + embed rebuild) — root cause FIXED 2026-05-21, rebuild PAUSED mid-run.** `zkm convert ner` is redundant (entities[] already populated). The "embed 500" was a **deterministic chunk-size vs. server-batch-size mismatch** (dense chunks >2048 tokens), NOT a transient bug — root-caused by capturing the body. Fixed: zomni bge-m3 `--batch-size`+`--ubatch-size` 8192; zkm v0.9.0 split fallback; v0.9.1 timeout 180s. Rebuild ran clean to a **1796-doc checkpoint**, then paused. **Remaining: (1) resume `zkm index` to completion [402c], (2) run 7c probe [2c6e], (3) close this item.** Full handover in `docs/embed-rebuild-500-investigation.md`.
- [ ] **[embed] Resume + complete the schema-4 embed rebuild.** **IN PROGRESS 2026-05-29** — ops steps done (PID 95944 killed, `zkm scrub zkm-eml` run, `zkm index` started clean). Running at PID 189608, 6496/92458 chunks, ETA ~7.5h. Riku gate: zero oversized/split warnings in journal (clean). Closes when `zkm doctor` embed docs == md count. <!-- id:402c -->
- [ ] **[embed] Run field-test 7c typed-value probe + close E9.** After rebuild completes (`zkm doctor` embed docs == md count, schema 3): derive a real IBAN prefix from an `entities[].type: iban` value, `zkm search "<prefix>" --no-dense -k 5`, verify top hit has IBAN in `entities[]` not body; repeat for `amount`. Record in `docs/field-test-bge-m3.md` step 7. **Probe procedure VALIDATED 2026-05-29** on synthetic corpus (`tests/test_entity_search.py` 4/4 pass; E8 entity-canonical BM25 confirmed — see `docs/field-test-bge-m3.md` step 7c). Remaining: run same probe against **production** store once rebuild completes. <!-- id:2c6e --> <!-- id:9e34 -->
- [~] **E13: N9g re-evaluation** — CLOSED MOOT 2026-05-21. Audit confirmed: (1) pattern-overlay overlap filter prevents spaCy from mislabelling value-type strings (amounts, IBANs, etc.); (2) N9c POS filter + `_COMMONNOUN_STOPLIST` handles common-noun FPs; (3) `_SALUTATION_BLOCKLIST` covers sign-off/salutation FPs; (4) `drop_structural_artefacts` + `drop_section_link_artefacts` cover structural pollution; (5) E12 shipped signature-scope extraction. No standalone "general body-NER cleanup" workstream remains. See `docs/meeting-notes/2026-05-12-1500-entity-vs-datamining.md`.

**Named deferrals (with triggers):**
- P3 typed query language — defer until γ + P2 live ≥1 month AND ≥1 concrete typed-query request.
- PII redaction implementation — defer until sharing scenario lands. Architectural design in E10.
- Entity-DB checksum-fail "ignore / correct?" policy — defer until ≥50 `valid: false` entries accumulate.
- `valid: false` forward-flag: re-evaluate dropping the per-type suspicious heuristic (Option 3) after ≥1 month observation.
- Crypto/stock-ticker domain scope — defer; revisit if real use case lands.
- WebUI typed-query hint UX — Phase 3 design concern.

- [ ] **Entity alias / synonym linking (Phase 4 backlog)** — `SBB CFF FFS` (DE/FR/IT names for Swiss Federal Railways) highlights that the same real-world entity can appear under multiple mention strings (abbreviations, translations, official variants). Likewise, persons appear under nicknames, maiden names, or initials. Deferred to Phase 4 alongside manual-merge tooling; design note needed in `docs/entity-model.md` before implementation. No heuristic auto-merge — human-confirmed alias pairs only.

- [ ] Session 15 (scoping, not implementation): meeting on zkm-whatsapp core gaps — (a) non-git source state / `zkm.state` helper, (b) per-store YAML config replacing long env-var lists, (c) stable-ID synthesis contract; deliverable: `docs/meeting-notes/YYYY-MM-DD-whatsapp-scope.md`

## Phase 2 — mbsync auto-trigger (decided 2026-05-08-mbsync-hook.md)

- [ ] from 2026-06-05: review journald evidence for convert-overlap; decide on lock if observed.
- [~] **zkm-eml signature stripping** — promoted 2026-05-12 to first-class action item: see **N9g-pre** above. (Original framing 2026-05-10-1640-n9b: heuristic detection of email signature blocks before markdown render; addresses popularity skew of personal contact details. Re-scoped from "stripping" to "typed extraction" in N9g-pre.)

## Phase 2 — SIGUSR1 progress + `zkm status` (decided 2026-05-08-1913-sigusr1-status.md)

Scope: `convert` and `index` (BM25 + embed phases) only. `query`, `clone`, `push`, `pull` explicitly out. Daemon/supervisor model deferred (N<2 background callers). Host-wide multi-store registry, historical run log, `--kill`, `--watch`, live-tail all deferred.

**Spawned follow-ups (from 2026-05-14 concurrent-run-guard meeting):**

- [ ] **Future re-evaluation trigger — local DB with git-tracked autoexport-on-write** — possible architectural pivot from sidecar-files-on-disk. Re-open if any one trigger fires: (a) concurrent-write bugs in sidecars become frequent; (b) WebUI read-write workload makes file-level locking visibly painful; (c) cross-machine sync stops being purely `git pull`-based. See `~/.claude/projects/-home-tobias-src-zkm/memory/project_db_pivot_trigger.md`.
- [ ] **`zkm queue` design meeting (Phase 3 daemon precursor)** — when attach semantics become a real ask (N=2 consumers wanting `--wait-for-busy`), open a meeting on a queue manager: PID-file → in-memory daemon queue; fail-fast → `attach/wait/wait-rerun` modes; `zkm status` polling → WebSocket push (Phase 3 WebUI alignment). Floor any successor must preserve: the v1 contract in `~/.claude/projects/-home-tobias-src-zkm/memory/project_concurrent_run_guard_contract.md`.
- [ ] from 2026-06-11: review `journalctl -t zkm-index-lock-watch` for lock-contention events; decide on stronger protection if any observed.

**Verification checklist** (313 tests passing, 2026-05-08):
1. `zkm convert zkm-eml` in terminal A → `zkm status` in terminal B shows one row with fresh `last_updated`.
2. `kill -USR1 <pid>` directly → dd-style line on convert's stderr.
3. `zkm index` → `phase` toggles `bm25` → `embed`; `zkm index --no-embed` stays at `bm25`.
4. SIGKILL the process → next `zkm status` drops stale file with stderr notice.
5. `zkm status --json | jq` → valid JSON array.

## zkm-vcard (V-prefix) — contacts plugin (decided 2026-06-01-1334-contacts-calendar-plugins.md)

Ingest-only, source-agnostic. Reads a local tree of standard `.vcf` files via `source_dir` (from proton-moresync / Google Takeout / vdirsyncer / any client export). Never authenticates or fetches. Phase 3 by roadmap, but buildable now against hand-exported fixtures.

- [ ] **V1.** Create `plugins/zkm-vcard/` repo: vCard→md converter — `contacts/<slug>.md` per vCard UID, human-readable body (FN/ORG/TITLE/emails/phones/ADR/NOTE), PHOTO→CAS (`zkm.cas.write_object`), UID dedup (like eml message_id), populated `scope: contact` `entities[]` (email_address/rfc5321, phone_number/E.164, org, person/FN, url, social_handle.<platform>, linkedin_profile, github_profile), `tags:[]` placeholder. Contract: no fetch, no identity-merge. See `docs/meeting-notes/2026-06-01-1334-contacts-calendar-plugins.md`. <!-- id:e5f9 -->

**Scope constraints (from meeting):**
- Contacts are authoritative structured-first data — emit `entities[]` populated, not empty.
- `scope: contact` entities coexist with `scope: body` NER (zkm-ner amends NOTE field). Dedup key `(scope,type,value)`.
- NO identity-merge — no auto-linking contact identity to NER mentions or mail participants. Phase 4 manual-merge, human-confirmed pairs only.
- No fetch, no credentials, no gazetteer/recognition-overlay (forward-flags, not v1 scope).
- Cross-link with `TODO.md:81` social-network scoping meeting (zkm-vcard front-runs it for structured-export case). <!-- id:2638 -->

## zkm-calendar (C-prefix) — calendar plugin (decided 2026-06-01-1334-contacts-calendar-plugins.md)

**Deferred — own meeting/build when zkm-vcard ships.** Ingest-only, standards-parser only (RFC 5545), never NLP. Build order: zkm-vcard → zkm-calendar.

- [ ] **C1.** (deferred) `plugins/zkm-calendar/` repo: VEVENT→message-like md per `docs/messaging-spec.md` — `message_id`=iCal UID, `date`=DTSTART, `participants[]` from ORGANIZER/ATTENDEE (roles `organizer`/`attendee`/`optional`/`invitee` already defined), body=SUMMARY+DESCRIPTION+LOCATION+time, RRULE series → one `thread_id`, ATTACH→CAS. Dedup-on-UID (RFC 5545 globally unique) merges mail-invite + calendar-tree copies for free; mail `.ics` routed via existing inbox fan-out (content-type claim; no eml↔calendar coupling). Standards-parser only. See `docs/meeting-notes/2026-06-01-1334-contacts-calendar-plugins.md`. <!-- id:cca0 -->
- [ ] (deferred) **zkm fetch** core orchestrator: config maps `source → external fetch command + output dir`; `zkm fetch <source>` shells out, deposits standard files, `zkm convert` ingests. mbsync-equivalent lever in core, not per-source systemd sprawl. See `docs/meeting-notes/2026-06-01-1334-contacts-calendar-plugins.md`. <!-- id:473c -->

## Plugin backlog — conversation / AI session sources

- [ ] **`zkm-claude-code`** — import Claude Code session transcripts (`.claude/projects/*/transcripts/*.json` or similar). Key fields: session ID, timestamp, project path, messages. Stable ID: session ID + message index. Source state: git-commit watermark on transcript dir or mtime-based. Scope and trigger path need a scoping session before implementation.
- [ ] **`zkm-claude-ai`** — import claude.ai conversation exports (JSON or markdown). Same stable-ID and amendment concerns as zkm-claude-code; likely shares core parsing logic. **Scoping note (2026-05-10 meeting):** the interesting corpus is `conversations.json` + per-project conversation IDs (not `docs[]` — those are a round-trip backup of disk content, see `~/.claude/projects/-home-tobias-src-zkm/memory/zkm_claude_plugin.md`). Hold a dedicated scoping meeting before implementation to decide start order (zkm-claude-ai vs zkm-claude-code first).
- [ ] **Other AI provider sessions** (ChatGPT exports, Gemini, etc.) — deferred until zkm-claude-code lands and the session-import pattern is proven. N=2 for a shared `zkm.session` helper module requires at least two providers implemented.

## Plugin backlog — social networks

- [ ] **Meeting: social-network profile scraping scope** — LinkedIn profile photo + resume/CV export, and equivalent for other networks (Instagram, Twitter/X, Mastodon, GitHub bio, etc.). Two distinct sub-questions: (1) *identity card* — profile data as a per-person entity page (photo, headline, current employer, skills); (2) *activity feed* — posts, reactions, comments, tags. Both have legal/TOS constraints that differ by network (takeout export vs. API vs. scraping). Needs a scoping meeting before any implementation. Key design questions: which networks are in scope, what the canonical markdown shape is, and whether profile data goes into `entities[]` (γ schema) or its own document type.
- [ ] **Meeting: takeout / export archive import** — personal data exports from Google Takeout, Facebook "Download Your Data", Instagram, LinkedIn, Twitter/X, etc. are structured archives (ZIP + JSON/HTML). Distinct from live scraping: deterministic, offline, privacy-safe. Sub-questions: (1) which export formats to support first (LinkedIn most structured); (2) shared `zkm.takeout` extraction helper vs. per-network plugins; (3) "being tagged" in others' posts as a distinct entity-mention type (requires cross-document resolution). Warrants a scoping meeting; likely a prerequisite for the live-scraping meeting above.

## Amendment contract backlog

- [ ] **Meeting: amendment replace-mode** — set-union merge (current) is correct for additive enrichment but cannot remove stale entities when extractor quality improves. `zkm scrub <plugin>` is the current workaround (N9b + future N9c). Trigger for meeting: a third amender wants single-producer-per-field semantics, OR N9c surfaces a need not solvable by scrub. See `docs/meeting-notes/2026-05-10-2142-n9b-scrub-cli.md` for design context.

## Plugin dependency loading (backlog)

- [ ] **Plugin-specific deps when loaded via importlib** — when `zkm convert` loads a plugin via `importlib.util.spec_from_file_location` into the main process, the plugin runs in the main zkm venv which lacks plugin-only deps (e.g. `ftfy`, `charset-normalizer` in zkm-eml). Current workaround: `convert.py` injects `.venv/lib/python*/site-packages` into `sys.path` at import time. Explore proper solutions: (a) subprocess isolation per plugin, (b) uv-run-in-plugin-venv wrapper, (c) declare plugin deps as optional extras in core and install them together. Warrants a scoping meeting before changing the plugin loading model.
- [ ] **Re-open derivable-data meeting trigger** — re-open `docs/meeting-notes/2026-05-13-1950-derivable-expensive-data-in-git.md` decision if: first real `zkm clone` to second host makes re-derive wait painful; OR re-derive budget exceeds ~2 h (today: ~50 min).
- [ ] **Meeting: verb order** — `zkm convert <plugin>` vs `zkm <plugin> convert` / `zkm <plugin> run`; the latter matches git-plugin style and disambiguates status display. Scoped separately after prefix-naming decision landed.

## Publishing / distribution (backlog — from 2026-05-12-0844-publish-plugins.md)

**Orphaned publish-plugins items (A1–A9 from 2026-05-12-0844-publish-plugins.md) — done vs. pending:**

- [~] **ASAP: PyPI publishing** — Stage 1 complete (2026-05-13): core `zkm` 0.5.0 published; 6 plugin names reserved as 0.0.1 stubs. Stage 2 (OIDC) + Session B (real plugin code) remaining. See `docs/meeting-notes/2026-05-13-1325-pypi-publish-canary.md`.
- [ ] **Session B (Class 3 meeting): plugin discovery via entry-point groups** — `[project.entry-points."zkm.plugins"]` in each plugin + extend `convert.py:find_plugin`; replaces 0.0.1 stubs with real wheels; architectural change, needs design meeting.
- [ ] **Stage 2: OIDC Trusted Publisher + `.github/workflows/release.yml` in all 7 repos** — tokenless CI publish; closes auto-publish loop with the post-commit auto-tag TODO. Per-project tokens available (created after first publish).
  - [~] **Ambiguity: bare first/last names in user_names are not unique** — Resolved 2026-05-19: `user_names` mechanism dropped entirely (N15a). See `docs/meeting-notes/2026-05-19-1610-ner-user-names-drop.md`.

## zkm-eml backlog (M-prefix) — migrated from plugins/zkm-eml/TODO.md 2026-05-13

Items migrated from the orphan per-plugin TODO file (pre-polyrepo-split artefact). Prefix convention documented in `CLAUDE.md`.

- [ ] **M1.** Decoration vs inline-photo classification — heuristics to distinguish logos/banners from informational inline images (size, repeated cid across senders, alt-text, tracking domains). Currently all attachments treated uniformly.
- [ ] **M4.** Drafts — optional "follow draft updates" mode (Message-ID/content changes on each save). YAGNI for now.

## Test corpus / fixture infrastructure (decided 2026-05-29-1112-synthetic-test-corpus.md)

Synthetic small corpus to replace multi-hour embed rebuild during dev/test. Two outputs sharing one source: a committed `.md` corpus for core pytest + a `seed_dev_store.py` for sub-second offline iteration. See `docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md` for polyrepo split, drift-guard design, and the title/subject trap rationale.

- [ ] **[deferred / future planning] `zkm test <plugin>` conformance-validator command** — builds on roundtrip harness; conformance-validator (not bare runner) interpretation; advisory-vs-gating TBD. (see docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md) <!-- id:aa77 -->
- [ ] **Production 7c probe:** run `zkm search "DE44500105175407324931" --no-dense` + `zkm search "CHF 1250" --no-dense` against real store once embed rebuild completes (`zkm doctor` embed docs == md count). Verify top hits have `type:iban`/`type:amount` in `entities[]`. Record in `docs/field-test-bge-m3.md` step 7. Close `[2c6e]`. See `docs/meeting-notes/2026-05-29-1443-7c-probe-synthetic-corpus.md`. <!-- id:c18c -->
