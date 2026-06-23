# Relay log <!-- merge=union; append-only — never edit or reorder past entries -->

## 2026-06-12 18:17 — reviewer (Fable 5)

handoff C1-C5: docs+ARCHITECTURE (8 decisions), blockers-first roadmap (3 ROUTINE/1 HARD), 10 red specs + 6 anti-gaming guards, @manual CLI BDD, C5 systemd self-scope shipped (id:62f3) — suite 545 green + 10 intended-red; Phase-2-done definition awaiting user confirm in REVIEW_ME

[2026-06-12 executor sonnet-4-6] Worked id:1098 — added GAMEMODE_LOCK_DEFAULT constant to runstate.py, gamemode-lock check inside RunSession.__enter__ (before PID file write, inside the ZKM_BYPASS_RUN_GUARD block), and informational "gamemode lock" row to cmd_doctor. All 8 tests green (6 RED→green + 2 GUARD still green); full suite 551 passing, 4 intended-red for other items.
Friction: none — straightforward; conftest autouse fixture was already in place.

[2026-06-12 executor sonnet-4-6] Worked id:dd89 and id:e1fc in one session.
id:dd89: added `not created` guard + skip-notice before the amender loop in cmd_convert (cli.py:666). 4/4 tests green. id:e1fc: added amender `created`-param warn in check_interface (conformance.py), and a one-paragraph note to docs/plugin-spec.md §Frontmatter amendments. 4/4 tests green. Full suite 555 passing, 0 failing.
Friction: none — both items were well-scoped; test fixtures were already in place.

## 2026-06-12 18:31 — reviewer (Fable 5), review since fable-ckpt-20260612-1817

Verified id:1098+id:dd89+id:e1fc genuinely green: zero test files touched since
the checkpoint, all 10 RED specs fail against the checkpoint tree and pass
against HEAD with byte-identical tests; 6 anti-gaming GUARDs intact; full suite
555 passing. No gaming flags, no reopens, no friction reported. Updated
ARCHITECTURE.md §D7 (gamemode lock guard) to match shipped reality. Re-derived
ROADMAP: compressed the three closed ROUTINE items; seeded id:83c7 (amendment
queue row in doctor + skip-notice count — observation half of the dd89
trade-off) and id:1a6f (doctor --entities valid:false census — gives the two
TODO deferral triggers a readable counter) with 6 new RED specs + 3 GUARDs in
tests/test_doctor_amendment_queue.py and tests/test_doctor_entities.py.

## 2026-06-12 18:46 — reviewer (claude-fable-5)

review: id:1098+dd89+e1fc verified genuine (0 gaming flags, 558 green); seeded id:83c7 (amendment-queue visibility in doctor) + id:1a6f (doctor --entities census), 6 RED specs

[2026-06-12 executor sonnet-4-6] Worked id:83c7 and id:1a6f in one session.
id:83c7: added `amendment queue` informational row to cmd_doctor (rglob *.json count, per-emitter breakdown via parent.name); updated zero-created skip notice in cmd_convert to append pending count when queue non-empty. 5/5 tests green (3 RED→green + 2 GUARDs). id:1a6f: added `--entities` flag to cmd_doctor; deferred frontmatter sweep (O(store), opt-in) counts valid:false entity slots per type; prints informational `suspicious entities` row always with the flag (0 when none found). 4/4 tests green (3 RED→green + 1 GUARD). Full suite 564 passing, 0 failing.
Friction: none — both items well-scoped; queue dir layout and γ entity schema were clear from amendments.py and ROADMAP context.

## 2026-06-13 10:57 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

zkm review: id:83c7+id:1a6f doctor features verified genuine (0 gaming, 564 green); refreshed stale relay-contract pointer v1->v2; ROADMAP fully consumed (6/6 closed)

## 2026-06-13 15:13 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review zkm: audited dcc1426 (docs-only) clean, 564 tests green, 8 new ids verified, Phase 2 done-def CONFIRMED, pruned 2 resolved REVIEW_ME boxes

## 2026-06-13 23:35 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260613-2304: 2 doc-only commits audited clean (R1 box confirms + plugin contracts + id:9878 BDD-convert item), 564 tests green, no gaming, contract pointer v2 current

