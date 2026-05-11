# 2026-05-11 — NER: next steps for tangible results soon

**Started:** 2026-05-11 15:31
**Session:** a6cd456b-1833-4b05-87c2-cd17371e6bfd
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🧠 Mira (ML quality lens — re-onboarded from 2026-05-08 information-flow), Zommuter (user)
**Topic:** Pick the next NER intervention that yields the biggest visible FP reduction for the smallest effort, given the user's explicit goal of "tangible results soon".

## Agenda

1. Triage: which residual FP classes from the post-N9c pilot are biggest and most-attackable in ≤1 session?
2. Mechanism: for the chosen class, which fix layer (phrase blocklist, signature stripping, LLM verifier, GLiNER A/B)?
3. Sequencing: what lands first, what is deferred, and what counts as "tangible"?

## Past meetings audit

- 2026-05-11-0946 (NER next after N9b): N9c-1 → N9c-9 all done; N10/N11/CLAUDE.md cleanup done via 2026-05-11-1506. Status observability `[ ]` left as 1-line log-and-wait TODO. No orphans.
- 2026-05-11-1506 (N10/N11 docs bundle): all action items closed; `object-storage.md` reconciliation done same day (TODO line 241).
- Remaining open NER items: N9d (backlog), N9e (backlog) — both gated "hold design meeting before implementation". This meeting is the design meeting for the GLiNER-promotion sub-path of N9d.

## Cross-project discoveries surfaced

- [2026-05-10 zkm] NER pollution on rendered-markdown corpora has 4+ distinct classes (now five with structural-artefact and bilingual-noun classes); each needs a different fix layer. Don't blend mechanisms; stoplist beats fuzzy cleanup for closed-set garbage.
- [2026-05-10 zkm] Extraction-cache keys miss preprocessing changes — must bump `model_version` in `version.py` whenever pre/post filter behaviour changes.

## Discussion

### Item 1 — Triage: residual FP classes post-N9c

**🏗️ Archie:** Snapshot from TODO.md N9c-6/N9c-8 (final state, 467,956 total mentions, down from 771,831 pre-N9b):

| Class | Top examples | Top counts | Fix layer |
|---|---|---|---|
| **A. Multi-word salutations** | `Hallo Tobias`, `Best Regards`, `Guten Tag Herr Kienzler`, `Hello Tobias` | ~4–5k combined | phrase-pattern blocklist in `textfilter.py` |
| **B. English nouns** | `Actions` ×430, `Download` ×357 | ~0.8k | bilingual POS partial; closed-set extension |
| **C. Self-signature** | `Tobias Kienzler` ×11,270 (own outbound signatures) | ~10k+ | zkm-eml signature stripping (separate plugin) |
| **D. Legal boilerplate** | `L-2449 Luxembourg RCS Luxembourg` ×859, `S.C.A. Société...` ×854 | ~2k | real entities, high-freq — explicitly deferred |

**✂️ Petra:** Raw counts say C wins, but C lives in zkm-eml, not zkm-ner. Different code paths, different blast radius, signature-detection is heuristic-fragile. A is the highest-impact zkm-ner-side intervention: ~4–5k mentions across 4–6 canonical phrase patterns, low FP risk (closed-set), slots into existing `textfilter.py` pattern. N=2 holds (third stoplist mechanism).

**🧠 Mira:** Salutation phrases are predictable. Two architectural options: (1) **Pre-extraction strip** — extend `strip_markdown_artefacts` to also strip greeting/sign-off lines. Stronger but false-strips could remove real content. (2) **Post-extraction value filter** — `_SALUTATION_BLOCKLIST` frozenset; drop entities whose value matches. Safer.

**😈 Riku:** FP risk on (2): `Best Regards` safe — never a real name. `Hallo Tobias` safe — multi-word greeting; real `Tobias` would be standalone. But `Dear NAME` patterns can't be wildcarded. So: closed-set frozenset of full phrases, not regex with `<NAME>` wildcards. Start with observed pollution, extend as new patterns surface.

**🏗️ Archie:** Sequence: A in this session (phrase blocklist + scrub + re-pilot), C as separate zkm-eml work, B and D deferred.

**😈 Riku:** Minimum evidence this is the right pick: top-N person list currently leads with `Hallo Tobias` ×1930 and `Hello Tobias` ×392 just behind legitimate names. Dropping those removes two top-10 entries — *visible* in `pilot.sh` output.

**User:** Picked **D then A** — GLiNER A/B first (cheap measurement), salutation blocklist as fallback. Reading: lever-first instinct — check whether a bigger architectural change moots the patch class before committing to the patch.

### Item 2 — GLiNER A/B protocol design

**🏗️ Archie:** GLiNER already wired (`plugins/zkm-ner/src/zkm_ner/gliner_backend.py`): model `urchade/gliner-multilingual-v2.1` (~280M params), schema-compatible with spaCy, independent cache key (`model_name=gliner`). Caveat: `_pos_filter` is no-op for GLiNER outputs (`root_pos=""`).

