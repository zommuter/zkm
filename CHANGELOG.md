# Changelog

<!-- DERIVED at relay integrate from existing relay state (report.summary + worked ids) by
     relay/scripts/changelog-append.sh (id:b8fa). Newest release first; never hand-edit or
     reorder past buckets. RELEASE-bucketed by version (## vX.Y.Z — DATE): the reviewer's bump
     at integrate (id:e647) supplies the version. Started from now; history is NOT backfilled
     (per-close tags are unrecoverable). Design: dotclaude-skills
     docs/meeting-notes/2026-07-17-1541-semver-trigger-and-fleet-changelog.md (D2/D4). -->

## v0.22.0 — 2026-07-18

- Added `zkm locate <term>` — scopes search to inventory/find-dump/** shards only, path-aware (component split + camelCase + substring) so find-dump paths no longer lose to prose in BM25; closes id:7f90. (id:7f90)
