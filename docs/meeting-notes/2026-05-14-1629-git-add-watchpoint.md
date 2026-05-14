# 2026-05-14 — git add watchpoint instrumentation

**Started:** 2026-05-14 16:29
**Session:** 264dcb89-7541-4ac7-af89-210bc636e311
**Mode:** Class 1 dispatch (impl-ready — decision made in concurrent-run-guard meeting 2026-05-14)
**Topic:** Instrument `git add -A` call sites to log `.git/index.lock` contention events to journald for 4-week observation window.

## Context

The concurrent-run guard meeting (2026-05-14) spawned a watchpoint: investigate whether two simultaneous zkm commands could produce a non-atomic `git add` + `git commit` via `.git/index.lock` contention. Decision was to observe before adding prevention. Instrument first; review 2026-06-11.

No-arg `/meeting` classified this as Class 1: linked meeting note with a clear Decisions section, ~1 session effort.

## Plan

Add `_git_add(cwd: Path)` helper in `src/zkm/cli.py` that:
- Runs `git add -A` with `stderr=subprocess.PIPE`
- On failure: re-emits stderr (so hook log / tee still captures it)
- If `"index.lock"` in stderr: emits `systemd-cat -t zkm-index-lock-watch -p warning` (best-effort; `FileNotFoundError` silently ignored on non-systemd hosts)
- Raises `CalledProcessError` — identical behavior to the previous `check=True` calls

Wire into 3 call sites in `cli.py`: `cmd_rm` (line ~243), `cmd_gc` (line ~284), `cmd_convert` (line ~524).

## Implementation findings

- `store.py:86` git add is in `init_store()` only — not a concurrent-run path, left unchanged.
- 454 tests pass after change.
- Pre-existing Pyright "unreachable code" warnings in `cli.py` (lines 507, 516, 675, 791, 844, 849) are unrelated to this change.

## Decisions

- `_git_add()` is the new canonical git-add wrapper in core CLI; direct `subprocess.run(["git", "add", ...])` calls replaced.
- systemd-cat tag: `zkm-index-lock-watch` (query: `journalctl -t zkm-index-lock-watch`).
- Observation window: 4 weeks; review date 2026-06-11.
- No lock-prevention code added — watchpoint only.

## Action items

- [x] `src/zkm/cli.py` — `_git_add()` helper + 3 call-site replacements — 2026-05-14
- [x] `TODO.md` — mark watchpoint done; add `from 2026-06-11` review item
- [ ] from 2026-06-11: `journalctl -t zkm-index-lock-watch` — review for events; decide if prevention needed