**🧠 Mira:** Full-corpus GLiNER on ~55k docs: ~280M-param transformer on CPU → ~100–500 ms/doc → **1.5–8 h wall time**. Sampling essential. Three strategies:
1. **Targeted FP-file sample** — grep store for top FP strings, ~200–2,000 files. Directly answers the FP question. ~5–30 min.
2. **Random stratified 500-file sample** — broader; may miss specific FP clusters. ~10–30 min.
3. **Full corpus background** — set-union amendment would *contaminate* frontmatter. 2–8 h. Risky.

**😈 Riku:** Skip option 3 — frontmatter pollution risk. Build a clean comparison script (`scripts/gliner_ab.py`) that calls `extract()` directly and writes to `.zkm-state/gliner-ab-<timestamp>.jsonl`. Never touches frontmatter. ~50 LOC.

**🏗️ Archie:** Concur. Script runs both backends per file, reports per-FP-string surviving/dropped counts + any new GLiNER-introduced top-20 entries.

**✂️ Petra:** Hard out-of-scope: switching the default model, full-corpus run, amendment integration. **Measurement only.**

**🧠 Mira:** Pre-flight: confirm `zkm-ner[gliner]` extra is installed and the model loads. If not, `uv sync --extra gliner`. Cold-load ~10–30s.

**😈 Riku:** Success criterion. **Define now** or we'll squint at output and rationalise either way. Proposal: **if GLiNER reduces each of the top-4 multi-word salutation FP strings to ≤10% of their spaCy count AND introduces no new top-20 FP cluster** → switching the default model becomes the path; A is mooted. **Otherwise** → land A this session as fallback.

**🏗️ Archie:** Concrete bar: spaCy emits `Hallo Tobias` ×1930. ≤200 from GLiNER on the same file set = 10× reduction. Anything weaker → A wins; phrase blocklist is deterministic.

**✂️ Petra:** Wall-time cap: ≤30 min. Overrun → fall back to A regardless.

**Pre-emption (Riku → user):** Loop-closure-instinct is profile-relevant — you might raise N9e territory mid-meeting. Flagged in advance: this A/B is model-comparison, not a verifier pipeline. Out of scope.

**User:** Picked **Two-stage with smoke gate**. 5-file smoke first; targeted sample only if smoke passes. ≤30 min cap.

### Item 3 — Sequencing and "tangible" deliverable in each branch

**🏗️ Archie:** Three outcome branches:
1. **Smoke fails** (GLiNER also extracts `Hallo Tobias` as PERSON) → fall back to A this session.
2. **Smoke passes, Stage 2 passes success bar** → record evidence; new TODO for "switch default model" decision; A mooted; no code shipped.
3. **Smoke passes, Stage 2 fails success bar** → fall back to A as deterministic floor.

Tangible deliverable in branches 1 and 3: phrase blocklist landed. Branch 2: A/B report + follow-up TODO.

**✂️ Petra:** Risk: if smoke fails at minute 5 and A isn't pre-designed, we burn the next 30 min designing A from scratch — defeating "tangible soon". Two options: **(α) Pre-design A** alongside the A/B script (mild scope expansion, high payoff). **(β) Strict A/B scope** (cleaner separation, but no tangible result if smoke fails).

**😈 Riku:** α has a hidden gotcha: pre-designing A requires reading the pilot review file to find the actual top-N multi-word FPs, not just my four-string guess. Do α properly with an audit, not from guesswork.

**🧠 Mira:** Audit is correct. The four FP strings came from TODO.md N9c-6 notes, not from a fresh top-N. Other patterns likely: `Mit freundlichen Grüßen`, `Lieber Tobias`, `Hi Tobias`.

**🏗️ Archie:** α-path is 8 numbered action items (see Decisions / Action items).

**✂️ Petra:** N=2 check for A — third stoplist mechanism; reuses case-insensitive `value.strip().lower() in <frozenset>` pattern. Solid. Audit expansion fits the cheap-helper-extension exception.

**Pre-emption (Riku → user):** Drift-aversion is profile-relevant — if Stage 2 passes and we add "switch default NER model" as a follow-up, you may push back that having both paths is a drift source. Acknowledged: a successful Stage 2 produces a follow-up meeting, not parallel paths. The switch would *replace* the default.

**User:** Picked **α: pre-design A alongside A/B**. Consistent with scope-tolerance + combination-picker.

## Decisions

