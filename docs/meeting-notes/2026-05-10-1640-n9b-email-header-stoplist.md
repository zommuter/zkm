# 2026-05-10 — N9b email-header stoplist

**Started:** 2026-05-10 16:40
**Session:** caee33d8-2e32-497d-bf8a-525b03dd710b
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), Zommuter (user)
**Topic:** How to clean email-header / markdown-syntax pollution from spaCy NER output before pilot window closes 2026-06-05.

## Agenda

1. Full set of leak vectors from pilot data.
2. Fix layer: pre-strip vs. stoplist vs. both.
3. Stoplist content + matching rules.
4. Placement (resolved within item 2).
5. Pilot integration + cache invalidation.

## Discussion summary

Pilot review file (`<store>/.zkm-state/ner-pilot-review.jsonl`, 138 548 flagged rows) showed 4 distinct pollution classes, broader than the original TODO description:

| Class | Examples | Count (top entry) |
|-------|----------|-------------------|
| 1 — Markdown syntax fragments | `\|`, `\|---\|`, `\| \|`, `ready](` | >12 000 total |
| 2 — Header column names | From=8959, Subject, Date, Thread, To | 8959 |
| 3 — Subject-line prefixes | Re=2903, Betreff, Fwd, Aw, Wg | 2903 |
| 4 — spaCy common-noun false positives | Du=1113, wünschen=773, EUR=2664, UTC=1278 | separate problem |

Key finding: `+41788578247` (×3852) is the user's own phone number from their email signature — pattern extractor correctly captured it; the count is a popularity skew, not pollution. Captured as separate TODO: zkm-eml signature stripping.

Class 4 (common-noun false positives) is a different root cause — spaCy model-level quality, not markdown rendering — and requires a different fix (POS filter or larger model). **Deferred to new item N9c.**

Personas converged on a **two-stage fix** co-located in new `plugins/zkm-ner/src/zkm_ner/textfilter.py`:
- **Pre-strip pass** removes class 1: drops markdown table separator rows (`^\s*\|[\s|:\-]+\|\s*$`) and pure-pipe rows (`^\s*\|+(\s*\|+)*\s*$`). Source-agnostic — applied to all md regardless of `source:` frontmatter.
- **Post-extraction stoplist** removes classes 2+3: flat type-agnostic exact-match filter on `value.strip().lower()` against 14 fixed words.

Cache invalidation: extraction cache is keyed by `(body_sha256, extractor_name, model_name, model_version)` — adding textfilter upstream doesn't change identity, so cache won't auto-miss. Fix: bump `model_version` suffix in `zkm_ner/version.py`. Pilot re-run mandated as verification.

## Decisions

1. **N9b scope** = classes 1+2+3 only. Class 4 → new **N9c** (spaCy common-noun false-positive gating).
2. **`plugins/zkm-ner/src/zkm_ner/textfilter.py`** (new file):
   - `strip_markdown_artefacts(body: str) -> str` — drop separator rows and pure-pipe rows.
   - `_STOPLIST = {"from", "to", "cc", "bcc", "subject", "betreff", "date", "sent", "received", "thread", "re", "fwd", "wg", "aw"}` (14 words).
   - `drop_stoplist(entities) -> list[Entity]` — type-agnostic exact-match filter.
3. **Wiring in `extract.py`**: `body = strip_markdown_artefacts(body)` before patterns/spaCy; `entities = drop_stoplist(merged)` before final dedup.
4. **Cache invalidation**: bump `model_version` suffix (e.g. `+textfilter-v1`) in `zkm_ner/version.py`.
5. **Pilot re-run**: mandatory verification step before 2026-06-05; compare top-N before/after; iterate if class-1/2/3 residuals remain.

**Explicitly out of scope:**
- Class 4 common-noun false positives → N9c.
- Email-signature stripping (→ new zkm-eml TODO).
- Source-gating the textfilter.
- `ZKM_NER_STOPLIST_EXTRA` runtime env knob (extension via code change + version bump, by design).

## Amendment session — email-signature stripping

Raised by user after confirming `+41788578247` ×3852 is their own number from email signature blocks. Signatures render verbatim into message md body and inflate counts for any personal contact detail.

Decision: new TODO "zkm-eml signature stripping" (heuristic block detection — `-- ` line, `Mit freundlichen Grüßen`, `Best regards`, `Sent from my…`). Belongs in `zkm-eml` rendering so every downstream consumer benefits. Not in N9b scope.

## Action items

- [ ] **N9b-1.** `plugins/zkm-ner/src/zkm_ner/textfilter.py` — `strip_markdown_artefacts` + `_STOPLIST` + `drop_stoplist`. Idempotent; preserves table data rows; type-agnostic.
- [ ] **N9b-2.** Wire into `plugins/zkm-ner/src/zkm_ner/extract.py` (pre-strip before patterns/spaCy; post-filter before dedup).
- [ ] **N9b-3.** Bump `model_version` in `plugins/zkm-ner/src/zkm_ner/version.py` (append `+textfilter-v1`).
- [ ] **N9b-4.** `plugins/zkm-ner/tests/test_textfilter.py` (6 tests): stoplist drops header words (parametrised), case-insensitive, no substring false positive; pre-strip drops separator rows, pure-pipe rows, preserves data rows.
- [ ] **N9b-5.** Re-run `plugins/zkm-ner/scripts/pilot.sh`; compare top-N before/after in `<store>/.zkm-state/ner-pilot-review.jsonl`; document delta.
- [ ] **N9b-6.** Update TODO.md: mark N9b done; add N9c; add zkm-eml signature stripping TODO.
