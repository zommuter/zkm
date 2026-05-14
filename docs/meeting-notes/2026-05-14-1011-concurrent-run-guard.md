# 2026-05-14 — Concurrent-run guard for zkm CLI

**Started:** 2026-05-14 10:11
**Session:** aa2ab60f-c91c-492d-a351-9ae262b52085
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity)
**Topic:** Size a same-key + cross-key refusal guard on zkm CLI commands using the existing PID-file mechanism, without locking in a future daemon's queueing design.

## Concrete state (read 2026-05-14 10:11)

- `src/zkm/runstate.py`: `RunSession` context manager writes `<store>/.zkm-state/running/<pid>.json` on enter, unlinks on exit. Atomic write via tmp+rename. SIGUSR1 handler installed for live progress.
- Commands wrapped today: `convert` (`cli.py:455`, `args=[plugin]`), `scrub` (`cli.py:603`, `args=[plugin]`), `index` (`cli.py:750`).
- `_take_status_snapshot` (`cli.py:839`) is the canonical "what's live?" function — `os.kill(pid, 0)` liveness test, stale-file cleanup, optional SIGUSR1 fan-out (`send_sigusr1=False` flag exists).
- `src/zkm/sidecar.py:21-48` `merge_producer` does read → modify → atomic-write. The *atomic-write* step is process-safe; the read-modify-write *across* processes is not.
- Existing bypass pattern: `ZKM_BYPASS_DIRTY_CHECK=1` (per `project_dirty_check.md` memory).

## Agenda

1. Scope: which commands does the guard cover?
2. Refusal granularity: same-key duplicates and cross-key real-conflict combinations.
3. Implementation site: `RunSession.__enter__` precheck vs. CLI command boundary.
4. Race condition (TOCTOU between snapshot and PID-file write): fix or accept.
5. Bypass / override.
6. Stepping-stone framing: contract the v1 guard must preserve for the future daemon.

## Discussion

### Agenda 1 — Scope

🏗️ **Archie:** Dangerous combinations (named with file evidence): `convert × convert(same plugin)` (mbsync re-fire), `convert × index`, `convert × scrub`, `scrub × index`. Existing six unguarded store-mutating commands (`rm`/`gc`/`clone`/`push`/`pull`/`plugin add+remove`) have no concrete race evidence.

User clarified mid-discussion: the original concern was *parallel `git add` poisoning a commit*. That extended the candidate scope to "every command that touches git."

😈 **Riku:** Riku's checklist on the broader scope:
- Cross-pollination scenario: `convert(eml)` mid-`git add` × `zkm rm somefile.md` in another shell — what lands in the commit?

🏗️ **Archie (rebuttal mid-meeting after user follow-up):** Git's own `.git/index.lock` serialises `git add` / `git commit` operations. A second `git add` from a concurrent zkm command refuses with `Another git process seems to be running` rather than silently interleaving. The "commit poisoning" scenario is prevented by git itself. `zkm push` mid-commit transmits whatever's been committed — the in-progress commit is just not pushed yet; the next push picks it up.

😈 **Riku:** What this leaves: same-key duplicate refusal (`convert(eml) × convert(eml)`) plus cross-key *semantic* conflicts that git cannot detect — `convert × scrub` (frontmatter ↔ md rewrite race), and concurrent `merge_producer` calls against the same CAS sidecar.

**Decision 1 (user):** Three commands `convert`/`scrub`/`index` only. Push/pull/rm/gc/plugin-add/plugin-remove/clone stay unguarded — git's own lock plus their disjoint state-write paths cover the race classes. **Carry-forward watchpoint:** a `git add` blocked by an interleaving `git add` from another process leaves the second `add`+`commit` non-atomic; defer the deeper atomicity question to a future session.

### Agenda 2 — Refusal granularity

🏗️ **Archie:** Match key = `(command, args[0])`. Same-key collision → "duplicate" error; cross-key collision → "busy" error. Single `_take_status_snapshot(send_sigusr1=False)` call reads the state; one rule, two error templates.

😈 **Riku:** Same-key semantics question — user introduced it: should the second invocation **attach** (wait + run-myself, strongest hook contract) or **fail-fast** (exit code, hook scripts re-try) or **switchable** (env var)? `zkm status --wait` already provides manual wait; that's the existing lever.

✂️ **Petra:** N=2 on `--wait-for-busy` flag: only the mbsync hook is a concrete consumer today. Defer the flag.

**Decision 2a (user):** Fail-fast with distinct exit code (75 = `EX_TEMPFAIL`). Defer attach semantics until a "smart zkm queue manager" lands — that's a separate Phase 3 design.

