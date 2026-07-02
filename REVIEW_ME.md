# Human review queue <!-- budget: 15 min -->

Judgment calls encoded in red tests — confirm or correct the interpretation.
Max ~10 open boxes; the reviewer prunes resolved ones each review turn.

- [x] **Central `[ROUTINE]` items that execute in PLUGIN repos are un-promotable —
  disposition gap.** Four TODO items are lane-tagged `[ROUTINE]` (apex DQ triage
  2026-07-02 / this review) but their execution lives in plugin repos, which the
  ROADMAP scope rule ("plugin-repo work stays in TODO.md, NOT mirrored here")
  correctly excludes: id:cfd1 (D2/D3 renames across calendar/whatsapp/scan),
  id:f3c6 (zkm-social url_sha256 write + migration), id:346c (zkm-social/zkm-ner
  REVIEW_ME boxes), id:f9a7 (16-plugin dev-deps sweep). `unpromoted-scan` will
  keep reporting them as `promote` candidates every round — a standing false
  "needs HANDOFF" signal on this repo. Decide the disposition: (a) route each into
  the owning plugin repo's ledger via the shared inbox and close the central line
  to a pointer, (b) teach the scan a "central-tracking, executes-elsewhere" marker,
  or (c) accept the noise. (Relay review 2026-07-02; the three CORE-runnable
  `[ROUTINE]` items 4431/e2c4/1e4f were promoted to ROADMAP this same pass.)
  — OWNER DECISION: route to plugin repos — cfd1/f3c6/346c/f9a7 filed via shared
  inbox (routed twins), central lines reduced to pointers (relay human 2026-07-02)
