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
