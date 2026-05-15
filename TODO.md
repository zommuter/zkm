# zkm — Phase 2 TODO

See `CLAUDE.md` for architecture overview. See `docs/phase2-plan.md` for sequencing.
Completed Phase 1 tasks archived in `docs/phase1-done.md`.

## Infrastructure / cross-project


## Phase 2 session 6 — hybrid search quality


## Phase 2 session 7 — aya expansion bugs (3 blockers found in live test)


## Query quality (post-MVP backlog)


## Phase 2.5 — next plugins (decided 2026-05-08-next-plugins.md, 2026-05-08-information-flow.md)

Order: pre-flight specs → zkm.amendments lib → photo → pdf → scan → notmuch → (scoping) → whatsapp.
WhatsApp requires three core additions before its own session; see session 15.

Pre-flight sessions (9a–9d) must land before any plugin session starts.

## Phase 2.5 — NER (decided 2026-05-10-1148-entity-extraction.md)

NER lands before whatsapp. `zkm convert <plugin>` runs amenders default-on (`--no-amenders` to skip). Session 9d extraction-cache transitions from design-only to implementation alongside zkm-ner.

    **Final state (post two convert+scrub cycles):** 471,894 total mentions (-34.4% vs 719,504 post-N9b). Legit-ORG target MET: Google LLC ×3204, PayPal ×1892, Amazon WS ×1074, SBB ×542, ETH ×485 all intact. Person top is now Tobias Kienzler ×11,270. Second cycle stable (+18 net entities only).
    **Remaining FP classes found:**
    - *Class 5 (pipe cell artifacts):* `'| |'` ×2664, `'| | |'` ×679, `'|  |'` ×373 — inline empty table cells within data rows; N9b only strips full pure-pipe rows. Fix: post-extraction value filter rejecting `^[\s|]+$`. See N9c backlog below.
    - *English-noun limitation in isolated POS:* `'Learn'` ×1032, `'Link'` ×679, `'Actions'` ×430, `'Download'` ×357 — German model tags these PROPN/X (foreign word), passes isolated POS. Fix: try EN model when DE model returns PROPN for a foreign-looking value.
    - *Multi-word phrase FPs (N9d territory):* `'Hallo Tobias'` ×1930, `'Best Regards'` ×1139, `'Guten Tag Herr Kienzler'` ×444, `'Hello Tobias'` ×392 — bypass multi-word skip in isolated POS; need LLM verifier or phrase-pattern blocklist.
    - *Boilerplate legal text in ORG:* `'L-2449 Luxembourg RCS Luxembourg'` ×859, `'S.C.A. Société en commandite par actions'` ×854 — legitimate entity names but high-frequency boilerplate; defer.
    **Note:** this convert ran with pre-N9c code; in-pipeline POS filter not yet applied. A fresh `zkm convert ner` will bust cache (new version key) and re-extract with POS filter, which will prevent new FPs — required before calling N9c fully clean.
- [ ] **N9e (backlog — no live trigger path).** Closed-loop verifier denylist — append-only JSONL at `<store>/.zkm-state/ner-verifier-denylist.jsonl`; one record per `(value, type)`: `{value, type, verdict, source, model_version, first_seen, heuristic_would, n_observations}`. `source ∈ {verifier, heuristic, manual}`; `verdict ∈ {drop, keep}` (drops-only direction designed; keeps-becoming-sticky deferred — precedence ambiguity). **Gate: (N9d shipped) AND (≥5 verifier-override cases observed in Stage 2 pilot).** **Status 2026-05-12: gate cannot fire — N9d closed via Gate C; verifier did not ship.** Entry remains in backlog for archival reference; no implementation path until/unless a successor verifier project replaces the gate condition. Conflict-resolution for allow+deny overlap unresolved — design meeting required if revived.
  - [~] **N9d-9.** Per-language accuracy lens — **not pursued** (gate closure pre-empts; reopen only if N9d is revived under a different model).
  - [~] **N9d-11.** N9e sketch into `docs/ner.md` — **not pursued** (N9e gate condition is moot; see N9e backlog entry).

**Scope constraints (from meeting):**
- `value:` strings are *mention strings*, never UIDs. No `id:`, `same_as:`, cross-doc clustering.
- Name alone is NOT a UID — manual-merge tooling deferred to Phase 4.
- Co-reference within doc deferred to v2; intra-doc pronoun coref not in scope.
- GLiNER is opt-in only; sentence-level language routing out of scope.


## Phase 2.5 — γ schema rollout (decided 2026-05-12-1500-entity-vs-datamining.md)

Sequencing: E1+E2+E3 (schema + amendments + normaliser lib) → E4 (suspicious dispatch) → E6 (`amount` pilot) → E7 (more value-types) → E8+E9 (P2 index integration + field-test). Each step rollback-able. ~6–8 sessions total.



**Named deferrals (with triggers):**
- P3 typed query language — defer until γ + P2 live ≥1 month AND ≥1 concrete typed-query request.
- PII redaction implementation — defer until sharing scenario lands. Architectural design in E10.
- Entity-DB checksum-fail "ignore / correct?" policy — defer until ≥50 `valid: false` entries accumulate.
- `valid: false` forward-flag: re-evaluate dropping the per-type suspicious heuristic (Option 3) after ≥1 month observation.
- Crypto/stock-ticker domain scope — defer; revisit if real use case lands.
- WebUI typed-query hint UX — Phase 3 design concern.




