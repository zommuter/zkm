# 2026-05-08 — Encoding audit + normalization (zkm-eml)

**Started:** 2026-05-08 21:01
**Session:** d7a22d0e-3009-4313-abd3-494135764455
**Attendees:** Archie (architect), Riku (devil's advocate), Petra (productivity)
**Topic:** Audit zkm-eml decode paths; add charset detection + mojibake repair; full store reprocess.

## Agenda

1. Classify unchecked TODOs → encoding audit selected (Class 2 — planning-worthy).
2. Design decode approach: charset-normalizer (detection) + ftfy (mojibake repair).
3. Implement parse.py refactor, new test fixtures, plugin-spec doc update.
4. Live reprocess on ~/knowledge.

## Discussion

### TODO classification

Three unchecked non-date-triggered items:
- **Class 2 (planning-worthy)**: Text file encoding issues — investigation + design shape, no ambiguous scope.
- **Class 3 (meeting-worthy)**: Session 15 (whatsapp scoping), zkm-claude-code, zkm-claude-ai.

Head pick: encoding audit (Class 2). Dispatched to EnterPlanMode / explore → design → implement flow (no persona scaffolding for Class 2).

### Design decisions

**Dep scope**: Both `charset-normalizer` (detection on decode failure) and `ftfy` (mojibake repair) chosen over stdlib-only or single-lib approach.

**Live probe scope**: Full `--reprocess-all` chosen (vs. synthetic fixtures only), to fix all historical mojibake in the store in one pass.

### Implementation findings

`_decode_part()` in `parse.py:246-264` had a quiet failure mode: fallback chain `declared → utf-8 → cp1252 → latin-1`. Because cp1252 and latin-1 never raise `UnicodeDecodeError`, a mis-declared utf-8 payload silently landed as mojibake.

Revised three-tier logic:
1. `_try_strict_decode()` — if declared is permissive (latin-1/cp1252): try utf-8 first, then trust the declaration. If declared is strict (utf-8, us-ascii): try it; if fail, stop. Always append utf-8 as final strict fallback.
2. `_detect_decode()` — charset-normalizer `from_bytes().best()` when strict candidates fail.
3. Last resort: utf-8 with `errors="replace"`.
4. `_post_decode()` — strip BOM + ftfy.fix_text (encoding-only mode) + NFC normalize; shared by body and header paths.

### Plugin dep loading issue

When `zkm convert` loads a plugin via `importlib.util.spec_from_file_location`, it runs in the main zkm venv — plugin-specific deps (ftfy) are not available. Workaround: `convert.py` injects `.venv/lib/python*/site-packages` into `sys.path` at import time. Flagged in TODO as a proper design question.

Also discovered: `uv.sources` path `../zkm` is wrong for all plugins after the repo reorg (now live at `plugins/zkm-*/`, not `~/src/zkm-*/`). Fixed for zkm-eml (`../../`); other plugins need the same.

### Test results

- 21 zkm-eml tests passing (15 existing + 6 new encoding fixtures).
- 315 core zkm tests passing (no regression).

### Live probe

29 mojibake-affected messages found in ~/knowledge/mail/messages/ before reprocess. Full `--reprocess-all` run started but interrupted by user before completion.

## Decisions

- `charset-normalizer>=3.3` and `ftfy>=6.2` added to `plugins/zkm-eml/pyproject.toml` dependencies.
- `_try_strict_decode` skips permissive codecs from the auto-fallback tier, but trusts them when explicitly declared (tries utf-8 first for permissive-declared, then falls back to the declaration).
- Plugin dep loading workaround: sys.path injection in `convert.py`. Proper solution deferred to scoping meeting.
- `uv.sources` path fixed for zkm-eml; other plugins tracked in TODO.
- Plugin-spec.md updated with one-paragraph encoding contract.

## Action items

- [x] `plugins/zkm-eml/src/zkm_eml/parse.py` — refactor `_decode_part`, `_decode_header_str`; add `_try_strict_decode`, `_detect_decode`, `_post_decode` helpers.
- [x] `plugins/zkm-eml/pyproject.toml` — add charset-normalizer + ftfy; fix uv.sources path; bump requires-python to >=3.14.
- [x] `plugins/zkm-eml/convert.py` — inject plugin venv site-packages into sys.path.
- [x] 6 new fixture `.eml` files + 6 new tests in `test_parse.py`.
- [x] `docs/plugin-spec.md` — encoding contract paragraph.
- [x] `TODO.md` — plugin dep loading + broken uv.sources paths for other plugins.
- [ ] Full `--reprocess-all` on ~/knowledge + `zkm index` refresh — pending (interrupted).
- [ ] Fix `uv.sources` in zkm-pdf, zkm-photo, zkm-scan, zkm-notmuch (same `../../` fix).
