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
