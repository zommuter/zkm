# Roadmap <!-- fables-turn roadmap v1 -->

Executor-facing task spec. Each item is sized for ONE Sonnet session. Items are
the single source of truth — TODO.md carries only a summary line. Executors tick
checkboxes; only the reviewer adds, removes, or re-scopes items.

**Scope rule for this repo**: every item below is runnable in the zkm core repo
alone — `plugins/` is empty in a fresh worktree and the suite must stay green
without any plugin repo present. Plugin-repo work stays in TODO.md (central
ledger by design) and is NOT mirrored here.

## Phase 2 "done" definition (CONFIRMED — owner 2026-06-13)

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

- [x] [ROUTINE] **Shell autocompletion for `zkm` (bash + zsh + fish)** <!-- id:e9e2 -->
  Ship a `zkm completion [bash|zsh|fish]` subcommand that prints the shell
  completion script (Click's native `_ZKM_COMPLETE=<shell>_source` mechanism) plus
  install docs in `docs/install.md`. Wire DYNAMIC plugin-name completion on the
  plugin-argument commands (`zkm convert <TAB>`, `zkm scrub <TAB>`) via a Click
  `shell_complete` callback that lists names from the live discovered plugin set
  (`convert.list_plugins()` — entry-points ∪ `plugins/*/plugin.yaml`, incl. multi-doc
  secondaries). Completion MUST stay fast: use the lightweight manifest scan, never
  `_load_plugin_module` (no heavy plugin imports on `<TAB>`).
  - **Acceptance**: `zkm completion bash|zsh|fish` each exit 0 and print a non-empty
    script; the `convert` command's `plugin` argument completes from the discovered
    plugin set. Green: `tests/test_completion.py` (currently RED — 4 specs).
  - **Done-check**: `uv run pytest tests/test_completion.py` green; full suite green;
    `uv run ruff check src/zkm/cli.py` introduces no NEW lint errors vs. baseline.
  - Reverse-handoff mini-handoff of TODO id:e9e2 (single-id-two-views; reuse token).

- [x] [ROUTINE] **Clear the CI `ruff check` lint debt (122 errors → 0)** <!-- id:04e5 -->
  The `.github/workflows/ci.yml` Lint step runs `uv run ruff check` and fails today
  with 122 violations against the locked ruff 0.15.10 (78 E501 line-too-long, 24 I001
  import-order, 7 UP017, 6 UP035, 3 F401, 2 UP037, 1 F841, 1 F541). Repo-wide debt
  from ruff-version drift, NOT introduced by any recent window. DECIDED 2026-07-13
  (relay human): FIX path — do NOT relax the ruff config or pin an older ruff.
  - **Steps**: (1) `uv run ruff check --fix` to auto-resolve the 43 fixable (I001/F401)
    and the mechanical UP0xx pyupgrade rules; (2) manually resolve the remaining E501
    line-too-long (wrap/reflow long lines — do not add per-line `# noqa` en masse; a
    justified `# noqa: E501` is acceptable only for genuinely unbreakable lines such as
    long URLs/paths). Do not weaken assertions or delete tests to satisfy the linter.
  - **Acceptance**: `uv run ruff check` exits 0 (the CI Lint tier is the spec — currently
    RED with 122 errors, so it IS the red spec; no separate pytest file needed).
  - **Done-check**: `uv run ruff check` exits 0 AND `uv run pytest -q` still fully green
    (632 passed at review time) — no behaviour change from the lint cleanup.
  - Promoted from the DECIDED REVIEW_ME box (relay human 2026-07-13); genuinely new
    work, fresh id (no prior TODO token for lint debt).

## Pointers (NOT executor items — wrong repo or gated)

- zkm-whatsapp W-series (W6f media manifest, W-key secret source, W8 owner-JID
  autodetect, W10 Syncthing auto-decrypt, W11 number-change tracking) — live in
  `plugins/zkm-whatsapp` (own repo). W9 WAL-safe backup handling shipped
  v0.3.0 (2026-06-11); no core-side blocker remains.
- NER FP backlog (N9c pipe-cell filter, HTML-entity artefacts) — fix paths are
  in zkm-ner / zkm-eml repos per TODO.md; core `scrub.py` is only the dispatcher.
- SOC1–SOC6 zkm-social — gated on GitHub remote + user review (TODO id:e395).
- Stage 2 OIDC trusted publishing — cross-repo CI work across all 7 repos.
