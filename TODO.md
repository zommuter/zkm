
# zkm — Phase 2 TODO

See `CLAUDE.md` for architecture overview. See `docs/phase2-plan.md` for sequencing. <!-- lint-ok: file-purpose preamble -->
Completed Phase 1 tasks archived in `docs/phase1-done.md`. <!-- lint-ok: file-purpose preamble -->

> **Topology (decided 2026-06-30, `docs/meeting-notes/2026-06-30-1004-per-plugin-todo-topology-revisited.md`, Option B):** <!-- lint-ok: file-purpose preamble -->
> This file holds ONLY **core** + **genuinely cross-cutting** items. Plugin-scoped work lives in each plugin's own `plugins/zkm-*/TODO.md` (executor specs in its `ROADMAP.md`). Boundary rule (first match wins): (1) edits `src/zkm/**` or a core test → here; (2) shared schema/spec/library imported by ≥2 plugins (γ, `zkm.pdftext`, object-storage, messaging-spec, conformance) → here; (3) else → the owning plugin's TODO.md. Tiebreaker: "would closing it touch ≥2 repos?" → here. All-plugin glance: `proj`/`/projects` (walks plugin TODOs) + relay `--all` rollup. The W/V/C/… prefix table is **retired** — the repo is the namespace. <!-- lint-ok: file-purpose preamble -->

## Cross-project

- [ ] [INPUT — meeting] **[MEETING] `--cross` git-add CAS objects during scans** so the commit is faster afterwards — though that might require worktrees like `/relay` uses to permit concurrency. *Design-judgment (two approaches: eager-add-during-scan vs. worktree-per-scan); a `/meeting` candidate, not executor-ready. Reverse-handoff qualified 2026-06-23.* <!-- id:40d5 -->

- [ ] [INPUT — meeting] **Cross-project (triad) — `/meeting`:** discuss the potentially connecting dots between **zkm <!-- id:21ca -->
  infrastructure** (embeddings / semantic retrieval / knowledge-mgmt) and the `.mw`/toesnail/collAIb triad.
  toesnail is the documented triad hub (`toesnail/docs/dependencies.md`); a session would decide whether/how
  zkm becomes a node in that dependency map. **MIRRORED in `toesnail/TODO.md` under the same `id:4159`** — keep
  both copies in sync MANUALLY (no automated cross-PROJECT sync; relay `--cross-ledger` is intra-repo only,
  inbox routing is one-way). Wherever worked/closed, tick the twin. Likely a manual `/meeting`. <!-- id:4159 -->

## Phase 2.5 — γ schema rollout (decided 2026-05-12-1500-entity-vs-datamining.md)

**Status: γ rollout COMPLETE (E1–E13).** Typed-slot `entities[]`, `(scope,type,value)` dedup, `zkm.canonical`, suspicious dispatch, 8 value-type extractors, P2 index integration, docs contract tables, and zkm-eml signature/salutation γ-scopes all shipped (largely 2026-05-12). E13 (N9g re-eval) closed moot 2026-05-21 — see item below. E14 (TODO bookkeeping) was the only never-run item — reconciled 2026-05-21, see `docs/meeting-notes/2026-05-21-0816-gamma-schema-gap-audit.md` and `docs/field-test-bge-m3.md` step 7. <!-- lint-ok: status summary -->

**Named deferrals (with triggers):** <!-- lint-ok: forward-flag note -->
- P3 typed query language — defer until γ + P2 live ≥1 month AND ≥1 concrete typed-query request. <!-- lint-ok: forward-flag note -->
- PII redaction implementation — defer until sharing scenario lands. Architectural design in E10. <!-- lint-ok: forward-flag note -->
- Entity-DB checksum-fail "ignore / correct?" policy — defer until ≥50 `valid: false` entries accumulate. <!-- lint-ok: forward-flag note -->
- `valid: false` forward-flag: re-evaluate dropping the per-type suspicious heuristic (Option 3) after ≥1 month observation. <!-- lint-ok: forward-flag note -->
- Crypto/stock-ticker domain scope — defer; revisit if real use case lands. <!-- lint-ok: forward-flag note -->
- WebUI typed-query hint UX — Phase 3 design concern. <!-- lint-ok: forward-flag note -->