## 2026-06-13 — executor (claude-sonnet-4-6)

Worked id:9878 — converted all 5 T1 @manual BDD scenarios from features/cli-journeys.feature to executable pytest tests in tests/test_bdd_cli_journeys.py. Tests cover: (1) hybrid search BM25 fallback when embed endpoint down, (2) concurrent convert exits 75 naming PID, (3) gamemode lock blocks index (exit 75, names path), (4) doctor shows gamemode-lock row, (5) no-op convert skips amenders, (6) doctor on healthy store exits 0 with md/bm25 counts. Removed @manual from the 4 converted Feature blocks; the @roadmap-62f3 scenario (systemctl freeze — T4/environment-gated) got its own @manual tag. ROADMAP checkbox ticked; full suite 570 passing (6 new tests).
Friction: none — PID file naming convention (must be <pid>.json for _scan_running_dir) required one debug iteration; doctor default endpoint resolution always returns localhost:8080 so the healthy-store test mocks httpx.post to return OK responses.

## 2026-06-14 00:00 — executor (sonnet, relay-loop)

feat(bdd): convert 5 T1 @manual BDD scenarios to executable tests (id:9878) — 6 new tests, 570 total passing

## 2026-06-15 11:04 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260615-1104: audited 46c2a04 (REVIEW_ME-only, user batch-triage) clean — no test/code changes, no deletions; user confirmed interpretations for id:1098 (gamemode-lock guard) + id:62f3 (index self-scope), both tests green (test_gamemode_guard.py + test_selfscope.py, 18 pass), full suite 570 green + BDD 6 green; closed umbrella TODO id:f631 (both sub-items now user-verified); refreshed stale relay-contract pointer v2->v3; 0 open ROADMAP items, 0 open REVIEW_ME boxes, 0 gaming flags

## 2026-06-15 11:12 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260615-1104: audited REVIEW_ME-only commit clean, closed id:f631 (user-confirmed 1098/62f3), refreshed relay-contract pointer v2->v3; 570 green, 0 gaming

## 2026-06-16 09:28 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260616-092804: audited b28e7ef (TODO.md-only) clean — pure cross-project /meeting item add (id:4159, zkm×triad connecting-dots, mirrored from toesnail under same id), no test/code/deletion changes; gaming-scan clean, 570 tests green. §5b reverse-handoff: id:4159 is design-judgment work (ambiguous "whether/how zkm becomes a node", explicitly flagged manual /meeting) → left as TODO /meeting candidate, NOT promoted to ROADMAP; already qualified by the meeting (id + cross-project sync note). §4 spec-drift: refreshed stale relay-contract pointer v3->v4 in CLAUDE.md (canonical marker bumped to v4). ROADMAP fully consumed (all items [x]), routine_open=0, 0 open REVIEW_ME boxes, 0 gaming flags, 0 reopens.

## 2026-06-16 09:38 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260616-092804: audited b28e7ef (TODO-only cross-project /meeting item id:4159) clean, 570 green, 0 gaming; refreshed contract pointer v3->v4; routine_open=0

## 2026-06-16 09:55 — reviewer (claude-opus-4-8, fable-standin, relay-loop), review since relay-ckpt-20260616-0938

