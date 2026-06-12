# Roadmap <!-- fables-turn roadmap v1 -->

Executor-facing task spec. Each item is sized for ONE Sonnet session. Items are
the single source of truth — TODO.md carries only a summary line. Executors tick
checkboxes; only the reviewer adds, removes, or re-scopes items.

**Scope rule for this repo**: every item below is runnable in the zkm core repo
alone — `plugins/` is empty in a fresh worktree and the suite must stay green
without any plugin repo present. Plugin-repo work stays in TODO.md (central
ledger by design) and is NOT mirrored here.

## Phase 2 "done" definition (PROPOSED — confirm in REVIEW_ME.md)

Phase 2 is declared done when all three hold:

1. **γ schema shipped** — DONE (E1–E13 closed 2026-05-21).
2. **Store hygiene + management landed** — DONE (`zkm rm`/`zkm gc` dry-run-first,
   `zkm remote/clone/push/pull` backend-aware).
3. **Observation-period gate** — 14 consecutive days of real-store operation
   (mbsync-triggered converts + manual index/search) with zero manual
   interventions for data integrity (no orphaned CAS objects beyond `zkm gc`
   dry-run noise, no sidecar duplicate-producer recurrences, no run-guard
   false positives). Clock starts when the last [ROUTINE] item below ships;
   any intervention restarts the window.

Rationale: 1–2 are already true, so the binding criterion is 3 — it follows the
"observe before preventing" heuristic and avoids declaring victory on the same
day the last feature merges. FP-rate targets for NER are explicitly NOT part of
the gate (N9c/N9d accepted-as-is decisions stand).

## Items