- [ ] **Entity alias / synonym linking (Phase 4 backlog)** — `SBB CFF FFS` (DE/FR/IT names for Swiss Federal Railways) highlights that the same real-world entity can appear under multiple mention strings (abbreviations, translations, official variants). Likewise, persons appear under nicknames, maiden names, or initials. Deferred to Phase 4 alongside manual-merge tooling; design note needed in `docs/entity-model.md` before implementation. No heuristic auto-merge — human-confirmed alias pairs only. <!-- id:af06 -->

## Phase 2 — SIGUSR1 progress + `zkm status` (decided 2026-05-08-1913-sigusr1-status.md)

Scope: `convert` and `index` (BM25 + embed phases) only. `query`, `clone`, `push`, `pull` explicitly out. Daemon/supervisor model deferred (N<2 background callers). Host-wide multi-store registry, historical run log, `--kill`, `--watch`, live-tail all deferred. <!-- lint-ok: section decision context -->

**Spawned follow-ups (from 2026-05-14 concurrent-run-guard meeting):** <!-- lint-ok: section context preamble -->

- [ ] **Future re-evaluation trigger — local DB with git-tracked autoexport-on-write** — possible architectural pivot from sidecar-files-on-disk. Re-open if any one trigger fires: (a) concurrent-write bugs in sidecars become frequent; (b) WebUI read-write workload makes file-level locking visibly painful; (c) cross-machine sync stops being purely `git pull`-based. See `~/.claude/projects/-home-tobias-src-zkm/memory/project_db_pivot_trigger.md`. <!-- id:1e4a -->
- [ ] **`zkm queue` design meeting (Phase 3 daemon precursor)** — when attach semantics become a real ask (N=2 consumers wanting `--wait-for-busy`), open a meeting on a queue manager: PID-file → in-memory daemon queue; fail-fast → `attach/wait/wait-rerun` modes; `zkm status` polling → WebSocket push (Phase 3 WebUI alignment). Floor any successor must preserve: the v1 contract in `~/.claude/projects/-home-tobias-src-zkm/memory/project_concurrent_run_guard_contract.md`. <!-- id:906c -->

## PDF routing unification — `zkm.pdftext` (decided 2026-06-22-1546-pdf-routing-unify-pdftext.md)

Shared `zkm.pdftext` helper owns the pdf/scan routing *decision* (`probe()` + `is_scanned_only()` + `resolve_threshold()`), consumed by both zkm-pdf and zkm-scan — a ≥2-plugin shared library, so it stays central. The per-plugin migration shipped 2026-06-24; only the cross-plugin density pilot remains. <!-- lint-ok: section decision context -->

- [ ] **Density-ratio pilot (gated, OPEN)** — per-page density/coverage discriminator vs char-count default; gated on "labeled PDF corpus built + ≥1 documented char-count misclassification". Needs `page_chars` on `PdfTextProbe` + a labeled corpus (MSA study). Shared zkm-pdf/zkm-scan concern → stays central (plugin-side seams: zkm-pdf id:8aa4, zkm-scan id:02bd). Not auto-fired. See `docs/meeting-notes/2026-06-22-1546-pdf-routing-unify-pdftext.md`. <!-- id:c63c -->

## Plugin backlog — conversation / AI session sources

**Scoped (decided 2026-06-06-1617-zkm-claude-ai-claude-code-scoping.md):** claude-ai ✓; claude-code ✓ (v0.1.0, 2026-06-11); `zkm.session` extracted (N=2 done, `src/zkm/session.py`). Other providers deferred until session-import pattern proven with two real plugins. <!-- lint-ok: section decision context -->