review 20260616-092804-18345: audited 03cceb2 (TODO.md-only) clean — adds the zkm-tabs plugin idea (id:301c, browser-state capture: open tabs/bookmarks/history, salvaged from the retired gtnsd repo's "attach open tabs per commit" thread). No test/code/deletion changes; gaming-scan clean, full suite 570 green. §5b reverse-handoff: id:301c is design-judgment work — explicitly "idea … Warrants scoping before build", with open Qs on capture mechanism (extension/bookmarklet/native-messaging vs reading places.sqlite), cadence, dedup/diff strategy, and privacy posture → left as a TODO /meeting candidate, NOT promoted to ROADMAP; reused its existing id:301c. §4 spec-drift: relay-contract pointer already v4 (refreshed prior turn), matches canonical — no change. ROADMAP fully consumed (all items [x]), routine_open=0, 0 open REVIEW_ME boxes, 0 gaming flags, 0 reopens.

## 2026-06-16 10:07 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260616-092804-18345: audited 03cceb2 (TODO-only zkm-tabs idea id:301c) clean, 570 green, 0 gaming; id:301c kept as /meeting candidate (design-judgment, not ROADMAP); routine_open=0

## 2026-06-18 16:16 — reviewer (claude-opus-4-8, fable-standin, relay-loop), review since relay-ckpt-20260616-1007

review 20260618-161606-30516: audited 7d5ae25 (TODO.md-only) clean — folds an "active-triage" dimension into the existing zkm-tabs idea (id:301c): a browser addon with per-tab actions (keep/archive/close/forget/reminder) where the triage decision is itself the captured signal, plus open Qs (action-verb locus addon-UI vs post-capture `zkm` command, reminder reusing a core date-trigger, forget vs delete/scrub semantics cf. zkm-notmuch id:f103). No test/code/deletion changes; gaming-scan clean. §5b reverse-handoff: still design-judgment work — explicitly "Warrants scoping before build" with multiple unresolved approach choices → kept as a TODO /meeting candidate, NOT promoted to ROADMAP; reused existing id:301c (no duplicate mint). §4 spec-drift: relay-contract pointer already v4, matches canonical — no change; README untouched (design idea, nothing shipped). ROADMAP fully consumed (all 7 items [x], 0 unticked), routine_open=0, 0 open REVIEW_ME boxes, 0 gaming flags, 0 reopens, 0 verified-green (no test/code churn this window).

## 2026-06-18 16:27 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 20260618-161606: audited 7d5ae25 (TODO-only id:301c active-triage) clean, 0 gaming, routine_open=0

## 2026-06-19 16:13 — reviewer (claude-opus-4-8), review since relay-ckpt-20260618-1627

Window = 2 commits, both ledger/design-only: a07a2bf archived 3 old `[x]` TODO
entries (no code), a7f4085 a /meeting session that added TODO id:25ec + the f103
tag-removal design note. No executor implementation in this window — nothing to
trust-but-verify against tests. gaming-scan.sh clean (no DELETED_TEST/ADDED_SKIP/
REMOVED_ASSERT); full suite 570 green + 5 skipped. All ROADMAP items remain
review-verified `[x]`; contract pointer already v4 (current); no spec drift.
Reverse-handoff (§5b): qualified+sized the one unqualified `/meeting` addition,
id:25ec (declarative-set retract primitive in src/zkm/amendments.py). Promoted to
ROADMAP as **[HARD — strong model]** REUSING its TODO token — HARD because it makes
the append-only attribution sidecar authoritative per-producer state with a
destructive wrong-removal failure mode, coupling an fcntl lock (module has none
today), a `_SCHEMA` 1→2 bump, legacy-sidecar graceful-read bootstrap, and a
`uv publish`. Wrote red spec tests/test_amendments_retract.py (`# roadmap:25ec`,
5 cases: sole-producer drop, multi-producer keep D2, no-op-on-empty D4a,
idempotence, additive-emit-unaffected) — currently skip-on-missing-`emit_set`,
EXPECTED-RED until the item ships. Stage 2 (zkm-notmuch f103) already routed to
that repo's inbox; not bundled. routine_open = 0 (the only open ROADMAP item is
HARD).

## 2026-06-19 16:24 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review since relay-ckpt-20260618-1627: ledger/design-only window (2 commits), gaming-scan clean, suite 570 green; promoted id:25ec declarative-set retract to ROADMAP [HARD] with red spec

## 2026-06-19 16:13 — reviewer (claude-opus-4-8), review since relay-ckpt-20260619-1624

