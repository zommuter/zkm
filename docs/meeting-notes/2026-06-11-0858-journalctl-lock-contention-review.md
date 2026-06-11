# 2026-06-11 — journalctl lock-contention review

**Started:** 2026-06-11 08:58
**Session:** c5e1b51a-e847-4423-94f1-4e11bc44f334
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Review `zkm-index-lock-watch` journal for git index.lock contention events; decide on stronger protection.

## Context

A `_git_add()` wrapper was shipped 2026-05-14 (Class 1 dispatch, 454 tests) in `src/zkm/cli.py`. It emits via `systemd-cat -t zkm-index-lock-watch` whenever `git add` fails with an `index.lock` error. A TODO item added 2026-06-11 asked to review this log after ~4 weeks and decide whether stronger protection (fcntl-lock, retry loop, etc.) was warranted.

## Plan

Run `journalctl -t zkm-index-lock-watch --no-pager` and count events. Decision rule: if events are zero or a handful with no clustering, close as no-action; if events cluster or recur frequently, open a design meeting on retry/lock strengthening.

## Implementation findings

```
$ journalctl -t zkm-index-lock-watch --no-pager | wc -l
2   (= 1 event entry, journal header line + content)

Jun 06 16:03:39 zomni zkm-index-lock-watch[175854]: zkm git-add lock-contention in /home/tobias/knowledge: fatal: Unable to create '/home/tobias/knowledge/.git/index.lock': File exists.
Jun 06 16:03:39 zomni zkm-index-lock-watch[175854]: Another git process seems to be running in this repository, or the lock file may be stale
```

**One event** in ~4 weeks of production use (2026-05-14 → 2026-06-11). No clustering, no recurrence.

## Decisions

- **No action.** Single-event rate in 4 weeks is negligible; no stronger protection needed at this time.
- The existing watchpoint (`systemd-cat -t zkm-index-lock-watch`) remains in place as the observability layer. The sidecar fcntl-lock TODO and DB-pivot trigger TODO retain their existing re-open conditions unchanged.
- The CLAUDE.md "Observe before preventing" heuristic applies: the pilot confirms the rate is too low to justify infrastructure investment.

## Action items

- [x] Close `from 2026-06-11: review journalctl -t zkm-index-lock-watch` TODO item — rate is 1 event / 4 weeks, no action.