- [ ] **Entity alias / synonym linking (Phase 4 backlog)** — `SBB CFF FFS` (DE/FR/IT names for Swiss Federal Railways) highlights that the same real-world entity can appear under multiple mention strings (abbreviations, translations, official variants). Likewise, persons appear under nicknames, maiden names, or initials. Deferred to Phase 4 alongside manual-merge tooling; design note needed in `docs/entity-model.md` before implementation. No heuristic auto-merge — human-confirmed alias pairs only.

- [ ] Session 15 (scoping, not implementation): meeting on zkm-whatsapp core gaps — (a) non-git source state / `zkm.state` helper, (b) per-store YAML config replacing long env-var lists, (c) stable-ID synthesis contract; deliverable: `docs/meeting-notes/YYYY-MM-DD-whatsapp-scope.md`

## Phase 2 housekeeping — repo reorg (decided 2026-05-08-repo-reorg.md)


## Phase 2 session 8 — doc chunking (core)


## Phase 2 session 1 — zkm-eml hot-fix


## Phase 2 session 2 — embed index fixes


## Phase 2 session 3 — core library

See `docs/object-storage.md` for the spec contract.


## Phase 2 session 4 — plugin migration

(Only after session 3 core library is complete and field-tested.)


## Phase 2 session 5 — hygiene commands

(Only after one week of session 4 in real use, per `docs/phase2-plan.md`.)


## `zkm store` — git-like store management

The store is a git repo; zkm should expose a thin wrapper that handles
git-annex / git-lfs automatically so the user doesn't have to think about it.


Design note: these commands read `.zkm-config` to know the backend and dispatch accordingly. The user never has to type `git annex` directly.

## Incremental processing (backlog)


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

## Plugin backlog — conversation / AI session sources

- [ ] **`zkm-claude-code`** — import Claude Code session transcripts (`.claude/projects/*/transcripts/*.json` or similar). Key fields: session ID, timestamp, project path, messages. Stable ID: session ID + message index. Source state: git-commit watermark on transcript dir or mtime-based. Scope and trigger path need a scoping session before implementation.
- [ ] **`zkm-claude-ai`** — import claude.ai conversation exports (JSON or markdown). Same stable-ID and amendment concerns as zkm-claude-code; likely shares core parsing logic. **Scoping note (2026-05-10 meeting):** the interesting corpus is `conversations.json` + per-project conversation IDs (not `docs[]` — those are a round-trip backup of disk content, see `~/.claude/projects/-home-tobias-src-zkm/memory/zkm_claude_plugin.md`). Hold a dedicated scoping meeting before implementation to decide start order (zkm-claude-ai vs zkm-claude-code first).
- [ ] **Other AI provider sessions** (ChatGPT exports, Gemini, etc.) — deferred until zkm-claude-code lands and the session-import pattern is proven. N=2 for a shared `zkm.session` helper module requires at least two providers implemented.

## Plugin backlog — social networks

- [ ] **Meeting: social-network profile scraping scope** — LinkedIn profile photo + resume/CV export, and equivalent for other networks (Instagram, Twitter/X, Mastodon, GitHub bio, etc.). Two distinct sub-questions: (1) *identity card* — profile data as a per-person entity page (photo, headline, current employer, skills); (2) *activity feed* — posts, reactions, comments, tags. Both have legal/TOS constraints that differ by network (takeout export vs. API vs. scraping). Needs a scoping meeting before any implementation. Key design questions: which networks are in scope, what the canonical markdown shape is, and whether profile data goes into `entities[]` (γ schema) or its own document type.
- [ ] **Meeting: takeout / export archive import** — personal data exports from Google Takeout, Facebook "Download Your Data", Instagram, LinkedIn, Twitter/X, etc. are structured archives (ZIP + JSON/HTML). Distinct from live scraping: deterministic, offline, privacy-safe. Sub-questions: (1) which export formats to support first (LinkedIn most structured); (2) shared `zkm.takeout` extraction helper vs. per-network plugins; (3) "being tagged" in others' posts as a distinct entity-mention type (requires cross-document resolution). Warrants a scoping meeting; likely a prerequisite for the live-scraping meeting above.

## Encoding / text quality (backlog)


## Versioning — retroactive tags (decided 2026-05-08-2318-tagging-cadence.md)

Convention: bump-and-tag + loose-0.x + plain `vX.Y.Z` per repo. See `CLAUDE.md` "Versioning".


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
- [ ] **Apply user_names to live store + scrub** — add `ner: { user_names: [Tobias, Kienzler, "Tobias Kienzler"] }` (or preferred forms) to `<store>/zkm-config.yaml`; run `zkm scrub ner` to retroactively remove greeting FPs (`'Hallo Tobias' ×1930`, `'Guten Tag Herr Kienzler' ×444`) from live store; run `zkm convert ner` for ongoing filtering on new mail.

## zkm-eml backlog (M-prefix) — migrated from plugins/zkm-eml/TODO.md 2026-05-13

Items migrated from the orphan per-plugin TODO file (pre-polyrepo-split artefact). Prefix convention documented in `CLAUDE.md`.

- [ ] **M1.** Decoration vs inline-photo classification — heuristics to distinguish logos/banners from informational inline images (size, repeated cid across senders, alt-text, tracking domains). Currently all attachments treated uniformly.
- [ ] **M4.** Drafts — optional "follow draft updates" mode (Message-ID/content changes on each save). YAGNI for now.