1. **Target class:** Class A (multi-word salutation phrase FPs) is the next NER intervention. Class C (signature stripping in zkm-eml) and Class B (English-noun residuals) deferred.
2. **Path order:** GLiNER A/B *first* (cheap measurement), salutation phrase blocklist as fallback. A/B is **measurement only** — never touches frontmatter or amendments.
3. **A/B protocol — two-stage with smoke gate:**
   - Stage 1: 5-file smoke test on one representative file per top-4 FP string. ~5 min.
   - Stage 2 (if Stage 1 passes): targeted sample across all files matching top-4 FP strings via `git grep -l`. ~25 min cap.
   - Hard success bar: each top-4 FP reduced to ≤10% of spaCy count AND no new top-20 FP cluster introduced by GLiNER.
4. **Comparison script:** `plugins/zkm-ner/scripts/gliner_ab.py` — reads file list, calls `extract(body, model="spacy"|"gliner")` per file, writes delta JSONL to `.zkm-state/gliner-ab-<ISO8601>.jsonl`. Never touches frontmatter. ~50 LOC.
5. **A pre-design (α):** Audit `pilot.py` to dump top-30 multi-word PERSON values from live frontmatter; freeze `_SALUTATION_BLOCKLIST` closed set from real data, not guesswork. Spec the function + scrub extension + version bump without writing code.
6. **A trigger:** Implement A *only if* smoke gate fails OR Stage 2 fails the success bar. Branch-2 (Stage 2 passes) → no A; instead write A/B findings as a Class 2 planning record and add a new TODO line for "Meeting: switch default NER model to GLiNER".
7. **TODO numbering:** New TODO entries — `N9d-α` (this A/B), `N9f` (salutation blocklist, conditional).

**Out of scope:** LLM verifier (N9d main, deferred), GLiNER as full-corpus default (separate decision), zkm-eml signature stripping (separate plugin work), Class B closed-set extension (defer to N9c follow-up), Class D legal boilerplate (deferred), closed-loop heuristic⇄verifier (N9e).

## Action items

- [ ] **N9d-α-1.** Audit step: patch `plugins/zkm-ner/scripts/pilot.py` (~10 LOC) to dump top-30 multi-word (≥2-token) PERSON values to stderr; run once against `~/knowledge/`; capture closed-set salutation list. Contract: list ≥4 phrases, all visibly salutation/sign-off patterns.
- [ ] **N9d-α-2.** Pre-flight: verify `zkm-ner[gliner]` is installed in the plugin venv (`uv pip list | grep -i gliner`); if missing, `uv sync --extra gliner` from `plugins/zkm-ner/`. Contract: `python -c "from gliner import GLiNER"` exits 0.
- [ ] **N9d-α-3.** `plugins/zkm-ner/scripts/gliner_ab.py` (~50 LOC): reads `--files` (newline-delimited paths) or stdin, runs `extract(body, model="spacy")` and `extract(body, model="gliner")` per file, writes JSONL records `{path, spacy_entities, gliner_entities}` to `.zkm-state/gliner-ab-<ISO8601>.jsonl`. Contract: never imports `zkm.amendments`; never writes to frontmatter.
- [ ] **N9d-α-4.** Smoke gate: select 5 representative files (one per top-4 FP string from N9d-α-1 + one control); run gliner_ab on them; verify gate condition (each FP string dropped by GLiNER).
- [ ] **N9d-α-5.** Stage 2 (gated on N9d-α-4 passing): `git grep -l -E '<top-4 FP regex>' -- '*.md'` from `~/knowledge/` → pipe filelist to gliner_ab.py → check success bar (≤10% retention each + no new top-20 cluster).
- [ ] **N9f (pre-spec; impl gated on N9d-α-4 OR N9d-α-5 failure):**
  - Add `_SALUTATION_BLOCKLIST: frozenset[str]` to `plugins/zkm-ner/src/zkm_ner/textfilter.py`, populated from N9d-α-1 audit.
  - Add `drop_salutation_blocklist(entities) -> list[Entity]` mirroring `drop_commonnoun_stoplist` shape.
  - Wire into `extract()` after `drop_structural_artefacts`.
  - Bump `version.py` to `+textfilter-v3+posfilter-v1`.
  - Extend `_is_scrub_candidate` in `plugins/zkm-ner/convert.py` to include the new predicate.
  - Tests in `plugins/zkm-ner/tests/test_textfilter.py` — parametrised per phrase + case-insensitivity.
  - Run `zkm convert ner` (cache bust) then `zkm scrub ner --apply`; commit; re-run `pilot.sh`; document delta in TODO.md.
- [ ] **Branch-2 deliverable (gated on N9d-α-5 success):** Write `docs/meeting-notes/2026-05-11-{HHMM}-gliner-ab-results.md` as Class 2 planning record. Add a new TODO line: "Meeting: switch default NER model to GLiNER".
- [ ] **TODO update:** Add N9d-α and N9f entries to TODO.md under the Phase 2.5 NER section; mark deliverable conditions clearly.
- [ ] **meeting-style.md:** Add this meeting to "Past meetings" index.