Window = 1 commit, TODO.md-only: 50b2ad6 added a "Plugin backlog — audio/video
transcription (STT)" section with one zkm-stt idea item. No test/code/deletion
churn — gaming-scan.sh clean (no DELETED_TEST/ADDED_SKIP/REMOVED_ASSERT); nothing
to trust-but-verify against tests this window. §5b reverse-handoff: the addition is
explicitly design-judgment work — an "idea", "Warrants scoping before build", with
multiple unresolved approach choices (backend whisper/faster-whisper/remote endpoint;
WhatsApp amender-style vs embedded; YouTube `zkm fetch youtube` subcommand vs
standalone `zkm convert stt` over `inbox/stt/`; caching/timestamp-granularity/
diarisation Qs) → kept as a TODO /meeting candidate, NOT promoted to ROADMAP.
**Defect fixed**: the item carried an INVENTED token `<!-- id:stt1 -->` ("stt1" is
not a valid 4-hex id and was never minted via append.sh) — re-minted a proper token
via append.sh new-ids and rewrote it to `<!-- id:dcf8 -->` (verified unique across
TODO/archive/ROADMAP/RELAY_LOG/docs). §4 spec-drift: relay-contract pointer already
v4 (matches canonical), README untouched (nothing shipped). ROADMAP unchanged — the
sole open item is id:25ec [HARD — strong model]; routine_open = 0, 0 open REVIEW_ME
boxes, 0 gaming flags, 0 reopens, 0 verified-green (no test/code churn).

## 2026-06-19 17:45 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review since relay-ckpt-20260619-1624: TODO-only window (1 commit), gaming-scan clean, suite 570 green; qualified zkm-stt idea as /meeting candidate (not ROADMAP), fixed invented id:stt1→id:dcf8, routine_open=0
## 2026-06-18 15:54 — reviewer (claude-opus-4-8[1m], relay-loop)

review 20260618-155410-10356: audited 7d5ae25 (TODO.md-only) clean — extends the zkm-tabs idea (id:301c) with an **active-triage** dimension (browser addon: per-tab keep/archive/close/forget/reminder actions, triage decision as the captured signal). No test/code/deletion changes; gaming-scan clean, full suite 570 green (32s). §5b reverse-handoff: this is the same design-judgment item the 2026-06-16 review already kept as a /meeting candidate — the new text still ends "Warrants scoping before build" and adds open Qs (action-verb location addon-UI vs post-capture `zkm` command; whether "reminder" reuses a core date-trigger; how "forget" interacts with delete/scrub semantics cf. zkm-notmuch id:f103). Two plausible approaches + ambiguous scope → left as TODO /meeting candidate, NOT promoted to ROADMAP; reused existing id:301c (no duplicate mint). §4 spec-drift: relay-contract pointer already v4, matches canonical — no change. ROADMAP fully consumed (all items [x]), routine_open=0, 0 open REVIEW_ME boxes, 0 gaming flags, 0 reopens.

## 2026-06-19 19:13 — reconcile (human)

reconcile integrate: relay(review): audit 7d5ae25 (zkm-tabs active-triage idea id:301c) clean, 570 green

## 2026-06-19 19:31 — strong-execute (claude-opus-4-8, fable-standin, relay-loop)

hard (claude-opus-4-8): id:25ec declarative-set retract primitive in amendments.py (emit_set, ref-count-to-zero removal, schema 1->2 graceful read, fcntl lock, dry-run); 578 tests green

## 2026-06-21 23:04 — reviewer (claude-opus-4-8)

Opus review (/relay review --all): 3-commit doc window — meeting(zkm-stt v1 scope + 25ec reconcile), relay-human(25ec(b) tag ref-count trade-off), todo archive. gaming-scan clean; docs-only. NOTE: uncommitted WIP left in main (TODO.md + 2026-05-13 pypi-canary meeting-note) is an in-progress correction of a wrong 'PyPI published' claim — LEFT UNTOUCHED; it is not part of the committed review window. Cross-ledger consistent.

## 2026-06-21 23:15 — reviewer (claude-opus-4-8[1m], relay-loop)

review 20260621-231529-15021: audited 4e8452f (single docs-only commit) clean — the PyPI "published" correction the 2026-06-21 23:04 note flagged as uncommitted WIP is now committed (TODO.md line + 2026-05-13 pypi-canary meeting-note both annotated: prod PyPI returns Not Found, `uv publish` never landed, publishing deferred indefinitely). No code/test changes; gaming-scan clean (0 DELETED_TEST/ADDED_SKIP/REMOVED_ASSERT), full suite 578 green (31s). §5b reverse-handoff: no new `- [ ]` items added in window — nothing to qualify. §4 spec-drift: relay-contract pointer v4, matches canonical — no change; README/ARCHITECTURE unaffected by a docs-correction commit. ROADMAP fully consumed (0 open boxes), routine_open=0, 0 open REVIEW_ME boxes, 0 gaming flags, 0 reopens. Cross-ledger consistent (the corrected TODO line is a tracking [~] item, no ROADMAP counterpart).

