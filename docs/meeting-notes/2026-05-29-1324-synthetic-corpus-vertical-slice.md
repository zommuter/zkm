# 2026-05-29 — Synthetic corpus vertical slice implementation

**Started:** 2026-05-29 13:24
**Session:** fd7c31f4-0e7b-466f-90f3-7254c09d84ec
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Implement the four vertical-slice items from the synthetic test corpus design (see 2026-05-29-1112-synthetic-test-corpus.md)

## Context

The synthetic-corpus design meeting (2026-05-29 11:12) ratified all decisions. This session is the implementation of the vertical slice: generator + roundtrip test + committed corpus + conftest centralization. Rationale for the slice choice: build the generator AND both its consumers ([fc87] roundtrip, [ba5e] corpus) so nothing is left dangling, plus [590b] conftest which is independent.

Items deferred to next tranche: [0af9] seed_dev_store.py, [f918] pathological anchors, [c582] cross-repo regen doc.

## Plan

Explored: `plugins/zkm-eml/src/zkm_eml/frontmatter.py`, `parse.py`, existing `tests/test_convert.py`, core `tests/test_search.py` + `test_index.py`, `tests/conftest.py`. Key findings:
- `PLUGIN_VERSION = "0.11.0"` in frontmatter.py (distinct from pyproject.toml 0.12.0).
- `frontmatter.py:44` writes `subject`, never `title` — the drift trap to guard.
- `_write_note` + `store` fixture were byte-for-byte identical in test_search.py:15-27 and test_index.py:18-30.
- Parser falls back to `datetime.now()` if `Date:` header is missing (parse.py:150/157) — generator must always emit explicit `Date:`.
- `keep_originals=False` + `quote_strip=False` in convert config for clean test store.

## Implementation findings

All items implemented and verified:

**[9e0e] Generator** (`plugins/zkm-eml/scripts/generate_corpus.py`):
- 5 byte-stable `.eml` messages: standalone, 3-message thread chain, multi-recipient.
- CRLF line endings (consistent with `_DEL_EML_TMPL` pattern), explicit `Date:` and `Message-ID:` everywhere.
- Generates into `tests/fixtures/corpus/` by default; accepts optional `dest` arg.

**[fc87] Roundtrip test** (`plugins/zkm-eml/tests/test_corpus_roundtrip.py`):
- 4 tests: byte-stability (regenerate → diff), subject≠title on all 5 messages, full frontmatter schema per message, thread_id consistency across 3-message chain.
- All 4 pass.

**[ba5e] Committed corpus** (`tests/fixtures/corpus/`):
- 5 `.md` files under `mail/messages/2026/04/`.
- `CORPUS_MANIFEST.json` with `processor_version`, generator path, and per-input sha256s.
- `tests/test_corpus.py`: 6 tests — manifest exists, 5 docs indexed, no `import zkm_eml`, body/participant search, `title` absent from all doc metadata.

**[590b] Conftest centralization** (`tests/conftest.py`):
- Added `store` fixture (init_store + none backend).
- Added `make_note` factory fixture bound to `store`.
- Removed `store` + `_write_note` from `test_search.py` and `test_index.py`.
- All call sites updated to `make_note(...)`.

## Decisions

- Generator emits CRLF (matches `_DEL_EML_TMPL` precedent); existing LF fixtures unaffected.
- Thread index files (`mail/threads/`) excluded from committed corpus — they are a side-effect of convert, not part of the faithful .md schema under test.
- `test_corpus_no_import_zkm_eml` asserts `"zkm_eml" not in sys.modules` at test time (no `corpus_store` fixture needed — the import check is independent of store state).

## Action items

All items implemented and closed in this session. No items to mirror to TODO.md.
