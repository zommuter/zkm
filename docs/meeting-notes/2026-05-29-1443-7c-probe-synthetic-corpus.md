# 2026-05-29 — First 7c typed-value probe on synthetic corpus

**Started:** 2026-05-29 14:43
**Session:** eca316ad-1d03-49aa-a940-ec62b8079caa
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Decouple the E9/7c entity-search probe from the production embed rebuild by validating it first on the synthetic corpus.

## Context

TODO `[2c6e]` required running the field-test 7c typed-value probe after the production embed rebuild completes (~4.5h ETA at time of session). User redirected: run a first 7c probe now against the synthetic corpus to validate the procedure. The production rebuild (PID 189608) continues independently.

**Stale-premise correction (load-bearing):** The memory entry `[2026-05-12 zkm]` in `discoveries.md` stating "BM25 ignores `entities[]`" was **outdated**. Since commit `e56dd55` (E8), `index.py:68-74` and `embed.py:484-492` index `entities[].value` and `.canonical`. The 7c probe is therefore an **E8 regression verification**, not a known-gap probe.

**Corpus gap:** No IBAN fixture existed; `CHF 1250` was present in one body but amounts-in-body don't isolate the entity-index path.

## Plan

Decisive test: add `corpus_iban_invoice.eml` with **spaced** IBAN `DE44 5001 0517 5407 3249 31` in body. The compact canonical `DE44500105175407324931` is absent from body. Searching the compact canonical via BM25 can only match via `entities[].canonical` (`index.py:73-74`) — never via body text.

Approach:
1. `plugins/zkm-eml/scripts/generate_corpus.py` — add 6th `MESSAGES` entry (byte-stable, deterministic).
2. Regen `.eml` fixture at `plugins/zkm-eml/tests/fixtures/corpus/corpus_iban_invoice.eml`.
3. Convert via Python API directly (not `zkm convert eml` CLI — EML_SOURCE_DIR is a config key post-M2, not env var).
4. Run `zkm convert ner` from `plugins/zkm-ner` venv (core venv has numpy conflict on Python 3.14).
5. Copy only `.md` files (no `.amendments.json`) to `tests/fixtures/corpus/mail/messages/`.
6. Update `CORPUS_MANIFEST.json` (6 inputs) and README regen procedure.
7. Update `test_corpus_roundtrip.py` (count 5→6, new IBAN assertions).
8. Update `tests/test_corpus.py` (count 5→6).
9. Write `tests/test_entity_search.py` with 4 probe tests.

## Implementation findings

All steps completed. Key discoveries:

- **Python 3.14 / numpy conflict:** `uv run zkm convert ner` fails with `No module named 'numpy._core._multiarray_umath'` in the core (Python 3.14) venv; workaround: call `convert()` directly from `plugins/zkm-ner` venv (which runs Python 3.12 and has working numpy). Documented in regen README.
- **EML_SOURCE_DIR is a config key, not env var (post-M2):** `zkm convert eml` CLI reads `source_dir` from `zkm-config.yaml` only; env override doesn't work. Must use Python API with explicit `source_dir` arg.
- **zsh `cp` alias:** zsh aliases `cp` interactively; use `command cp` to bypass.
- **Entity extraction result:** NER produced `{type:iban, canonical:DE44500105175407324931, valid:true}` + `{type:amount, unit:CHF}` in the IBAN invoice, plus several false positives (BIC as amount, "Bank:" as org) — harmless for the probe.

## Decisions

- Commit `entities[]` in the corpus `.md` files (pre-baked from NER regen). Core tests have **zero** live `zkm_ner` dependency.
- Regen now requires a NER step from `plugins/zkm-ner` venv; documented in `README.md`.
- **Does NOT close E9** — production store probe (`zkm doctor` embed docs == md count) remains open as `[2c6e]`. TODO updated with "Probe procedure VALIDATED 2026-05-29" note.

## Action items

- [x] `corpus_iban_invoice.eml` added; roundtrip test updated (4/4 pass in zkm-eml)
- [x] `tests/test_entity_search.py` written; 4/4 pass in core; total 475 pass
- [x] `docs/field-test-bge-m3.md` step 7c recorded
- [x] `project_synthetic_corpus` memory updated
- [ ] Production 7c probe: run `zkm search "DE44500105175407324931" --no-dense` against real store once embed rebuild completes (`zkm doctor` embed docs == md count). Close `[2c6e]`. <!-- id:c18c -->
- [ ] Correct stale `discoveries.md` entry: "[2026-05-12 zkm] BM25 ignores entities[]" — add correction that E8 (commit `e56dd55`) added entity+participant indexing. <!-- id:0c63 -->
