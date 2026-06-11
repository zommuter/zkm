# 2026-06-11 — W9: WAL-safe read + incremental backup design note (zkm-whatsapp)

**Started:** 2026-06-11 10:33
**Session:** 5db9f883-e452-4ae5-af33-43c5f21013bc
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Make zkm-whatsapp's convert() safe against WAL-mode msgstore.db; design historical-backup ingest path.

## Context

`plugins/zkm-whatsapp/convert.py:241` opened the source db with a plain `sqlite3.connect(source_db)`.
A live WhatsApp `msgstore.db` runs in WAL journal mode; committed frames can sit in a sibling
`<db>-wal` file that has not yet been checkpointed. Reads without handling the WAL could return
stale data (missing the newest messages). TODO item W9 (no id minted — in-session resolution).

Constraint: zkm-whatsapp is documented as **ingest-only / never mutate source** (`CLAUDE.md`).
A naive `wal_checkpoint(PASSIVE)` on the source would write to the user's file.

## Plan

**WAL strategy (confirmed: copy-trio-to-temp):**
- `_wal_safe_source(source_db)` helper: if sibling `-wal` is non-empty, copy `db + -wal + -shm`
  to a tempdir, run `PRAGMA wal_checkpoint(TRUNCATE)` on the copy, return copy path + tmpdir.
- Fast path: no `-wal` or empty `-wal` → return original path, `tmpdir=None`.
- `convert()` wraps the connection in `try/finally` → `shutil.rmtree(tmpdir)` on exit.
- State/watermark key remains the **original** `source_db` path — `state.py` unchanged.

**Historical backups (design note only, decided in planning):**
- Multi-source ingest is structurally safe: dedup on `key_id`, watermark per source path.
- Deferred until concrete need (e.g. gap after phone wipe). See `CLAUDE.md` design note.

## Implementation findings

- `PRAGMA wal_checkpoint(TRUNCATE)` on a fresh copy reliably folds all committed WAL frames.
- `wal_autocheckpoint=0` + reader snapshot pattern reliably leaves frames in `-wal` for tests
  on most SQLite builds; test skips gracefully if SQLite checkpoints on close.
- `pytest -q`: 23 pass, 1 skip (skip = SQLite auto-checkpointed, not a code defect).
- New tests: `test_wal_safe_source_no_wal`, `test_wal_safe_source_empty_wal`,
  `test_wal_safe_source_with_wal`, `test_convert_wal_frames_visible`.

## Decisions

- **Source never mutated**: copy-trio-to-temp is the WAL strategy; any checkpoint is on the copy only.
- **Historical backup ingest**: design note only; no new config option in v1.
- **Version**: 0.2.0 → 0.3.0 (minor per loose-0.x: behaviour change).
- **Remote**: bare repo created at `fievel:src/zkm-plugins/zkm-whatsapp.git`, pushed with `--tags`.

## Action items

- [x] Implement `_wal_safe_source` + wire into `convert()` — `plugins/zkm-whatsapp/convert.py`
- [x] Add W9 design note to `plugins/zkm-whatsapp/CLAUDE.md`
- [x] Add WAL tests to `plugins/zkm-whatsapp/tests/test_convert.py`
- [x] Bump version 0.2.0 → 0.3.0 across `convert.py`, `pyproject.toml`, `plugin.yaml`
- [x] Create `fievel:src/zkm-plugins/zkm-whatsapp.git` and push `v0.3.0` tag
- [x] Mark W9 `[x]` in `TODO.md`
