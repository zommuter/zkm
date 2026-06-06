# 2026-06-06 — Convert-overlap review

**Started:** 2026-06-06 15:10
**Session:** 6ffb79cd-3e9f-4bed-b169-784ed19727fe
**Mode:** Class 2 planning record (no meeting was held — review-and-decide output)
**Topic:** Review journald evidence for `zkm convert` overlap; decide whether a lock is warranted.

## Context

TODO item (mbsync auto-trigger section) asked to review journald evidence once enough data had accumulated (gate date: 2026-06-05).

## Plan

1. `journalctl --since 2026-06-01 | grep zkm` to find relevant events.
2. Look for concurrent `zkm convert` PIDs or "convert already running" guard fires.
3. Decide: add locking infrastructure if overlap observed; close as no-op if not.

## Implementation findings

**No convert-overlap observed.** All `zkm-eml-hook` invocations (PIDs 16997, 49068, 71646, 78036, 85150, 111855, …) ran sequentially — each completing its convert+commit before the next mbsync trigger fired. The concurrent-run guard (`_MUTUAL_EXCLUSIVE = {"convert", "scrub"}` in `runstate.py`) was never exercised for convert.

**Index blocking works correctly.** `zkm index` pid 6888 (started 2026-06-01T08:00:37) was still live at 15:44, blocking 8+ auto-triggered index attempts. All correctly received `Error: index already running`.

**Side-finding A: `.json.lock` files committed to knowledge store.** `mail/_objects/*/abc.json.lock` and `inbox/mail/*/file.origin.json.lock` appear as `create mode` entries in git commits. Root cause: the existing `~/knowledge/` store was initialized before 2026-05-14 (commit 457fa33) when `*.lock` was added to `store.py:_GITIGNORE`. The existing store's `.gitignore` lacks `*.lock`.

**Side-finding B: Long-running index.** `zkm index` ran for 7+ hours on 2026-06-01. Likely hung on embed/500-wall issue (known). Warrants a timeout or dead-man's mechanism.

**Side-finding C: NER amender failing.** numpy 2.4.4 compiled for Python 3.12, but zkm uv-tool env uses Python 3.14. Separate issue.

## Decisions

- **No additional convert-overlap lock needed.** Sequential mbsync triggers never race; the existing concurrent-run guard is sufficient for the rare edge case.
- Two new follow-up items added to TODO.md: A-gitignore (fix `~/knowledge/.gitignore` missing `*.lock`) and A-index-stuck (investigate/add timeout to long-running index).

## Action items

- [x] Review journald evidence and decide on lock. **Decision: no lock needed.**
- [ ] Add `*.lock` to `~/knowledge/.gitignore` + `git -C ~/knowledge rm --cached -r --ignore-unmatch '*.lock'` to clear committed lock files. <!-- id:9047 -->
- [ ] Investigate 2026-06-01 8h+ index hang; consider timeout or dead-man's check in `zkm index`. <!-- id:141a -->
