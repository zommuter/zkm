# zkm meeting overrides

The canonical meeting format and skill live at `~/.claude/skills/meeting/`.
This file contains only zkm-specific augmentations, appended to the global format at meeting time.

## Past meetings

- [2026-05-07 — Object storage scope](2026-05-07-object-storage.md) — CAS/sidecar/inbox as core library vs. plugin code; `zkm rm` / `zkm gc` sequencing
- [2026-05-08 — Doc chunking scope](2026-05-08-doc-chunking.md) — embed-side chunking as core feature; char-window MVP; file-level RRF aggregation
- [2026-05-08 — Next plugins](2026-05-08-next-plugins.md) — photo→pdf→scan order; fan-out overlap policy; whatsapp deferred to scoping meeting
- [2026-05-08 — Information flow](2026-05-08-information-flow.md) — drop A/B/C; extraction-cache + frontmatter-amendment replace pipeline; zkm-notmuch as first amender; meeting now interactive
- [2026-05-08 — Repo reorg](2026-05-08-repo-reorg.md) — plugin repos nest in ~/src/zkm/plugins/; fievel mirrors at zkm-plugins/; no core subdir; no rename to zkm-core
- [2026-05-08 — mbsync auto-trigger](2026-05-08-mbsync-hook.md) — git post-commit hook in ~/mail/.git/hooks/ triggers zkm convert + index; dirty-tree guard in core; embed deferred to A5 systemd timer
- [2026-05-08 — SIGUSR1 progress + zkm status](2026-05-08-1913-sigusr1-status.md) — PID-file model in .zkm-state/running/; fibonacci auto-writes; SIGUSR1 dual channel (file + stderr); zkm status survey command
- [2026-05-08 — Encoding audit](2026-05-08-2101-encoding-audit.md) — charset-normalizer detection + ftfy mojibake repair in zkm-eml; plugin dep loading workaround; uv.sources path fix
- [2026-05-08 — Privacy audit](2026-05-08-2254-privacy-audit.md) — full GitHub repo scan; repo clean; claude.ai URL in 5d8646c accepted as residual risk; no remediation needed
- [2026-05-08 — Tagging cadence](2026-05-08-2318-tagging-cadence.md) — bump-and-tag rule; loose-0.x; 6 retroactive tags; plain vX.Y.Z per repo; coupling deferred
- [2026-05-10 — Entity extraction scoping](2026-05-10-1148-entity-extraction.md) — NER before whatsapp; zkm-ner amender plugin; extraction-cache lands with it; spaCy+patterns+GLiNER-opt-in; name-not-UID constraint
- [2026-05-10 — TODO audit + N9a](2026-05-10-1628-n9a-value-normalization.md) — Class 1 dispatch; Entity.__post_init__ strips value whitespace; 3 regression tests
- [2026-05-10 — N9b email-header stoplist](2026-05-10-1640-n9b-email-header-stoplist.md) — class 1+2+3 scope; two-stage textfilter (pre-strip + 14-word stoplist); model_version bump for cache invalidation; pilot re-run before 2026-06-05
- [2026-05-10 — N9b scrub CLI](2026-05-10-2142-n9b-scrub-cli.md) — scrub-pass vs amendment replace-mode; decision: `zkm scrub <plugin>` core CLI (N=2: stoplist + future POS-filter); plugin contract scrub(); dry-run default; sidecar boundary; replace-mode deferred
- [2026-05-11 — NER next after N9b](2026-05-11-0946-ner-next-after-n9b.md) — zkm status observation deferred; N9c = hybrid POS-filter + _COMMONNOUN_STOPLIST; N9d/N9e backlog for LLM verifier + closed-loop feedback; CLAUDE.md version literals to be dropped
- [2026-05-11 — Plugin name convention](2026-05-11-1401-plugin-name-prefix.md) — bare manifest names everywhere (eml/pdf/photo); find_plugin() strips zkm- prefix for compat; β migration (no store rewrite); dir names stay zkm-*; verb-order deferred
- [2026-05-11 — N10/N11 docs bundle](2026-05-11-1506-n10-n11-docs-bundle.md) — docs/ner.md (new); entity-model.md PII note; CLAUDE.md version literals dropped + Phase 2.5 NER correction; object-storage.md reconciliation deferred
