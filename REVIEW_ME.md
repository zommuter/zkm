# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [x] tests/test_gamemode_guard.py::test_bypass_run_guard_also_bypasses_gamemode_lock
  (roadmap:1098) — interpretation: `ZKM_BYPASS_RUN_GUARD=1` bypasses BOTH the
  concurrent-run guard and the new gamemode-lock guard (one "I know what I'm
  doing" switch, no second env var). Also encoded nearby: exit code 75 reused,
  and `zkm doctor` reports the lock without flipping its exit code. — confirmed by user 2026-06-15 (review_me batch triage)

- [x] tests/test_cli_amenders.py::test_zero_created_skips_amenders
  (roadmap:dd89) — interpretation: skipping the amender pass on zero-created
  converts also skips zkm-ner's whole-store `apply_queue` drain; queued
  amendments wait for the next non-empty convert or an explicit
  `zkm convert ner`. Alternative (run amenders with created=[] so the queue
  still drains) was rejected for the no-op-mbsync speed win. — confirmed by user 2026-06-13 (batch triage)

- [x] tests/test_conformance.py::TestAmenderCreatedParam::test_amender_created_finding_is_warn_not_fail
  (roadmap:e1fc) — interpretation: an amender without the `created` param is a
  WARN (works, but full-sweeps on every trigger), not a FAIL — existing
  amender wheels must stay shippable. Escalate to fail only via a future
  plugin-spec major bump. — confirmed by user 2026-06-13 (batch triage)

- [x] tests/test_selfscope.py (roadmap:62f3, shipped in this handoff's C5) —
  two judgments: (a) fail-open — ANY precheck error (no systemd-run, systemctl
  failure, non-Linux) silently runs the index unscoped, because indexing on
  fievel/pixel must never break on account of a zomni-only feature; (b) when
  `zkm-index.scope` already exists (frozen or active) the new run exits 75
  rather than joining/blocking on the frozen scope. — confirmed by user 2026-06-15 (review_me batch triage)

- [x] tests/test_doctor_amendment_queue.py (roadmap:83c7, seeded in review
  2026-06-12) — interpretation: pending-queue visibility is a *cheap count*
  (number of queue .json files, never parsed/validated) shown in `zkm doctor`
  and appended to the dd89 skip notice. Alternative (auto-drain the queue on
  zero-created converts) was rejected — it would undo the dd89 speed win. — confirmed by user 2026-06-13 (batch triage)


- [x] tests/test_amendments_retract.py (roadmap:25ec, relay HARD-execute
  2026-06-19) — TWO items for the human budget:
  (a) **OWED at integration, not done by the relay child:** the
  `pyproject.toml` bump 0.14.0→0.15.0 is committed, but the matching `v0.15.0`
  git tag and `uv publish` are NOT done — a relay child must never tag, push, or
  publish (relay invariant). The integrator/owner must `git tag v0.15.0` on the
  merge commit and `uv publish` so Stage 2 (zkm-notmuch f103, routed:8b00) can
  build against a released API. The bump-and-tag rule (tag in the SAME commit as
  the version change) is intentionally deferred here because the relay never tags.
  (b) **Accepted design hazard (Riku's blind spot, DP2 in the meeting):** the
  ref-count-to-zero rule keys removal on tag *name*, not a UID. A user-hand-typed
  tag that happens to match a producer's tag gets absorbed into that producer's
  set; if the producer later drops it and no other producer asserts it, it IS
  removed (rule 3 passes). The meeting consciously accepted this — auto-remove +
  git/sidecar reversibility net + non-mandatory dry-run, NOT a quarantine queue
  (tag churn like inbox/unread makes mandatory review unusable). Confirm this
  trade-off is acceptable, or whether a baseline-snapshot "this tag predates any
  producer claim" protection is wanted before zkm-notmuch starts emitting sets.
  - **(b) RESOLVED 2026-06-21 (/relay human): accept the trade-off AS-IS** — keep
    auto-remove + reversibility net, no baseline-snapshot guard, no quarantine queue.
    Ratifies the meeting's deliberated decision; zkm-notmuch (f103) may emit sets.
  - **(a) RESOLVED 2026-06-21 (/meeting, owner):** `v0.15.0` tag pushed to both `origin`
    (fievel) and `github`. **`uv publish` DEFERRED INDEFINITELY** — pip account recovery in
    progress and `zkm` is not currently on PyPI at all (returns "Not Found", contradicting the
    SB5/canary memory's "0.5.0 published" claim — worth investigating). Wheel built at
    `dist/zkm-0.15.0-py3-none-any.whl`. Publish is no longer a blocker on this item; re-run
    `UV_PUBLISH_TOKEN=… uv publish` once the account is recovered. Tracked under the Stage 2
    OIDC item in TODO.md.

- [x] id:8f1c — duplicate canonical token on TWO checkbox lines in TODO.md (one OPEN
  "Git operations on `$ZKM_STORE` are now slow…" measure-first note, one CLOSED `[x]`
  "…DECIDED 2026-06-23-2251…" decided version). Pre-existing (already count-2 at
  relay-ckpt-20260625-1627, NOT introduced this window). The closed item's body says it
  carries the original note forward, so the id-reuse may be intentional — but a shared
  canonical id across an open AND a closed checkbox makes orphan-scan / cross-ledger
  checkbox-state ambiguous (which state is authoritative?). Decide: either re-id the still-
  open measure-first half to a fresh token, or archive/close the open half if the DECIDED
  item fully supersedes it. (Review-flagged 2026-06-26; the unrelated f3c6 collision was
  auto-fixed this turn → N9e re-id'd to 5a0b.)
  — **RESOLVED 2026-06-26 (/meeting, owner): re-id the open half.** The CLOSED line 272
  keeps id:8f1c as the authoritative DECIDED record (annex-anchoring = driver A, pack bloat).
  The OPEN half was NOT superseded — it carries the independent **driver B** residual
  (500k-file working-tree walk); verified `core.fsmonitor`+`core.untrackedCache` both UNSET
  on `~/knowledge`, so the config quick-wins are real and unfinished. Re-id'd to fresh
  **id:6e13** and narrowed to driver-B-only. Cross-ledger ambiguity gone; work preserved.