- [ ] Refuse to start convert/scrub/index while the gamemode lock is present [ROUTINE] <!-- id:1098 -->
  - **Acceptance**: When the lock file exists (path from `$ZKM_GAMEMODE_LOCK`,
    default `/tmp/zomni-gamemode.lock`), entering `RunSession` for
    `convert`/`scrub`/`index` raises a ClickException with **exit code 75**
    and a message naming the lock path, BEFORE any PID file is written.
    `ZKM_BYPASS_RUN_GUARD=1` bypasses this check too (same bypass as the
    concurrent-run guard). `zkm doctor` prints a `gamemode lock` row when the
    lock is present (informational, does not flip doctor's exit code).
    User-observable: `touch /tmp/zomni-gamemode.lock && zkm index` exits 75
    immediately instead of competing with a game for CPU/RAM.
  - **Tests**: `tests/test_gamemode_guard.py`, marked `# roadmap:1098`.
    RED spec: `test_default_lock_path_constant`,
    `test_runsession_refuses_when_gamemode_lock_present`,
    `test_refusal_exits_75_and_writes_no_pid_file`,
    `test_default_used_when_env_unset`,
    `test_cli_index_exits_75_when_lock_present`,
    `test_doctor_reports_gamemode_lock`.
    Already-green GUARDs (do not break):
    `test_env_var_overrides_default_lock_path`,
    `test_bypass_run_guard_also_bypasses_gamemode_lock`.
  - **Done-check**: `uv run pytest tests/test_gamemode_guard.py` (then full
    `uv run pytest` green)
  - **Context**: `src/zkm/runstate.py` (`RunSession.__enter__`, the
    `ConcurrentRunError` exit-75 pattern), `src/zkm/cli.py` `cmd_doctor`.
    First half of TODO id:f631. Hermeticity: conftest gains an autouse fixture
    pointing `ZKM_GAMEMODE_LOCK` at a nonexistent tmp path (already added with
    the red tests) — mirror of the `ZKM_BYPASS_DIRTY_CHECK` pattern.
    See ARCHITECTURE.md §D7 and §Conventions (exit codes).

- [x] Self-scope `zkm index` under systemd-run for freeze/thaw control [HARD — strong model] <!-- id:62f3 -->
  (done in handoff C5, 2026-06-12: `src/zkm/selfscope.py` + cmd_index hook;
  10 tests in `tests/test_selfscope.py` green; smoke-verified on zomni —
  journal shows zkm-index.scope starting the re-exec'd command. Judgment
  calls flagged in REVIEW_ME.md.)
  - **Why HARD**: environment-dependent (systemd user manager presence,
    `INVOCATION_ID` semantics differ between service and scope units, Termux/
    Raspbian fallback), re-exec must be loop-proof and absolutely must not fire
    inside pytest/CliRunner, and the "scope exists but is frozen" collision
    case needs a judgment call (join-and-block vs fail-clean).
  - **Acceptance**: `zkm index` re-execs itself under
    `systemd-run --user --scope --collect --unit=zkm-index` when not already
    scoped, so `systemctl --user freeze zkm-index.scope` (zomni gamemode
    toggle) can freeze a running index. Skip conditions (run unscoped):
    `ZKM_SELF_SCOPED` set (loop guard, injected on re-exec), `INVOCATION_ID`
    set (already under systemd), `ZKM_NO_SELF_SCOPE=1` (opt-out; autouse in
    conftest), `systemd-run` not on PATH, or any precheck error (fail-open —
    indexing must still work on fievel/pixel). If `zkm-index.scope` already
    exists (frozen or active), exit 75 with a message stating the scope state.
    Second half of TODO id:f631; see zomni meeting note
    2026-06-11-1328-memory-swap-failsafe-llama-swap.
  - **Tests**: `tests/test_selfscope.py` marked `# roadmap:62f3` (written
    red-first during execution; monkeypatch `shutil.which`/`subprocess.run`/
    `os.execvpe` — no real systemd calls in tests).
  - **Done-check**: `uv run pytest tests/test_selfscope.py` (then full suite)

- [ ] Skip the amender pass when the triggering convert created zero files [ROUTINE] <!-- id:dd89 -->
  - **Acceptance**: After a non-amender `zkm convert <plugin>` that returns an
    empty created list (and was not cancelled), the CLI does NOT invoke any
    amender; it prints `Skipping amenders (0 files created)` to stderr.
    Amenders still run when ≥1 file was created, and explicit
    `zkm convert ner` (amender as primary) is unaffected. User-observable:
    a no-op mbsync-triggered `zkm convert eml` returns in seconds instead of
    sweeping the store through zkm-ner's capability-unaware path.
  - **Tests**: `tests/test_cli_amenders.py` — marked `# roadmap:dd89`
    (currently RED): `test_zero_created_skips_amenders`,
    `test_zero_created_prints_skip_notice`; plus already-green regression
    guards `test_nonzero_created_still_runs_amenders`,
    `test_cancelled_convert_skips_amenders` (protect against
    over-implementation — do not break them).
  - **Done-check**: `uv run pytest tests/test_cli_amenders.py` (then full suite)
  - **Context**: `src/zkm/cli.py` `cmd_convert` amender loop (the
    `if not cancelled and not no_amenders and not is_amender:` block).
    Amender-contract hardening takes precedence over new amender types
    (ARCHITECTURE.md §D5). NOTE the encoded judgment call (REVIEW_ME.md):
    skipping also skips zkm-ner's whole-store `apply_queue` drain on zero-file
    converts; queued amendments then wait for the next non-empty convert or an
    explicit `zkm convert ner`.

- [ ] Conformance: warn when an amender's convert() lacks the `created` parameter [ROUTINE] <!-- id:e1fc -->
  - **Acceptance**: `zkm test <amender-plugin>` emits a **warn**-level
    interface finding (not fail) when a plugin with `kind: amender` has a
    `convert()` that neither declares a `created` keyword parameter nor
    `**kwargs` — such amenders silently full-sweep the store on every
    triggered run. Converter-kind plugins are unaffected. The finding message
    names `created` and points at docs/plugin-spec.md.
  - **Tests**: `tests/test_conformance.py::TestAmenderCreatedParam`, marked
    `# roadmap:e1fc`. RED spec: `test_amender_without_created_param_warns`,
    `test_amender_created_finding_is_warn_not_fail`. Already-green GUARDs:
    `test_amender_with_created_param_no_warning`,
    `test_converter_without_created_param_no_warning`.
  - **Done-check**: `uv run pytest tests/test_conformance.py` (then full suite)
  - **Context**: `src/zkm/conformance.py` `check_interface` (follow the
    existing `progress`-parameter check pattern); `_supports_created` in
    `src/zkm/convert.py`. Also add one line to `docs/plugin-spec.md`'s amender
    section documenting the expectation. ARCHITECTURE.md §D5.

## Pointers (NOT executor items — wrong repo or gated)

- zkm-whatsapp W-series (W6f media manifest, W-key secret source, W8 owner-JID
  autodetect, W10 Syncthing auto-decrypt, W11 number-change tracking) — live in
  `plugins/zkm-whatsapp` (own repo). W9 WAL-safe backup handling shipped
  v0.3.0 (2026-06-11); no core-side blocker remains.
- NER FP backlog (N9c pipe-cell filter, HTML-entity artefacts) — fix paths are
  in zkm-ner / zkm-eml repos per TODO.md; core `scrub.py` is only the dispatcher.
- SOC1–SOC6 zkm-social — gated on GitHub remote + user review (TODO id:e395).
- Stage 2 OIDC trusted publishing — cross-repo CI work across all 7 repos.