- [ ] **Other AI provider sessions** (Gemini, etc.) — deferred until a real export shows up. N=2 for a shared `SessionImporter` scaffold now has its second foreign schema (chatgpt). Cross-cutting (would seed a shared `zkm.session`-adjacent scaffold spanning claude-ai/chatgpt/future) → stays central. <!-- id:fd7e -->

## Plugin backlog — social networks

- [ ] [INPUT — meeting] **Meeting: takeout / export archive import** — personal data exports from Google Takeout, Facebook "Download Your Data", Instagram, LinkedIn, Twitter/X, etc. are structured archives (ZIP + JSON/HTML). Distinct from live scraping: deterministic, offline, privacy-safe. Sub-questions: (1) which export formats to support first (LinkedIn most structured); (2) shared `zkm.takeout` extraction helper vs. per-network plugins; (3) "being tagged" in others' posts as a distinct entity-mention type (requires cross-document resolution). Warrants a scoping meeting. Cross-link: LinkedIn browser-save lane in zkm-social SOC3 converges with LinkedIn-takeout ingest — shared parser opportunity; keep separate but note the overlap. Cross-cutting (spans multiple networks + a possible shared helper) → stays central. <!-- id:285f -->

## Chat / messaging — cross-cutting (shared `messaging-spec.md` + entity model)

Per-plugin chat work (whatsapp/telegram/signal/threema ingest, segmentation, footer manifests) lives in each plugin's own TODO.md. Only the genuinely cross-cutting items — shared transcript conventions and Phase-3 entity-model work spanning ≥2 plugins — stay here. <!-- lint-ok: section preamble -->

- [ ] [INPUT — meeting] **Call/voice-event rendering convention in `docs/messaging-spec.md`** — define one shared transcript shape for calls/missed-calls so all chat plugins (whatsapp/telegram/signal/threema) render them identically; the per-platform call-table *ingest* stays per-plugin. Cross-cutting (the spec) half of zkm-whatsapp's call-log ingest. From 2026-06-25 whatsapp folder-naming meeting. <!-- id:5e19 -->
- [ ] **Forward-flag (Phase 3 entity-timeline).** Cross-channel merged per-person conversation timeline: Instagram reel + WhatsApp voice message + phone call as one chronological thread for a contact. Layer-2 entity work (`docs/entity-model.md`); overlaps zkm-social activity-feed (id:a580). Reopen when entity pages + ≥2 channels are ingested. <!-- id:9ee1 -->
- [ ] [INPUT — meeting] **Meeting: real contact names in chat by-name views (phone-number → contact/NER label).** Upgrade chat `by-name/<label>/<leaf>` DM labels to a person's actual name instead of the raw phone number. **Needs a contacts source first** (Google People API export, or extend zkm-vcard with a google lane) producing a phone→display-name map. NER is a complementary source, not a replacement. Why a meeting: (1) which source; (2) where the phone→name map lives + refresh cadence; (3) **name-is-not-a-UID** ([[project_name_not_uid]]) — display-only label, never an identity merge; (4) privacy of the contacts fetch. Spans whatsapp + a contacts/vcard plugin → stays central. <!-- id:6ac6 -->

## Plugin backlog — built environment / home (BIM)

- [ ] [INPUT — meeting] **Meeting: BIM / home-knowledge plugin(s).** Building/flat/house floor plans, room + device inventory, 3D models, smarthome infrastructure topology, and per-device manuals/bills/warranties as linked CAS originals. Open scope (warrants a scoping meeting): one "property" source feeding entity pages (rooms, devices) vs. a cluster of plugins; phase; overlap with the entity model + originals/CAS; how smarthome device state (live vs. snapshot) fits the git-as-temporal-index model. No repo yet → stays central until scoped. Filed 2026-06-25. Device-roster sub-case: + routed:4279 (hardware inventory: RPis/IoT model/location/in-use) → covered by zkm-inventory plugin (id:e65e), scoped 2026-07-11; broader BIM/floor-plan/3D scope stays here. See docs/meeting-notes/2026-07-11-2132-inventory-data-scope.md <!-- id:d35e -->

