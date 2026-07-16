# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [ ] **id:3aa3 was promoted on a FALSE premise — confirm the narrowed scope.**
  (relay handoff 2026-07-16) The TODO line said "OIDC Trusted Publisher +
  `release.yml` in all 7 repos" with "per-project tokens available (created after
  first publish)". Two parts of that do not survive contact:
  1. **The tokens premise is false.** `zkm` was never published to prod PyPI — the
     2026-06-21 correction banner on `docs/meeting-notes/2026-05-13-1325-pypi-publish-canary.md`
     records that the Stage-1 `uv publish` never landed and that **all PyPI publishing
     is deferred indefinitely pending pip account recovery**. So there is no "first
     publish" and no per-project token. I promoted id:3aa3 anyway because the AUTHOR
     half is still genuinely buildable (a `release.yml` needs no credential) — that is
     exactly what the author-then-run split is for — but the workflow will be
     **authored-and-dormant**: correct, committed, and publishing nothing until id:df4e.
     **Confirm this is wanted**, or park id:3aa3 until account recovery.
  2. **"7 repos" is not executable here, and "7" looks stale.** Each `plugins/zkm-*`
     is its own git repo and `plugins/` is untracked, so a core worktree cannot reach
     them — and this ROADMAP's own scope rule forbids mirroring cross-repo work. I
     therefore narrowed the promoted item to the **core repo only** and split the
     replication out as TODO **id:2b63**. Note **19** plugin repos exist today vs. the
     "7" of the 2026-05-13 Stage-1 set. **Which repos actually get a release workflow
     is your call**, not the relay's — id:2b63 records the question, unanswered.

- [ ] **Five surface items left deliberately untagged — lane is a judgment call.**
  (relay handoff 2026-07-16) Of the 7 surface items, 2 had an unambiguous lane and were
  tagged at source (id:5f86 → `[INPUT — access]`, live remote + real store + credential;
  id:cf18 → `[ROUTINE]`, authoring a doc box needs no credential). The other five I
  refused to guess, per the never-auto-promote-with-a-guessed-lane rule:
  - **id:e7c1** — a DESIGNED umbrella with typed `children:3628,d336,4a4f,173f`. It
    needs no lane because it is a *container*, not work. The clean fix is a `@container`
    marker, but that marker's semantics are ROADMAP-lint-scoped and e7c1 lives in TODO —
    decide whether `@container` should apply to TODO umbrellas too.
  - **id:c63c** — density-ratio pilot, gated on a labeled PDF corpus that does not exist.
    Plausibly `[MECHANICAL]` once the corpus exists, but corpus-building is judgment.
  - **id:3423** — an it-infra cross-cutting *note*, not a task; its executable half
    ("key drive identity on `ID_SERIAL_SHORT`") belongs to the zkm-inventory repo.
    Should become a routed pointer like the cfd1/f3c6/346c lines — but routing to
    another repo is outside a handoff child's scope.
  - **id:aa57** — promoting frontmatter `title` to `CORE_OWNED_SCALARS` is a two-line
    mechanical sync (`src/zkm/conformance.py` + the `docs/plugin-spec.md` registry
    table), but *whether* `title` should be core-owned is field doctrine (cf. id:cfd1),
    and it is a conformance change felt across every plugin. The bundled "audit all
    plugins" half is cross-repo. Wants a decision, then a split.
  - **id:5466** — an inbound git-annex coupling *ack* that is explicitly dormant until
    ≥2 annexed drives exist. Reads as archivable rather than laneable.

- [x] **Three OPEN TODO items carry gate vocabulary but no typed `gated-on:` edge**
  (`orphan-scan.sh --shipped` UNMARKED-GATE, id:46f6): id:c63c (density-ratio pilot,
  "gated, OPEN"), id:f1cf (forward-flag `@{u}` done-gate script, "Gate: next todo-update
  revision OR second need"), id:3174 (subject-clouds overlap, "GATED on slice-0 miss-set
  non-empty"). Each states its gate in prose but lacks the machine-readable `gated-on:`
  sibling comment the typed-ledger reconciler reads. Add a typed `gated-on:` edge to each
  (or confirm the gate is intentionally prose-only) so closure-tracking sees them. Advisory
  — report-only, does not block. (relay review 2026-07-11)
  **RESOLVED 2026-07-11 (/meeting) — confirmed intentionally prose-only.** The `gated-on:`
  marker is id-typed: `orphan-scan.sh:295-311` parses `<!-- gated-on:d,e -->` as TODO-id
  tokens and checks each against local `[x]` state. All three gates are **external-condition**
  gates, not TODO-id dependencies — c63c: labeled-PDF-corpus evidence; f1cf: skill-revision-
  or-2nd-need; 3174: slice-0 miss-set data. None depends on another local TODO id, so an
  id-typed `gated-on:` edge does not apply; the prose gate is correct. NOTE: the UNMARKED-GATE
  backstop has no non-hacky suppressor for external-condition gates and will re-fire on these
  each `--shipped` scan — a durable `prose-only confirmed` marker for orphan-scan.sh is routed
  to dotclaude-skills so the loud detector shrinks rather than re-litigating. See
  docs/meeting-notes/2026-07-11-2132-inventory-data-scope.md (Amendment session).

- [x] **CI `ruff check` tier is RED (122 errors) — PRE-EXISTING, not this window.**
  (relay review 2026-07-12) The `.github/workflows/ci.yml` Lint step runs
  `uv run ruff check`; against the locked ruff 0.15.10 it reports 122 violations
  (78 E501 line-too-long, 24 I001 import-order, 7 UP017, 6 UP035, 3 F401, 2 UP037,
  1 F841, 1 F541). This is repo-wide lint debt from ruff-version drift (pin `>=0.4`
  → locked 0.15.10), **NOT introduced by this window's commits**: the changed source
  files carry the *same* count at the checkpoint tree (`cli.py` 13 both, `convert.py`
  2 both, `store.py` 0 both — id:998b added zero lint errors). The pytest tier is
  fully green (628 passed). Decide: run `ruff check --fix` for the 43 auto-fixable
  (I001/F401) + address E501, or relax the ruff config — either way the CI Lint step
  fails today. Advisory — does not block this review (pytest green, work verified
  genuine).
  — DECIDED 2026-07-13 (relay human): FIX + E501 path — run `ruff check --fix` (43 auto: I001/F401) then manually resolve the 78 E501 line-too-long; do NOT relax config or pin an older ruff. Re-lane as [ROUTINE] executor work.
  **PROMOTED 2026-07-13 (relay review) → ROADMAP `[ROUTINE]` id:04e5** (reverse-handoff, §5b; fresh id — no prior TODO token for lint debt). Verified this window: `uv run ruff check` = 122 errors (43 fixable); `uv run pytest -q` = 632 passed. Box resolved.
