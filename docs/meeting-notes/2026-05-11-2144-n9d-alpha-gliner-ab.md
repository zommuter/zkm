# 2026-05-11 — N9d-α: GLiNER A/B results

**Started:** 2026-05-11 21:44
**Session:** 777fdc73-b118-4054-8f11-3adf55769a21
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Run GLiNER A/B smoke gate + Stage 2 to determine whether GLiNER moots N9f and is suitable as the default NER backend.

## Context

N9d-α was designed in 2026-05-11-1531-ner-tangible-results.md to answer: "would GLiNER reduce or eliminate the top-4 multi-word salutation FP strings (Hallo Tobias ×1930, Best Regards ×1139, Guten Tag Herr Kienzler ×444, Hello Tobias ×392)?" The comparison script (`scripts/gliner_ab.py`) and pre-flight tasks (N9d-α-1/2/3) were completed in the same session. N9f (salutation blocklist) was also implemented in that session as a "pre-design A" parallel track.

## Plan

1. Run 5-file smoke gate (one representative file per top-4 FP string + control).
2. If smoke passes (each FP dropped by GLiNER): run Stage 2 on larger targeted sample.
3. Check success bar: ≤10% retention of each top-4 FP string AND no new top-20 FP cluster introduced by GLiNER.

## Implementation findings

**Smoke gate (N9d-α-4):** Both backends emitted 0 FP hits for the salutation strings. However, N9f was already implemented before the gate ran — `drop_salutation_blocklist()` in `extract.py` applies to both `model="spacy"` and `model="gliner"`. The original question ("would GLiNER moot N9f?") is unanswerable from this test. Gate technically passes (0 FP hits from GLiNER).

**Stage 2 — mixed sample (25 files):**

- spaCy: 364 entities total / GLiNER: 261 entities total (−28%)
- Long German job-application emails: GLiNER gets 42–48% of spaCy's count
- Short transactional emails: GLiNER gets 80–94% of spaCy's count
- spaCy-only FPs: `usability`, `physicist`, `any`, `c`, `alm`, `mfc`, `de252066603`, `download patreon` — common nouns, abbreviations, garbled strings
- GLiNER-only finds: `jeph Jacques` ×3, `dr. robert grünwald` ×2, `amazon.com, inc.` ×2 — person titles and full org names
- GLiNER missed legit: `Visual Studio`, `Windows CE`, `Real Staffing Group`, `Frankfurt am Main`

Truncation warnings were frequent: GLiNER model truncates input at 384 tokens (~2800 chars). Long emails had content in the second half silently ignored.

**Short-email-only run (30 files, <3KB body):**

- spaCy: 143 entities / GLiNER: 164 entities (**+14%**)
- Both backends have comparable FP rates; GLiNER introduces different FP types: `zommuter` as PERSON ×9, `ihr kind` ×1, `pädagogischer mitarbeiter` ×1, `eltern` ×1, crypto wallet addresses ×4
- spaCy-only FPs: `wei` ×4, `tweets`, `glad`, `image004.jpg@...`, `token symbol` — different types, similar count

**Critical finding:** On short emails (no truncation), GLiNER finds +14% MORE entities than spaCy. The apparent 28% reduction in the mixed-sample run was almost entirely truncation-related noise, not genuine precision improvement.

## Decisions

- **N9d-α verdict: FAIL.** GLiNER (`urchade/gliner_multi-v2.1`) is not suitable as the default backend for a mixed-length email store.
- Root cause: 384-token hard truncation causes systematic recall loss on long emails, and GLiNER has no meaningful precision advantage on short emails.
- **N9f stays** as the correct deterministic floor for multi-word salutation FPs.
- **Truncation note added** to `plugin.yaml` (ZKM_NER_MODEL description) and `gliner_backend.py` docstring, so future evaluators know the constraint without re-running this test.
- **Deferred:** GLiNER with sliding-window chunking — revisit if `urchade/gliner_multi-v2.1` or a successor gains long-document support. Not tracked as an active TODO; raise explicitly if needed.

## Action items

- [x] Add truncation note to `plugins/zkm-ner/plugin.yaml` ZKM_NER_MODEL config description — 2026-05-11
- [x] Add truncation note + A/B findings to `plugins/zkm-ner/src/zkm_ner/gliner_backend.py` module docstring — 2026-05-11
- [x] Mark N9d-α-4 and N9d-α-5 done in TODO.md with findings summary — 2026-05-11
- [x] Add this planning record to meeting-style.md past-meetings index — 2026-05-11