## 2026-06-21 23:27 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

relay(review): audit 4e8452f (PyPI-correction docs commit) clean, gaming-scan clean, 578 green, ROADMAP fully consumed

## 2026-06-22 01:03 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: verified docs-only TODO W-section reconciliation accurate (6 shipped twins, 1 gated); 0 gaming flags, 0 reopened, routine_open=0

## 2026-06-22 15:44 — reviewer (claude-opus-4-8, relay-handoff)

relay handoff: messenger plugins. Core ROADMAP gains id:f399 (zkm.state lift) + id:ab8b (reemit contract helper) with 5 red tests. Three new plugin repos (zkm-telegram/signal/threema) created + pushed remote-first; telegram has 7 red tests (executor-ready), signal/threema are pilot-first (decryption pilot HARD/human first, parser blocked). Design: 2026-06-22-1503-messenger-plugins-telegram-signal-threema.md.

## 2026-06-22 16:21 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review since relay-ckpt-20260622-1544: docs-only window, no gaming; id:66e0 mark-done verified (3 plugin skeletons + fievel remotes); §5b reverse-handoff mirrored id:9e13 core zkm.pdftext to ROADMAP [ROUTINE] + 6 RED specs; suite 578 green, routine_open=3 (f399/ab8b/9e13)

## 2026-06-22 — executor (claude-sonnet-4-6)

Worked id:f399, id:ab8b, id:9e13 — all three open [ROUTINE] items.
id:f399: added src/zkm/state.py (load_state/save_state with plugin parameter, atomic writes, multi-account independence). 3 tests green.
id:ab8b: added src/zkm/testing.py (assert_reemit_identical helper); documented in docs/messaging-spec.md §Deterministic emission contract. 2 tests green.
id:9e13: added src/zkm/pdftext.py (PdfTextProbe dataclass, probe, is_scanned_only, resolve_threshold, DEFAULT_TEXT_THRESHOLD=100); ARCHITECTURE.md §Routing contract added; version 0.15.0→0.16.0 (autotag fired: v0.16.0 local tag created). 6 tests green.
Full suite: 589 green (0 failures). Friction: none.

## 2026-06-22 16:55 — executor (sonnet, relay-loop)

executor: all 3 ROUTINE items done (f399 zkm.state, ab8b zkm.testing, 9e13 zkm.pdftext); 589 green; v0.16.0 tagged

## 2026-06-22 21:31 — strong-execute (claude-opus-4-8, uv.lock cascade)

uv.lock cascade fix (id:bae5): relocked parent self-bump 0.15.0->0.16.0; added scripts/relock-plugins.sh (relock+--check+--push+--install-hook) + scripts/hooks/pre-push guard that refuses a version-bump push while parent/plugin locks are stale. Guard tested: blocks stale-bump, allows non-bump + in-sync. Authored+verified this Opus turn.

## 2026-06-23 08:32 — reviewer (claude-opus-4-8), review since relay-ckpt-20260622-2131

review: 7 commits in window — 4 doc-only (TODO.md), 3 real fixes in src/zkm/convert.py.
Verified all genuinely green (full suite 593 passed on Python 3.14, gaming-scan clean:
0 DELETED_TEST/ADDED_SKIP/REMOVED_ASSERT; test_plugin.py change purely additive, +119
lines, 0 assertions removed):
- id:c4d1 (multi-document plugin.yaml discovery) — load_plugin_manifests() via
  safe_load_all; both entry-point + filesystem loops iterate all docs; regression test
  asserts BOTH plugins discovered + list_amenders()=={multi-amend}. Unblocks zkm-stt
  (stt + stt-wa, dead on main since id:3874). Worked from TODO.md (never on ROADMAP).
- id:d3a9 (Python 3.14 dev-plugin loading) — two real fixes: sys.modules registration
  before exec_module (else any plugin @dataclass crashes with NoneType.__dict__ on 3.14;
  test actually constructs the dataclass), and auto-heal of a stale .venv via
  `uv sync --frozen -p <running>` (--frozen → no lock mutation, opt-out
  ZKM_NO_PLUGIN_AUTOSYNC=1, graceful warn-fallback). Tests verify --frozen+pinned flags
  and site-packages injection; opt-out test asserts uv never runs.
