# 2026-06-10 — Default-mode dispatch: 4 C1 items via parallel agents

**Started:** 2026-06-10 20:24
**Session:** 56c51583-29b1-4761-916e-fd3e92bf4453
**Mode:** Class 1 dispatch (no meeting held — all items impl-ready)
**Topic:** Default /meeting audit dispatched 4 C1 items (E9 probe, SOC1–3) to parallel Sonnet agents via workflow.

## Context

No-arg /meeting invocation. TODO audit classified:
- **C1 (impl-ready, non-deferred):** E9 follow-up `e4fe`, SOC1 `56ac`, SOC2 `017f`, SOC3 `7f55`
- C2/C3 items not dispatched this session.

User elected: "Do all four C1 tasks via parallel Sonnet agents using the dotclaudeskill discussed parallel worktree approach."

## Plan

4-agent workflow (`zkm-c1-parallel`):
- **Phase 1 (parallel):** E9 synthetic-store probe + SOC1 skeleton
- **Phase 2 (parallel after SOC1):** SOC2 GitHub parser + SOC3 LinkedIn parser
- **Phase 3:** Full test suite + TODO.md update

## Implementation findings

### E9 — IBAN search probe (PASS, synthetic store)
- Real store BM25 index has a watermark mismatch (EOFError on load; HEAD cc3a2e1 ≠ index watermark d54713). Needs `zkm index` re-run.
- Synthetic store at `/tmp/zkm-e9-probe/` created: one `.md` with IBAN `CH93 0076 2011 6238 5295 7` in `entities[]`.
- `zkm search "CH93 0076 2011 6238 5295 7"` returned the test document. **PASS.**
- Note: full corpus re-extract (`zkm convert ner`) deferred to a scheduled job; real-store index re-run also needed.

### SOC1 — zkm-social skeleton
Plugin created at `plugins/zkm-social/` (own git repo, gitignored by parent). Files:
`plugin.yaml`, `convert.py` (dispatch), `_github.py` (stub), `_linkedin.py` (stub),
`pyproject.toml`, `uv.lock`, `README.md`, `LICENSE`, `CLAUDE.md`, `tests/test_convert.py`, fixture dirs.

### SOC2 — GitHub parser (11 tests pass)
`_github.py` implements `convert_github()`: public API fetch, avatar → CAS, entities at `scope:profile.github`, idempotent on profile URL sha256.

### SOC3 — LinkedIn parser (24 tests pass)
`_linkedin.py` implements `convert_linkedin()`: scans source_dir for `.html`/`.mhtml`/`.htm`, BeautifulSoup4 extraction, photo → CAS, entities at `scope:profile.linkedin`, idempotent.

### Post-workflow fixes
Pyright diagnostics fixed (commit `f9f4f68`):
- `sys` unused in `convert.py`; `Path` unused in `test_convert.py` — removed
- `_github.py`: `_avatar_ext()` function unused (removed), `cas_path` unused → `write_object(...)` bare call
- `_linkedin.py`: `part.get_param("charset")` returns `_ParamType` → replaced with `part.get_content_charset("utf-8")`; `img.get("class", [])` type → `isinstance(raw_classes, list)` guard
- `convert.py` sibling imports → `# type: ignore[import]` (dynamic sys.path; expected pattern)
- `pyrightconfig.json` added pointing to `.venv`

**Final test count:** 45 passing, 0 failing.

## Decisions

- **D1:** E9 contract verified via synthetic store. Full corpus re-extract + real-store index re-run are separate deferred jobs.
- **D2:** zkm-social plugin is a standalone git repo at `plugins/zkm-social/`. Flat layout (`_github.py`, `_linkedin.py` alongside `convert.py`) with Pyright config.
- **D3:** `_avatar_ext()` helper removed (CAS is content-addressed, extension not needed for storage).

## Action items

- [ ] Re-run `zkm index` on real store to fix BM25 watermark mismatch. <!-- id:d45a -->
