# Concurrent-run guard

`zkm convert`, `zkm scrub`, and `zkm index` refuse to start if a conflicting
process is already running. This prevents the cross-process sidecar race described
in the meeting note at `docs/meeting-notes/2026-05-14-1011-concurrent-run-guard.md`.

## Conflict matrix

| New command | Existing command | Conflict? |
|-------------|-----------------|-----------|
| `convert`   | `convert` (same plugin) | ✓ same key |
| `convert`   | `scrub` (any plugin) | ✓ sidecar race |
| `scrub`     | `convert` (any plugin) | ✓ sidecar race |
| `convert`   | `index` | – allowed |
| `index`     | `index` | ✓ same key |
| Any         | Same command + same first arg | ✓ same key |

**Key** is `(command, first_arg)` — e.g. `convert(eml)`.

## Exit code

The guard raises with **exit code 75** (`EX_TEMPFAIL`), indicating a temporary
condition that is worth retrying. The mbsync post-commit hook should handle this:

```bash
# Silence EX_TEMPFAIL so the hook does not abort the mail commit:
zkm convert zkm-eml || [ $? -eq 75 ]

# Or wait for the running process to finish, then convert:
zkm status --wait && zkm convert zkm-eml
```

## Bypass

```bash
ZKM_BYPASS_RUN_GUARD=1 zkm convert zkm-eml
```

Use only when you are certain there is no competing process (e.g. test runs,
CI environments, or after manually verifying the store is idle). The guard uses
PID files to detect live processes, so it does not fire if the store has only
stale PID files.

## Observability

`zkm doctor` reports same-key duplicate PID files as a warning:

```
concurrent runs   convert(eml) × 2  (stale: 1 race-survivor pid(s))
```

If you see this after a crash, the stale file will be cleaned up automatically
on the next `zkm status` or `zkm convert` invocation.

## Design scope (v1)

- Guards: `convert`, `scrub`, `index`
- Unguarded: `rm`, `gc`, `clone`, `push`, `pull`, `plugin add/remove`, `init`
  (git's own `.git/index.lock` covers commit-level conflicts; these commands
  have disjoint state paths)
- TOCTOU window: the precheck and PID-file write are not atomic; a race between
  two simultaneous starts is possible but unlikely in practice. The `zkm doctor`
  check provides observability if a race ever fires.
- `--wait-for-busy` (queue semantics) — deferred to Phase 3 queue manager.