- id:b7e2 — /meeting-flagged design item (CAS processed-by-version tracking + git-as-byte
  -source); skipped per §5b (design task, already has id).
Spec drift (§4): refreshed the CLAUDE.md §Plugin discovery contract to document multi-doc
plugin.yaml (load_plugin_manifests) + the .venv auto-rebuild / ZKM_NO_PLUGIN_AUTOSYNC
opt-out. Contract pointer v4 — current, no drift.
Reverse-handoff (§5b): adopted the prior orphaned review's ids for two unqualified new
TODO lines — id:40d5 ([MEETING] eager-git-add-during-scan, design-judgment → /meeting
candidate, NOT promoted) and id:dab8 (uncommitted-objects-in-knowledge bug, needs
triage/repro before executor-ready). NOTE: orphan branch relay/orphan/
relay-20260623-070136-24096-review (prior review run) carries commit 6ad331a that
qualified these SAME two items as 40d5/dab8 + a RELAY_LOG paragraph but was never merged
to main, so the raw lines re-appeared this window; I reused 40d5/dab8 (avoiding a
duplicate-id) — the orphan ref is now redundant and safe to delete at integration.
ROADMAP has 0 open items. No gaming flags, no reopens, no friction. routine_open=0.

## 2026-06-23 08:46 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review since relay-ckpt-20260622-2131: d3a9/c4d1 convert.py fixes verified genuinely green (593 on Py3.14, gaming-scan clean, +119 additive test lines); CLAUDE.md plugin-discovery drift fixed; §5b adopted orphan ids 40d5/dab8 (no dup); routine_open=0

## 2026-06-23 08:46 — reviewer (claude-opus-4-8, relay-20260623-083216-13413-review)

review since relay-ckpt-20260623-0846: single commit 4a4be2f, TODO.md-only (ticks W14
done — zkm-whatsapp v0.6.0 lossless multi-source merge: reprocess() manifest heal +
crypt12/14/Java-key decrypt + docs/merge-old-backup.md runbook). Verified the tick is a
genuine, non-gamed summary line for plugin-repo work: zkm-whatsapp HEAD carries v0.6.0
with d4d7aae (heal), 17d24c7 (crypt12/14 + raw key), 8c66c52 (runbook) — claim accurate.
Plugin work lives in TODO.md by the repo scope rule; nothing to mirror to ROADMAP.
Core suite 593 passed; gaming-scan clean (0 DELETED_TEST/ADDED_SKIP/REMOVED_ASSERT).
ROADMAP has 0 open items (0 ROUTINE / 0 HARD). Contract pointer v4, current — no drift.
§5b: no new open ledger items added this window. Orphan relay/orphan/relay-20260623-
070136-24096-review inspected: its TODO.md is based on a pre-W12/W13/W14 snapshot (would
REGRESS — delete the W12-W14 done-entries + id:7c3f + id:d3a9 — if merged), and its
substantive conclusions (c4d1 green, 40d5/dab8 qualified) were already independently
re-derived + recorded by the 0846 checkpoint; only un-merged artifact was its own 07:01
RELAY_LOG paragraph (fully superseded by the 0846 entry). No un-captured information →
RETIRE the orphan ref, do NOT re-merge (re-merge would regress TODO.md). No gaming flags,
no reopens, no friction. routine_open=0.

## 2026-06-23 08:58 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: W14 TODO tick (zkm-whatsapp v0.6.0 multi-source merge) verified genuine; suite 593 green, gaming-scan clean; orphan ref superseded → retire; routine_open=0

## 2026-06-23 09:08 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: 1 docs-only commit (id:3b8a TODO addition); gaming-scan clean; no code/test changes; id:3b8a correctly left as /meeting design-judgment candidate; ROADMAP has 0 open items (routine_open=0)

## 2026-06-23 10:01 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review: W15 TODO tick (id:5d2a, zkm-whatsapp v0.7.0 fail-loud on bad decrypt/non-SQLite) verified genuine; suite 593 green, gaming-scan clean; ROADMAP 0 open; routine_open=0

