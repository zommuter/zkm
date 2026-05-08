# 2026-05-08 — mbsync auto-trigger for zkm-eml

**Attendees:** Tobias (product owner), Archie (architect), Riku (devil's advocate), Petra (productivity)
**Topic:** Decide how a successful mbsync sync auto-runs `zkm convert zkm-eml` (and what, if anything, runs after).

## Context

`~/mail/` is a git repo populated by mbsync (read-only IMAP pull). `zkm-eml` already has a git-commit watermark (`<store>/.zkm-state/zkm-eml.json` per source repo, see `plugins/zkm-eml/src/zkm_eml/state.py`) and a fast-path enumerator `iter_messages_since(...)` (used in `plugins/zkm-eml/convert.py:62`). So the conversion path is incremental and idempotent. The missing piece was the trigger — currently manual.

## Past-meetings audit

All five prior meeting outcomes are tracked in `TODO.md`. No orphans.

## Agenda

1. Where does the auto-trigger live?
2. Failure semantics — what does Tobias see when conversion fails?
3. Concurrency — what if mbsync fires again while convert is still running?
4. Auto-chain scope — convert only, or also `zkm index` and embed?
5. Out-of-scope confirmation.

## Discussion

### Item 1 — Trigger placement

**Archie:** Three homes: (A) git post-commit hook in `~/mail/.git/hooks/`, (B) systemd unit chained off the mbsync timer, (C) wrapper script around mbsync. Conversion path is already incremental — the trigger just needs to fire when `~/mail/` advances.

**Riku:** Hook in `~/mail/.git/hooks/` is not version-controlled — gone on a rebuild. Must live in a tracked location and be symlinked in.

**Archie:** Precedent: `~/.mbsyncrc` is installed via `make install-mail`. Same pattern works here — script at `plugins/zkm-eml/hooks/post-commit`, symlinked into `~/mail/.git/hooks/post-commit`.

**Petra:** Out of scope — mbsync invocation, cron-poll mode.

**Decision:** Git post-commit hook, tracked source + symlinked install.

### Item 1a — `zkm` on PATH

**Tobias:** The hook should call `zkm convert zkm-eml`, not `uv run zkm …`. Add `zkm` to PATH.

**Archie:** `uv tool install --editable ~/src/zkm`. Drops a `zkm` shim in `~/.local/bin/`, source changes stay live, `uv tool update-shell` handles PATH.

**Riku:** Editable install means the hook runs against the *current* working tree — opens a WIP/corruption risk (escalated below).

### Item 1b — N=2 check (Syncthing → zkm-photo)

**Tobias:** Plan similar automation on Syncthing-synced photo paths.

**Petra:** Mechanically different — Syncthing writes files continuously, no commit boundary. Right trigger there is a systemd `.path` unit watching the directory (debounced). N=1 for the post-commit hook design.

**Archie:** What *is* shared between any future trigger and this one: both call `zkm convert <plugin>`. The single-instance concern lives in core, not in either trigger script.

### Item 2 — Failure surface

**Archie:** Hook pipes through `systemd-cat -t zkm-eml-hook` and exits 0 regardless of zkm exit. Failures queryable via `journalctl -t zkm-eml-hook -n 50`.

**Riku:** Per "observe before preventing" — log first, layer in desktop notifications later if log-noise turns out to be invisible.

**Petra:** Note: a post-commit hook returning non-zero does NOT roll back the commit — it only prints a warning. So "block the commit on convert failure" is a misnomer; drop that option.

**Decision:** journald only.

### Item 2a — Don't run WIP code via auto-trigger (escalation)

**Tobias:** Editable install + auto-trigger could run a half-broken zkm during a refactor and corrupt the knowledge store. "Observe before preventing" applies to lock files; data corruption is a different category.

**Riku (corruption surface):**
- atomic writes already in place (`zkm.atomic.write_atomic`)
- watermark only advances on success (`plugins/zkm-eml/convert.py:198`)
- `originals/mail/` is the data of record; `convert.py:204 reprocess()` regenerates the .md tree
- store is a git repo — every convert auto-commits, `git revert` is the rollback path

Real residual risk: a logic bug in originals/CAS or a watermark mis-advance silently skipping mail.

**Tobias's design:** Push the dirty-tree check into `zkm` itself, not into the hook. Default ON (check runs); bypass via `ZKM_BYPASS_DIRTY_CHECK=1` env var (tests, deliberate dev runs). Never set in `.zshrc`.

**Riku (initial framing pushback):** I had originally framed this as "default off, opt in via flag" — Tobias correctly inverted. Default-ON expresses the right policy: any zkm invocation on a dirty tree refuses; bypass is the explicit exception. Default-OFF would have been backwards.

**Archie (implementation):**
- At the top of state-modifying subcommands (`convert`, `index`, `rm`, `gc`), run a dirty-tree check.
- Read commands (`search`, `query`, `doctor`, `plugin list`) unaffected.
- `Path(zkm.__file__)` → walk up to `.git/`. Non-editable installs (`uv tool install` without `--editable`) have no `.git/` ancestor and the check no-ops (binary is frozen at install time).
- Primitive: `git diff-index --quiet HEAD -- <paths>` (untracked files don't count; local-but-unpushed commits don't count).
- Scope: `src/zkm/` + `plugins/<invoked-plugin>/`. Editing zkm-photo doesn't gate a zkm-eml convert.

**Petra (N=2 sanity):** This is a single guard in `zkm.cli` protecting all state-modifying commands — not an abstraction with multiple call sites. N=2 is satisfied at the trigger level (eml hook today, photo trigger tomorrow), not the implementation level.

**Decision:** `ZKM_BYPASS_DIRTY_CHECK=1`-style guard in `zkm.cli`. Default ON. Scope: core + invoked plugin. Hook calls plain `zkm convert zkm-eml` and inherits the protection.

### Item 3 — Concurrency

**Petra:** "Observe before preventing." mbsync cadence ≥ 5 min, steady-state convert is fast via watermark. Zero evidence of overlap.

**Archie:** Even if two runs interleave: watermark advances only on success, atomic writes prevent partial md, message_id dedup catches in-flight duplicates. Worst case: duplicated work, not corruption.

**Riku:** journald captures timing if overlap happens.

**Decision:** Defer. No lock today. Revisit from journald evidence over 2–4 weeks.

### Item 4 — Auto-chain scope

**Archie:** `zkm index` is incremental (watermark at `<store>/.zkm-index/last-commit`); cheap to chain. Embed couples to a dense-endpoint, slower, doesn't belong in the post-commit path.

**Decision:** Hook runs `zkm convert zkm-eml && zkm index`. Embed and `zkm doctor` move to a separate systemd timer (own session).

### Item 5 — Out of scope

How mbsync is invoked; cron-poll mode for non-git source trees (Syncthing → zkm-photo); multi-store orchestration; a `zkm sync` meta-command (YAGNI; revisit at N=3).

## Decisions

1. **Trigger** lives in `~/mail/.git/hooks/post-commit`, symlinked from `~/src/zkm/plugins/zkm-eml/hooks/post-commit`.
2. **`zkm` on PATH** via `uv tool install --editable ~/src/zkm`. Hook calls plain `zkm`.
3. **Failure surface:** `systemd-cat -t zkm-eml-hook`. Hook exits 0 unconditionally.
4. **In-binary dirty-tree guard** for state-modifying commands. Bypass via `ZKM_BYPASS_DIRTY_CHECK=1`. Scope: `src/zkm/` + `plugins/<invoked-plugin>/`. Read commands unaffected. Non-editable installs no-op the check.
5. **Concurrency lock:** deferred; observe via journald.
6. **Chain:** `zkm convert zkm-eml && zkm index`. Embed + doctor on a separate timer.

Out of scope: mbsync invocation, cron-poll, multi-store orchestration, `zkm sync` meta-command.

## Action items

- [ ] **A1.** `src/zkm/cli.py` (or new `src/zkm/devcheck.py`): `ZKM_BYPASS_DIRTY_CHECK` guard on `convert`, `index`, `rm`, `gc`. Contract: dirty `src/zkm/` blocks all four; dirty `plugins/zkm-eml/` blocks only `convert zkm-eml`; non-editable install no-ops; bypass env disables. Tests in `tests/test_devcheck.py`.
- [ ] **A2.** Document `uv tool install --editable ~/src/zkm` in setup notes; verify `which zkm` resolves to `~/.local/bin/zkm`.
- [ ] **A3.** Create `plugins/zkm-eml/hooks/post-commit` (executable). Body: pipe stdout+stderr through `systemd-cat -t zkm-eml-hook`, run `zkm convert zkm-eml && zkm index`, exit 0. Add an `install-hook` target or doc snippet that symlinks into `~/mail/.git/hooks/post-commit`.
- [ ] **A4.** Update `TODO.md`: replace the "mbsync post-commit hook" line with a sub-checklist for A1–A3, plus a "from 2026-06-05: evaluate need for convert lock from journald" follow-up.
- [ ] **A5.** Deferred: separate systemd timer for `zkm embed` + `zkm doctor`. File as a future TODO entry.

## Verification (for A1–A3)

- `uv run pytest tests/test_devcheck.py` passes (dirty/clean/bypass/non-editable matrix).
- `git -C ~/src/zkm` clean → `zkm convert zkm-eml` runs normally; modify a tracked file in `src/zkm/` → `zkm convert zkm-eml` refuses with a clear error pointing at the dirty paths.
- After install: `git -C ~/mail commit --allow-empty -m "test"` triggers the hook; `journalctl -t zkm-eml-hook -n 20` shows the run output.
- mbsync sync that produces 1 new message → md appears in `~/knowledge/mail/messages/...`, BM25 index reflects it, and `zkm search` finds it without manual `zkm index`.