🏗️ **Archie (cross-key sub-question, after sidecar verification):** Verified `src/zkm/sidecar.py:21-48` — `merge_producer` read-modify-write across processes is non-atomic. Two concurrent producers against the same sidecar lose one entry. Cross-plugin `convert × convert` (e.g. zkm-pdf consuming eml's PDF attachments — future case) hits this directly.

✂️ **Petra:** N=0 today (eml writes `mail/_objects/`, photo writes `photos/_objects/`; disjoint). N=∞ once cross-plugin amenders land.

**Decision 2b (user):** Broaden v1 guard cross-key scope to refuse *any* pairing of `convert`/`scrub` (so `convert × convert(any)`, `convert × scrub`, `scrub × scrub`). File a separate TODO entry to make `merge_producer` `fcntl`-locked.

**Forward-flag (user, captured to action items):** local DB with git-tracked autoexport-on-write as a possible architectural pivot away from sidecar files — worth future re-evaluation; complicates merging but eliminates this class of race.

### Agendas 3–6 — Implementation, race, bypass, daemon framing

🏗️ **Archie:** Implementation site (α) inside `RunSession.__enter__` extends the existing lever; (β) at the CLI command boundary repeats the call per command. Lever-first profile pattern favours (α). Raise a `ClickException` subclass with `exit_code=75`; click formats stderr automatically.

😈 **Riku:** TOCTOU on the read-snapshot → write-PID-file window — microseconds, but real. Mitigation options:
- (i) Accept; document; rely on future daemon to dissolve.
- (ii) `fcntl.flock` on `.zkm-state/.guard.lock` — kills race, ~10 LOC.
- (iii) Defer until daemon — but then no v1 ships.

Observe-before-preventing profile pattern (high confidence, pre-emption-eligible): user prefers to measure first. The guard itself IS the logger — a slipped-through double-run leaves two PID files with the same `(command, args[0])` in `running/`. Add a `zkm doctor` check for "concurrent same-key PID files detected" so a race firing is observable.

✂️ **Petra:** Bypass: `ZKM_BYPASS_RUN_GUARD=1` env var, symmetric with the existing `ZKM_BYPASS_DIRTY_CHECK=1`. N=1.5; cheap; ship for consistency.

🏗️ **Archie:** Daemon stepping-stone contract — v1's commitments that any successor must preserve:
- PID-file path + JSON schema at `.zkm-state/running/<pid>.json`.
- Exit code 75 on conflict (universal-Unix `EX_TEMPFAIL`).
- Conflict key = `(command, args[0])`.
- Fail-fast default (queueing / attach modes are additive flags, not breaking changes).

**Decision 3–6 (user):** Ship as proposed. If the TOCTOU race ever fires in real use, fix via `fcntl.flock` adapted from `~/.claude/skills/git-diary-workflow/git-lock-push.sh` (which already implements the exact pattern with a 30 s timeout).

## Decisions

- **Guard scope:** `convert`, `scrub`, `index` only. Other store-mutating commands (`rm`/`gc`/`clone`/`push`/`pull`/`plugin add+remove`/`init`) explicitly out of scope — git's own `.git/index.lock` plus their disjoint state-write paths cover the realistic race classes.
- **Match key:** `(command, args[0])` from the existing PID-file JSON schema.
- **Conflict matrix (v1):**
  - Same-key match → refuse (`duplicate` error template).
  - Cross-key within `{convert, scrub}` → refuse (`busy / would race on frontmatter or sidecar` error template). Sidecar atomicity in `merge_producer` is the motivating concern.
  - All other cross-key combinations (`convert × index`, `scrub × index`, `index × index`) → refuse only for *same-key* (i.e. `index × index`); `convert × index` and `scrub × index` proceed. Rationale: index reads only; partial state at worst causes a re-run on the next mbsync hook, not corruption.
- **Same-key semantics:** fail-fast with exit code 75 (`EX_TEMPFAIL`). Attach semantics (`--wait-for-busy`) deferred until a smart queue manager / daemon design lands.
- **Implementation site:** precheck inside `RunSession.__enter__`. Raise a `ClickException` subclass (`ConcurrentRunError`) with `exit_code=75`. Conflict-matrix logic lives in `runstate.py` as a small function importable by future daemon code.
- **TOCTOU:** accepted as best-effort guard for v1. Observability via a new `zkm doctor` check that flags multiple live PID files sharing a `(command, args[0])` key. If a race ever fires in real use, fix via `fcntl.flock` adapted from `~/.claude/skills/git-diary-workflow/git-lock-push.sh`.
- **Bypass:** `ZKM_BYPASS_RUN_GUARD=1` env var, symmetric with `ZKM_BYPASS_DIRTY_CHECK=1`.
- **Daemon-contract floor (preserved by any successor):** PID-file path/schema, exit code 75, conflict key `(command, args[0])`, fail-fast default. Queueing / attach are additive, not breaking.

**Explicitly out of scope:**
- Wrapping `rm`/`gc`/`clone`/`push`/`pull`/`plugin add+remove`/`init` in `RunSession` — git's own lock + disjoint state paths.
- `--wait-for-busy` flag (deferred to queue-manager session).
- `fcntl.flock` on `.zkm-state/.guard.lock` — accepted TOCTOU until observed.
- Fixing `merge_producer` cross-process race — separate session (tracked below).
- Architectural pivot to local-DB-with-git-autoexport — future re-evaluation (tracked below).
- Deeper `git add` interleaving atomicity (the "commit poisoning" carry-forward) — future session if observed.

## Action items

- [ ] `src/zkm/runstate.py` — add `ConcurrentRunError(ClickException)` with `exit_code=75`; add `_conflicts_with(other_row: dict) -> bool` helper containing the conflict matrix (same-key always; `{convert, scrub}` cross-key); precheck in `RunSession.__enter__` calling `_take_status_snapshot(..., send_sigusr1=False)` before writing the PID file. Contract: `with RunSession(store, "convert", args=["eml"])` raises `ConcurrentRunError` if `_take_status_snapshot` returns any row whose `(command, args[0])` matches OR whose `command` is in `{convert, scrub}` while self is in `{convert, scrub}`. Bypass via `os.environ.get("ZKM_BYPASS_RUN_GUARD") == "1"`.
- [ ] `src/zkm/cli.py:_take_status_snapshot` — already accepts `send_sigusr1=False`. Add a sibling helper `_count_concurrent_keys(rows)` returning a dict `{(command, args[0]): count}` for `zkm doctor` to consume.
- [ ] `src/zkm/cli.py:cmd_doctor` — new check: scan `.zkm-state/running/` for live same-key duplicates; print `concurrent runs: …` line with `(stale: N race-survivor pids)` annotation when count > 1 per key. Race-observability hook.
- [ ] Tests in `tests/test_runstate.py` — (a) same-key collision raises ConcurrentRunError exit 75; (b) cross-key `{convert, scrub}` raises; (c) `convert × index` allowed; (d) `ZKM_BYPASS_RUN_GUARD=1` bypasses; (e) stale PID file (process dead) doesn't trigger refusal — `_take_status_snapshot` already cleans those; (f) error message includes other pid + started time.
- [ ] `docs/install.md` (or a new `docs/concurrent-runs.md`) — document the guard, the env var bypass, the exit-75 convention, and the mbsync-hook implication (`zkm convert eml || true` if you want to silence the EX_TEMPFAIL in the hook; or use `zkm status --wait; zkm convert eml`).
- [ ] `CLAUDE.md` — one-line pointer to the doc + the `ZKM_BYPASS_RUN_GUARD` env var alongside the existing `ZKM_BYPASS_DIRTY_CHECK` mention.
- [ ] `TODO.md` — mark this item closed once shipped; cross-link to this meeting note.

**Spawned follow-up items (NEW TODO entries to file):**

- [ ] **Sidecar atomicity: file-lock `merge_producer`** — `fcntl.flock` around the read-modify-write window in `src/zkm/sidecar.py:21-48`. Eliminates the cross-process producer-loss race verified during this meeting. Once shipped, the `convert × convert(different plugin)` refusal in this v1 guard could be narrowed back to `convert × scrub` only — but probably keep the broader guard (one line, cheap insurance). Reference flock implementation: `~/.claude/skills/git-diary-workflow/git-lock-push.sh`.
- [ ] **Future re-evaluation trigger — local DB with git-tracked autoexport-on-write** — alternative to the current sidecar-files-on-disk model. Eliminates concurrent-write races entirely (DB ACID) but complicates merging across remotes (export-on-write is essentially a second write path; conflict resolution becomes harder). Re-open: if (a) concurrent-write bugs in sidecars become frequent, OR (b) the WebUI's read-write workload makes file-level locking visibly painful, OR (c) cross-machine sync stops being purely "git pull"-based.
- [ ] **`zkm queue` design meeting (Phase 3 daemon precursor)** — when attach semantics become a real ask (N=2 consumers wanting `--wait-for-busy`), open a meeting on a queue manager: PID-file → in-memory daemon queue, fail-fast → attach/wait/wait-rerun modes, status polling → WebSocket push (Phase 3 WebUI alignment). v1 contract (this meeting) is the floor that meeting must preserve.
- [ ] **Carry-forward watchpoint — `git add` interleaving atomicity** — investigate whether git's `.git/index.lock` retry semantics could leave one zkm command's `git add` blocked by another's mid-`add`, producing a non-atomic stage+commit. Action: instrument the auto-trigger hook to log a journald event when `git add` returns a lock-contention error; review evidence after 4 weeks. No code change today.