## 2026-06-23 11:40 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review 9c1dce2 (LEDGER-ONLY docs commit, STT5/id:1f6d done-mark) — clean by vacuity; gaming-scan 0, suite 593/0, contract pointer v4 current, routine_open 0; parked orphan relay-20260623-070136-24096 noted for manual reconcile
## 2026-06-23 07:01 — reviewer (claude-opus-4-8), review since relay-ckpt-20260622-2131

review: 3 commits in window — 2 doc-only (TODO.md), 1 real fix id:c4d1
(multi-document plugin.yaml discovery). Verified id:c4d1 genuinely green:
gaming-scan clean (0 DELETED_TEST/ADDED_SKIP/REMOVED_ASSERT), test_plugin.py
change purely additive (new test_multidoc_plugin_yaml_discovers_all, no removed
asserts), fixture is a real ---separated multi-doc plugin.yaml asserting BOTH
plugins discovered + list_amenders()=={multi-amend} — no fixture special-casing.
Full suite 590 passed (confirms commit claim). c4d1 was worked directly from
TODO.md (never on ROADMAP); ticked [x] there by the executor. ROADMAP has 0 open
items. Contract pointer v4, current — no drift. Reverse-handoff (§5b): qualified
2 unqualified new TODO lines — id:40d5 ([MEETING] eager-git-add-during-scan,
design-judgment → /meeting candidate, NOT promoted) and id:dab8 (uncommitted-
objects bug, needs triage/repro before executor-ready). id:b7e2 (CAS processed-
tracking design) skipped — design task, already has id. No gaming flags, no
reopens, no friction.

## 2026-06-23 15:37 — reconcile (human)

reconcile integrate: review(relay): verify id:c4d1 multi-doc plugin.yaml green; qualify 40d5/dab8 (reverse-handoff)

## 2026-06-23 16:02 — reviewer (claude-opus-4-8)

Opus review (/relay review --all): 1-commit doc-only window (5c802fb todo-update: STT3 id:4ab4 marked handed off). Audited clean — no code, no gaming, no spec drift; cross-ledger consistent with zkm-stt relay-ckpt-20260623-1551 (P1 id:b695 done/running, P2 id:5148 + P3 id:4bf2 RED-specced; umbrella id:4ab4 stays open pending pilot recommendation). routine_open=0.

## 2026-06-23 19:42 — reviewer (claude-opus-4-8), review since relay-ckpt-20260623-1602

Opus review: 1-commit doc-only window (2bd2ccc — the /meeting note
2026-06-23-1807 zkm-amendments-removal-coherence). gaming-scan clean (no test
files touched); full suite 593 green; roadmap-lint exit 0; CLAUDE.md relay-contract
pointer already v4 (no drift); ARCHITECTURE/README current. Reverse-handoff (§5b):
the meeting note decided D1 (id:7b4e ner scrub↔cache = tombstone + emit_set) and D2
(id:f103 → ROUTINE) and minted children 29ac/0566/fa5a but wrote NONE of them to a
ledger (by design — meeting owns "why"). Of those, id:29ac is the only CORE-runnable
piece (add `entities` to `_SET_FIELDS` so emit_set retraction applies to entities, not
just tags — keyed on the `(scope,type,value)` tuple, since entities are typed dicts not
strings). Mini-handoff: promoted id:29ac into ROADMAP as [ROUTINE] with acceptance +
done-check, added the twin TODO.md §Amendment-contract-backlog line (reusing the
meeting token — single-id-two-views), and wrote a RED spec tests/test_amendments_entity_retract.py
(`# roadmap:29ac`; test_entity_sole_producer_dropped_when_unasserted is the genuine RED —
an unasserted entity is NOT retracted today). The plugin children (0566/fa5a → zkm-ner;
f103 → zkm-notmuch) stay OUT of this core ROADMAP per the repo scope rule and are handled
when those plugin repos are reviewed (the note's own Forward actions route them there).
No gaming flags, no reopens. routine_open=1 (id:29ac).

## 2026-06-23 19:44 — reviewer (claude-opus-4-8, fable-standin, relay-loop)

review(relay): doc-only window verified green (suite 593, gaming-scan clean); mini-handoff id:29ac (entities in _SET_FIELDS) to ROADMAP [ROUTINE] + RED spec
