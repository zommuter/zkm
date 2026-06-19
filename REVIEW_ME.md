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


- [ ] tests/test_amendments_retract.py (roadmap:25ec, relay HARD-execute
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
