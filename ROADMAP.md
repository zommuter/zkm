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

- [x] [ROUTINE] **Stage 2 (core repo half): tokenless OIDC `release.yml`** <!-- id:3aa3 -->
  Author `.github/workflows/release.yml` in THIS repo (zkm core) so a pushed `vX.Y.Z`
  tag builds and publishes to PyPI via a **Trusted Publisher (OIDC)** — no API token,
  no `UV_PUBLISH_TOKEN`, no repo secret anywhere in the workflow. Mirror `ci.yml`'s
  existing style (`actions/checkout@v4` + `astral-sh/setup-uv@v5`), build with
  `uv build`, publish with `pypa/gh-action-pypi-publish@release/v1`.
  - **Required shape** (this IS the contract the red test pins):
    - `on: push: tags: ["v*"]` — tag-triggered, not branch-triggered.
    - The publishing job declares `permissions: id-token: write` (the OIDC handshake)
      and `contents: read`. `id-token: write` is what makes it tokenless.
    - The job sets `environment: pypi` (GitHub deployment-environment gate).
    - No `password:`/`UV_PUBLISH_TOKEN`/`secrets.*` reference in the publish step.
  - **SCOPE — core repo ONLY.** The parent TODO id:3aa3 says "in all 7 repos"; the
    other repos are separate git repos that are NOT present in a zkm-core worktree
    (`plugins/` is untracked — see the Scope rule at the top of this file), so an
    executor cannot touch them from here. Replication to the plugin repos is a
    separate seam tracked in TODO.md as token 2b63 — do NOT attempt it in this item.
    (Tokens are named bare, without the `id:` prefix, everywhere except this item's
    own trailing marker: `unpromoted-scan.sh` treats ANY `id:<token>` string in this
    file as that item's ROADMAP twin, so a prose mention would silently hide the
    referenced item from the backlog scan.)
  - **This item does NOT make a publish succeed** and is not expected to. The
    Trusted-Publisher registration on PyPI is a human credential action gated behind
    TODO token df4e (`[INPUT — access]`), and PyPI publishing for this project is
    currently DEFERRED pending account recovery (see the 2026-06-21 correction banner
    in `docs/meeting-notes/2026-05-13-1325-pypi-publish-canary.md`). The workflow is
    authored-and-dormant until then: it is valid, committed, and fires only on a `v*`
    tag push. Do not "verify" it by publishing anything.
  - **Acceptance**: `tests/test_release_workflow.py` green (currently RED — the
    workflow file does not exist yet; 6 specs pinning trigger/permissions/environment/
    tokenlessness/build-step/publish-action).
  - **Done-check**: `uv run pytest tests/test_release_workflow.py` green AND
    `uv run pytest -q` fully green AND `uv run ruff check` exits 0 (no new lint).
  - Promoted from TODO id:3aa3 (single-id-two-views; token reused, not minted).

- [x] [ROUTINE] **Add a conforming `@needs-auth` REVIEW_ME box for the 0b37 second-annex-copy auth wall** <!-- id:cf18 -->
  The 2nd-annex-copy step (TODO id:0b37 — `git annex copy --to <fievel-annex-remote>`
  against the real `~/knowledge` store) is blocked on a human-held credential (ssh/annex
  access to the fievel remote) that no relay child can supply unattended. Record that wall
  as a conforming `@needs-auth` box in this repo's `REVIEW_ME.md` so the offline lister
  (`gather-human-backlog.sh --needs-auth`, dotclaude-skills id:1750) surfaces it. Authoring
  the box needs NO credential itself — it only DESCRIBES the credential 0b37 needs, so this
  is executor-ready prose work, not an `[INPUT — access]` item.
  - **The box MUST carry all four mandatory `@needs-auth` fields** (convention in
    dotclaude-skills `relay/references/hard-lanes.md` §"The `@needs-auth` marker"):
    - **what-secret** — ssh/annex access to the fievel annex remote (the credential that
      lets `git annex copy --to` reach it).
    - **where-it-goes** — where that access is applied (the ssh auth to fievel / the
      configured git-annex special-remote the `--to` names).
    - **exact-command** — the exact command the human runs from `~/knowledge`, i.e.
      `git annex copy --to <fievel-annex-remote>` (then `git annex whereis`/`fsck` to
      confirm), matching id:0b37.
    - **why** — without a 2nd annex copy the store is single-copy ("one disk = total
      loss"); it is also the prerequisite for reclaiming local disk via `git annex drop`.
  - The box MUST reference `id:0b37` so the wall is traceable to the blocked work, and
    carry the `@needs-auth` marker token so the lister and `roadmap-lint.sh` recognise it.
  - **Acceptance**: `tests/test_needs_auth_review_box.py` green (currently RED — the box
    does not exist yet; 5 specs pinning marker presence / 0b37 reference / all four field
    labels / the `git annex copy --to` exact-command / the single-store "why").
  - **Done-check**: `uv run pytest tests/test_needs_auth_review_box.py` green AND
    `uv run pytest -q` fully green. (Pure-prose change — no `ruff` surface.)
  - Promoted from TODO id:cf18 (single-id-two-views; token reused, not minted). INBOUND
    routed:9b68 from dotclaude-skills id:1750; lane tagged `[ROUTINE]` at source 2026-07-16.

## Pointers (NOT executor items — wrong repo or gated)

- zkm-whatsapp W-series (W6f media manifest, W-key secret source, W8 owner-JID
  autodetect, W10 Syncthing auto-decrypt, W11 number-change tracking) — live in
  `plugins/zkm-whatsapp` (own repo). W9 WAL-safe backup handling shipped
  v0.3.0 (2026-06-11); no core-side blocker remains.
- NER FP backlog (N9c pipe-cell filter, HTML-entity artefacts) — fix paths are
  in zkm-ner / zkm-eml repos per TODO.md; core `scrub.py` is only the dispatcher.
- SOC1–SOC6 zkm-social — gated on GitHub remote + user review (TODO id:e395).
- Stage 2 OIDC trusted publishing — the CORE-repo half is now a real executor item
  above (token 3aa3). What stays OUT of this roadmap: replication of `release.yml` to
  the plugin repos (TODO token 2b63 — separate repos, unreachable from a core worktree)
  and the PyPI Trusted-Publisher credential registration (TODO token df4e —
  `[INPUT — access]`, human-held). PyPI publishing overall is DEFERRED pending account
  recovery. Tokens are named bare here on purpose — see the note on the 3aa3 item above.