- [ ] **(cross-cutting note, 2026-07-12) it-infra annex pilot ↔ zkm-inventory (id:e65e) dormant annex-enrichment seam.** it-infra verified git-annex end-to-end on fievel (add → copy → `whereis`=2 → `fsck ok`; nested-repo exclusion confirmed; ~100–120 B/file git-annex-branch overhead) — the **first step toward the ≥2-annex-drives gate** that e65e's dormant enrichment seam waits on. **Drive-identity finding for zkm-inventory:** the HW **serial** is the durable key — volume labels are *reused* across drives ("ZOMMUTER" on ≥2) and the FS-UUID changes on the planned exFAT→non-exFAT reformat; so **if the shipped UUID/label auto-discovery doesn't already key on `ID_SERIAL_SHORT`, consider adding it** (fievel drive-name scheme: `<label>-<serial4>`, UID = full serial; `fievel00-d89d`/`fievel01-236F` for fievel's fixed drives). **Partition-aware extension (2026-07-12, it-infra id:a28d):** the HW serial keys the *physical disk*; the mounted/swept unit is a *partition/filesystem*. Two-level model — disk record `<model>-<serial4>` (e.g. `EVO2TB-834R`) ⊃ per-partition records keyed by **FS-UUID**, displayed `<fs-label>-<serial4>` (`Cee-834R` + `Manjaro-834R`). The shared serial4 across a disk's partitions is intentional (same-spindle failure domain); fs-label disambiguates, FS-UUID is the unique key. For zkm-inventory this confirms finddump's `mount:` block (UUID/label match) is already the right per-partition granularity — but consider recording each partition's parent-disk serial so same-spindle siblings are queryable (relates the still-open `ID_SERIAL_SHORT` identity note above. Full verdict/details in **it-infra `TODO.md` id:a28d**; the plugin-scoped identity change belongs in the zkm-inventory repo (github.com/zommuter/zkm-inventory, not on fievel). <!-- id:3423 -->

## Plugin backlog — browser state (open tabs / bookmarks / history)

- [ ] [INPUT — meeting] **zkm-tabs (idea — salvaged from the retired `gtnsd` repo's "attach a list of open tabs to each commit" <!-- id:8b5d -->
  / TreeStyleTab thread; history preserved in `toesnail` branch `gtnsd-archive`).** A plugin to capture
  browsing context into the store: currently-open browser tabs (e.g. TreeStyleTab tree export), bookmarks, and
  possibly history — as timestamped knowledge snapshots / per-session context. Open Qs: capture mechanism
  (browser extension / bookmarklet / native-messaging vs. reading the browser's `places.sqlite` +
  session-restore files); cadence (on-demand vs. periodic); **dedup/diff** — tabs & bookmarks churn, so store
  deltas not full dumps (overlaps the inflownistration/staleness idea, `.mw` `id:aae4`); privacy posture (URLs
  can be sensitive — mirror zkm-claude-ai's deliberate-render stance). Relates to the zkm-social SOC4
  bookmarklet-capture front-end (id:dfa4). **Active-triage extension (added 2026-06-18):** beyond passive capture, a
  browser addon that lets you *triage* open tabs with per-tab actions — **keep** (snapshot into the
  store as durable knowledge), **archive** (store + close the tab), **close** (drop, no store),
  **forget** (close + suppress from future capture/dedup), **reminder** (store with a date-trigger /
  resurface later). This makes zkm-tabs a tab-hygiene workflow, not just a snapshotter — the triage
  *decision* becomes the captured signal (why a tab mattered), and "archive/forget" naturally feed
  the dedup/diff + staleness model already noted. Open Qs it adds: where the action verbs live
  (addon UI vs. a post-capture `zkm` triage command over a captured tab-list); whether "reminder"
  reuses a core date-trigger mechanism; how "forget" interacts with the delete/scrub semantics
  (cf. zkm-notmuch id:f103 tag-removal). No repo yet → stays central until scoped. <!-- id:301c -->

## Store hygiene — processed-tracking + git-as-byte-source (design)

- [ ] [INPUT — meeting] **`/meeting` — CAS processed-by-version tracking + git-sourced bytes.** Two coupled problems: **(1) input clutter** — `inbox/<subdir>/YYYY/MM/` symlinks accumulate indefinitely as sources are ingested; over time the inbox stops being a "drop zone / unprocessed view" and becomes an ever-growing pile of already-processed items. **(2) reprocessing is working-tree-walk shaped** — `run_reprocess` (version-aware skip, cf. `test_reprocess_outdated_skips_current_version`) and amenders iterate filesystem paths, not the set of CAS objects-needing-work. **Idea:** track which CAS objects were processed by which **plugin version** directly (the per-object sidecar `producers[]` already records `plugin` + `message` + `sha256` but **NOT version** — `docs/object-storage.md` schema v1), so a converter/amender can enumerate CAS objects whose `(plugin, version)` provenance is missing/outdated and process those directly — decoupling "what needs work" from the cluttered inbox view; the inbox symlink can then be retired/pruned once an object is fully processed (relates to `zkm gc`/`hygiene.py` orphan sweep). **Further idea (harder):** stop keeping processed bytes in the working tree at all — read originals via `git show <blob>` on demand instead of working-tree files, so tools operate on git history as the byte store. **Open question (annex):** git-annex/lfs externalize bytes — `git show` on an annex pointer yields the pointer text, not the content, and annexed objects may be absent locally (availability/`annex get`), so the git-show path is clean only for `backend=none`; annex/lfs need a backend-aware resolve (`zkm.cas` already abstracts this for symlinks — extend, don't bypass). Decide: sidecar schema bump (add `version` to producers) vs. a separate processed-ledger; eager-prune vs. lazy-prune of inbox symlinks; git-show byte-source as opt-in per backend. Touches `zkm.cas` / `zkm.inbox` / `zkm.sidecar` / `hygiene.py` / `convert.run_reprocess`. Filed 2026-06-23. <!-- id:b7e2 -->
- [ ] [INPUT — access] **(store, driver-B residual of [[id:8f1c]]) Working-tree-walk speedup for `$ZKM_STORE` git ops — config quick-wins not yet applied.** The annex-anchoring surgery (DECIDED [[id:8f1c]] / [[id:5636]]) fixed **driver A** (pack/history bloat from CAS blobs committed straight into git). **Driver B is independent and unaddressed:** `git status`/`add` stat the ~500k-file working tree on every auto-commit. Verified 2026-06-26 that `core.fsmonitor` and `core.untrackedCache` are **both unset** on `~/knowledge`. Apply the cheap, reversible config wins (no history rewrite): `core.untrackedCache=true` + `core.fsmonitor=true` (largest win for a half-million-file `status`), optionally `feature.manyFiles=true`/`index.version=4`, split-index. **Measure `git status` before/after** (observe-before-preventing) to confirm the win. Ties into [[id:b7e2]] (git-as-byte-source). Re-id'd from id:8f1c 2026-06-26 to disambiguate the open/closed shared-token pair (REVIEW_ME box). — (M3 relane 2026-07-11: ACCESS) <!-- id:6e13 -->
- [ ] [INPUT — access] **(store, after recreate — depends [[id:5636]])** Establish a real 2nd annex copy: `git annex copy --to <fievel-annex-remote | external-HDD>` so the store isn't single-copy ("one disk = total loss" is worse than bloat; also the prerequisite for reclaiming local disk via `git annex drop`). See 2026-06-23-2251 note. — (M3 relane 2026-07-11: ACCESS) <!-- id:0b37 -->
- [ ] **(core, defer/low)** `zkm verify`/`doctor`: read-only warning when a committed blob >N MB is not an annex/lfs pointer. Reporter, not guard. Gated: build on a 2nd un-annexed-blob incident (observe-before-preventing). **2nd capability (decided 2026-06-24, storage-tiers note D4):** `--rederive` — re-derive a *sample* of amenders/embeddings and **diff** against stored state (drift/corruption reporter, sample-based not full >2h corpus). Both capabilities gated/deferred until a 2nd concrete need. See 2026-06-23-2251 + 2026-06-24-1350-storage-tiers-restore-sync notes. <!-- id:5f61 -->
- [ ] [INPUT — meeting] **(zkm-eml + core) Handle spam / source-deleted mail — FULL removal, not just untag.** zkm-eml is append-only: a converted mail's `.md` (+ thread `.md`), its CAS attachment objects, annex content, and index entries all persist even when the mail is **spam** or later **deleted from the mailbox**. Need a path to *fully drop* a mail: remove the `.md` + thread `.md`, decrement/remove its CAS attachment objects (orphan sweep via `zkm rm`/`zkm gc`), purge from BM25 + dense index, and **`git annex drop`** the now-orphaned annex objects. **Two coupled questions:** (1) **spam detection** — what signals spam (notmuch `spam`/`deleted` tag, a Junk/Trash folder, mbsync flag)? zkm-eml owns detect-and-signal. (2) **general source-deletion semantics** — when a mail disappears from the mailbox, should zkm mirror the deletion? This is the broader open "treat deleted mails / source-deletions" question. **Boundaries:** core owns the removal mechanics (`rm` `.md` + `gc` CAS + index purge + annex drop); zkm-eml owns detection. Cross-cutting (core mechanics + zkm-eml detection) → stays central. Relates to [[id:25ec]] (amendments declarative retraction), `zkm rm`/`zkm gc` (CAS orphan sweep). Filed 2026-06-24. <!-- id:9f3c -->
- [ ] [INPUT — meeting] **`/meeting` — core: multiple source locations per plugin (retained sources for version-aware re-processing).** Today most plugins take a single source pointer (`source_db`, `source_dir`, …) and the watermark is keyed per absolute source path, so re-running a later plugin version only re-derives from the *current* source — older/archived sources (e.g. a previous phone's WhatsApp backup, an old mail export, a superseded calendar dump) aren't re-processed even though a newer plugin version could extract more from them. Generalize to a **list of source locations** per plugin (e.g. `sources: [<path-or-config>, …]`, back-compat with the singular key) that `zkm convert <plugin>` and especially `--reprocess`/`--reprocess-all` iterate — so a plugin-version bump can sweep ALL retained sources, oldest-first, with existing dedup (key_id / sha256 / url) collapsing overlaps. Cross-cutting: **core** owns the config-schema convention + reprocess iteration; each plugin keeps its own dedup + per-source watermark. The whatsapp multi-source merge (id:9e44, manual `source_db` swap per backup + `docs/merge-old-backup.md`) is the concrete prototype to generalize. Open Qs: where retained-source *bytes* live (in-store under `originals/` vs. external path registry — ties into [[id:b7e2]] git-as-byte-source + annex availability); per-source vs. per-plugin watermark map; whether "retain the source" is a fetch-role concern (decryption boundary) or core. Decide the config shape + reprocess contract before any plugin adopts it. Filed 2026-06-23. <!-- id:7c3f -->
- [ ] [INPUT — meeting] **Core hygiene: `.lock` file proliferation in the store (33k+).** `zkm.amendments`/sidecar/CAS read-modify-write creates a per-object advisory-lock sibling `<file>.lock` (`*.amendments.json.lock`, `mail/_objects/**/<sha>.json.lock`, …) that is **never reaped after release** → 33,043 stale `.lock` files observed 2026-06-25 (gitignored via store `*.lock`, so untracked — clutter, not a commit risk). Fix options: flock on the real file fd (no sibling file), a single lock-dir, or unlink-on-release; and a one-shot sweep of existing stale locks. Cross-cutting core (`zkm.atomic`/`zkm.sidecar`/`zkm.amendments`/`zkm.cas`) — affects mail, transcripts, all CAS consumers. Filed 2026-06-25. <!-- id:79a6 -->

## Workflow / process backlog

- [ ] (Forward-flag, deferred — D4) Design a TODO-mutating script/tool that enforces the `@{u}` done-gate at `[x]`-write time. Gate: next todo-update skill revision OR second enforcement need. <!-- id:f1cf -->

## Frontmatter schema vocabulary (decided 2026-06-13-1413-frontmatter-schema-vocabulary.md)

Cross-cutting schema rules (core-owned scalar registry + per-plugin namespacing) — span core docs + ≥2 plugins, so they stay central. <!-- lint-ok: section preamble -->

- [ ] **D2/D3 plugin field doctrine (status enum, namespacing, core-owned registrations)** — routed to zkm-calendar (routed:c74e, 2026-07-02); central line is a pointer, execution tracked in the plugin ledger. <!-- id:cfd1 -->
- [ ] **D4 url_sha256 write + migration for source:social** — routed to zkm-social (routed:8607, 2026-07-02); central line is a pointer, execution tracked in the plugin ledger. <!-- id:f3c6 -->

## NER false-positive doctrine (decided 2026-06-13-1413-ner-false-positive-doctrine.md)

- [ ] **NER false-positive doctrine ticks for REVIEW_ME 204c/b081 (zkm-social + zkm-ner)** — routed to zkm-social (routed:23f3, 2026-07-02); central line is a pointer, execution tracked in the plugin ledger. <!-- id:346c -->

## Amendment contract backlog

- [ ] **Meeting: amendment replace-mode** — set-union merge (current) is correct for additive enrichment but cannot remove stale entities when extractor quality improves. `zkm scrub <plugin>` is the current workaround (N9b + future N9c). Trigger for meeting: a third amender wants single-producer-per-field semantics, OR N9c surfaces a need not solvable by scrub. Cross-cutting (core amendments contract) → stays central. See `docs/meeting-notes/2026-05-10-2142-n9b-scrub-cli.md` for design context. <!-- id:4787 -->

## Plugin dependency loading (backlog)

- [ ] **Plugin-specific deps when loaded via importlib** — option (d) shipped as SB2 (2026-06-03): `_inject_plugin_venv` now called inside `_load_plugin_module` for dev-symlink plugins. Remaining open question: options (a)/(b)/(c) (subprocess isolation / uv-run wrapper / optional extras) for the entry-point install path where `.venv` is absent. Low urgency — entry-point installs already resolve deps via `uv tool install zkm --with zkm-<name>`. Warrants a scoping meeting only if this remaining gap causes problems in practice. <!-- id:6c07 -->
- [ ] **Re-open derivable-data meeting trigger** — re-open `docs/meeting-notes/2026-05-13-1950-derivable-expensive-data-in-git.md` decision if: first real `zkm clone` to second host makes re-derive wait painful; OR re-derive budget exceeds ~2 h (today: ~50 min). <!-- id:e344 -->

## Publishing / distribution (backlog — from 2026-05-12-0844-publish-plugins.md)

- [ ] [ROUTINE] **Stage 2: OIDC Trusted Publisher + `.github/workflows/release.yml` in all 7 repos** — tokenless CI publish; closes auto-publish loop with the post-commit auto-tag TODO. Per-project tokens available (created after first publish). Cross-cutting (all repos) → stays central. — author-half of M3 author-then-run split (write `.github/workflows/release.yml` across the repos) — (M3 relane 2026-07-11: ROUTINE) <!-- id:3aa3 -->
- [ ] [INPUT — access] Set up the PyPI OIDC Trusted-Publisher credential for the 7 repos (DEP: 3aa3) — run-half of the M3 author-then-run split of id:3aa3 <!-- id:df4e -->

## Test corpus / fixture infrastructure (decided 2026-05-29-1112-synthetic-test-corpus.md)

**Status: COMPLETE (2026-06-01).** Committed `.md` corpus (`tests/fixtures/corpus/`, 6 docs + CORPUS_MANIFEST.json), three pathological anchors (`tests/fixtures/pathological/`), `scripts/seed_dev_store.py`, `tests/conftest.py` `store`+`make_note` fixtures, corpus README with regen procedure, zkm-eml generator (`generate_corpus.py`) + roundtrip test (`test_corpus_roundtrip.py`), `zkm test <plugin>` conformance validator. See `docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md`. <!-- lint-ok: status summary -->

## inbox intake 2026-06-26 (routed from todo-inbox.md)

- [ ] **Grand Truth Project zk hub note + mindmap** — Grand Truth Project zk hub note + mermaid mindmap of the certainty-gating mesh (zelegator/chidiai/mathematical-writing/toesnail/zkm) + one-sentence thesis; spoke repos link up via a CLAUDE.md 'Part of: Grand Truth Project' line (inbox routed:eb36 from project_manager, docs/meeting-notes/2026-06-16-1018-chidiai-scoping.md) *(scheduled as a ~1h owner slot on the human-sprint list; raw-material packet = mathematical-writing docs/meeting-notes/2026-07-02-1000 (triad §1/§5-inputs) + 2026-07-02-1100 §5 (tensions + strawmen))* <!-- id:3d98 -->
- [ ] **16-plugin dev-deps → [dependency-groups] sweep** [INBOUND routed:97a9 from zkm-eml relay review 2026-07-02] — routed to zkm-calendar (routed:1dbe, 2026-07-02); central line is a pointer, execution tracked in the plugin ledger. <!-- id:f9a7 -->
- [ ] [INBOUND routed:b46d from dotclaude-skills] Subject-clouds semantic/embedding overlap layer — build ONLY for overlaps dc60 slice-0's ground-truth run provably misses; toesnail/docs/se-corpus.md = hand-labeled eval fixture; GATED on slice-0 miss-set non-empty <!-- id:3174 -->
- [ ] [INBOUND routed:22f6 from zkm-chatgpt id:05eb relay-human 2026-07-11] Promote frontmatter `title` to core CORE_OWNED_SCALARS (id:4431); audit all zkm plugins for bare `title`/other generic scalars to fold in once <!-- id:aa57 -->
- [x] **(core) Shell autocompletion for `zkm` (bash + zsh, ideally fish).** Static command/subcommand/option completion via Click's native support (`_ZKM_COMPLETE=bash_source zkm` etc.) — but crucially DYNAMIC completion for plugin-name arguments: `zkm convert <TAB>` / `zkm scrub <TAB>` should complete from the live discovered plugin set (entry-points ∪ `plugins/*/plugin.yaml`, incl. multi-doc secondaries like `inventory-finddump`), and value args (e.g. `--outdated`, remote names) where cheap. Keep it fast (completion must not trigger heavy plugin imports — reuse the lightweight manifest scan, not `_load_plugin_module`). Ship a `zkm completion [bash|zsh|fish]` command that prints the script + install docs (docs/install.md). Central (edits src/zkm/cli.py). <!-- id:e9e2 -->
- [ ] **(core, manual/non-hermetic follow-up of [[id:998b]])** Live durability smoke: `zkm push <fievel-annex-remote>` against real `~/knowledge`, then `git annex whereis`/`fsck` on the remote confirms content + location tracking landed. Not a unit test. See 2026-07-12-1030-d2-unified-zkm-push note. <!-- id:5f86 -->
- [ ] [INBOUND routed:50d7 from it-infra] git-annex coupling ack: it-infra 3-2-1 meeting scoped git-annex on redundancy merits only (not whole-disk); 'locate my X on a drive' stays zkm-inventory (manifest / Layer-2 find-dump / annex-whereis); whole-disk annex reconsidered post-drive-map on cross-drive-dup evidence; zkm-inventory (id:e65e) annex seam stays dormant until ≥2 annexed drives <!-- id:5466 -->
