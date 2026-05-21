# 2026-05-21 — Embed rebuild ETA: resume now vs. clean first vs. profile GPU

**Started:** 2026-05-21 19:08
**Session:** 48e20823-711a-4eee-a347-5b1202fb1bc3
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🔧 Quinn (inference-server internals — llama-server embedding mode, GPU/throughput) (re-onboarded), 🗺️ Flora (information-flow architecture — content-type vs file-format, routing topology) (re-onboarded)
**Topic:** The schema-3 embed rebuild [402c] is paused at a 1796-doc checkpoint with a projected ~19.5h ETA. Decide whether to attack the ETA and how — (a) just resume, (b) clean dense email cruft first, (c) profile/relieve GPU contention.

## Agenda
1. Attack the ~19.5h ETA at all, or just let the resumable rebuild run unattended?
2. If attacking: which lever — source-level data-URI/base64 strip (b), GPU-contention relief (c), or both?
3. Sequencing & cache: clean-before-resume vs. let-it-finish-then-quality-pass; what happens to the 1796-doc checkpoint?
4. Adjacent: the 14-file base64-derived garbage-entity frontmatter bloat — fold into this fix or keep separate?

## Pre-meeting evidence (Explore agents, read-only)

**Content characterization:**
- Cruft is concentrated: ~15 body files carry base64 data-URIs (80–97% of their bytes, e.g. marina-hotel 517 KB of 532 KB); a handful carry empty HTML-table `| | |` cruft from markdownify.
- Root cause: zkm-eml `_html_to_markdown` (render.py:154) `markdownify(...)` passes `<img src="data:...">` through as `![](data:...)` verbatim. No data-URI stripping. Real attachments already detach to CAS (`originals.py`); inline data-URIs do not.
- Adjacent: 14 files have NER-written garbage `value: <base64-fragment>` entities in frontmatter (~275 KB in one), polluting both BM25 (`_tokenize_doc`, index.py:63) and embedded `entity_str` (embed.py:460).
- Corpus: 55,504 md / ~158 MB / 89,546 chunks.

**CAS-detach mechanism (for reuse):**
- `write_object(store, "mail", bytes)` (cas.py:12) takes raw bytes — perfect reuse seam for a decoded data-URI.
- Attachments do **not** appear as body links — they detach to `mail/_objects/`, get a symlink under `originals/mail/...`, and a frontmatter `attachments[]` entry (`_att_entry`, frontmatter.py:72). "Same as signatures" = same attachment path, flagged `inline`/`cid_referenced`.
- Impedance mismatch: `write_original`/`_att_entry` expect a `ParsedAttachment` (filename/content_type/part_index) an inline data-URI lacks. Adapter = synthesize a `ParsedAttachment` (`filename=inline-<sha8>.<ext>`, `part_index=-1`, `is_inline=True`).
- Cleanest insertion: **before** markdownify, in `convert.py` (where `store_path`, `msg`, `dest`, `inbox` are in scope) — extract `<img src=data:...>`, detach, drop the tag → markdownify emits a clean body.
- Cache: `build_embed_store` reuses chunks keyed on `(rel_path, mtime_ns)` (embed.py:292). Re-converting the ~15 files changes their mtime → `zkm index` re-embeds exactly those, reuses the rest.

## Discussion

### Agenda 1 & 2 — Attack the ETA, and with which lever

🏗️ **Archie:** The ETA is a *content* problem concentrated in ~15 files (80–97% base64). At ~2.5 tok/char a 2000-char chunk is ~5000 tokens — over the server batch, firing `_embed_single_with_split` and causing the 75–100s batches. Embedding base64 is pure noise. So the ETA cost and the retrieval-quality cost are the same defect; (b) is the root cause, not a side quest.

🔧 **Quinn:** Defend (c) as the cheapest probe: bge-m3 shares the GPU with always-on gemma4-e4b. `nvidia-smi dmon` for 30s settles whether throughput is contention-bound; pausing gemma4-e4b is a zero-code lever. But even a 2× contention win still embeds garbage — (c) makes the symptom cheaper, (b) deletes it. Not competitors.

😈 **Riku:** Caution on scope-creep dressed as root-cause. The 500 is fixed; [402c]'s job is "finish the rebuild." Opening render code + re-convert + re-embed + re-verify turns "press resume" into a chain. Minimum evidence to drop my objection: the strip touches only `data:` URIs, and re-converting busts ~15 files not thousands.

✂️ **Petra:** Closed set — ~15 base64, a handful table-cruft, 14 entity-bloat. Resist a general "chunk quality cleaner." Tight fix = handle `data:` image URIs at one site. (a) do-nothing is correct and zero-engineering; its only failure is permanently banking noise vectors.

🏗️ **Archie:** Cache bound for Riku: the fix lives in zkm-eml render; re-convert rewrites only files whose body changes (~15 + handful), mtimes change → re-embed exactly those, 1796 checkpoint preserved. Sequencing that maximizes benefit: fix → re-convert affected → resume.

🔧 **Quinn:** Run the 30s probe first (free info, may say pause gemma4-e4b regardless), then do (b) as the fix. Don't pick between them.

**Convergence:** (c) free probe; (b) the real fix; (a) rejected — banks noise vectors permanently.

**DECISION (Zommuter):** Option 1 — strip + GPU probe + resume. **Refinement:** rather than dropping the base64, reuse the existing CAS object-store mechanism (as attachments and signatures already do): decode the data-URI, store the binary in CAS, refer to it via link/frontmatter entry.

### Agenda 3 & 4 — Sequencing, and the existing entity bloat

🗺️ **Flora:** This is a routing leak, not a new feature. zkm already routes binaries to CAS and text to markdown; an inline data-URI is a binary that leaked into the text lane via markdownify. The fix sends it down the lane every other binary already takes — Tobias's reuse instinct is exactly right.

🏗️ **Archie:** Reuse seam is clean: `write_object(store,"mail",bytes)` + synthesized `ParsedAttachment`. Bounded ~1 session: HTML-preprocess in convert.py before render_body, the adapter, tests. Re-converting rewrites frontmatter too (new `attachments[]`), fine — mtime busts those files.

😈 **Riku:** Cost-accuracy challenge — the opening premise was false. 53,708 docs remain at ~1.25 texts/s ≈ ~12h baseline that has nothing to do with base64. The base64 dense penalty over baseline is ~3–7h. Cleaning saves the dense slice + noise vectors — real — but does NOT collapse the rebuild. Blocking a 12h-irreducible job on ~1 session of feature work to fix a ~3–7h slice is an asymmetry that should drive sequencing.

🔧 **Quinn:** Which makes the free probe matter more: if the 12h baseline is contention-bound, pausing gemma4-e4b dwarfs the base64 slice. Run it regardless.

✂️ **Petra:** Two honest shapes. **A — feature-first:** build detach, re-convert ~15, then one clean rebuild; no noise embedded, but waits ~1 session. **B — resume-now, detach-later-incremental:** resume tonight (eats ~3–7h dense slice + transient noise), build detach in parallel, re-convert 15 + re-embed only those. No throwaway code in either; B respects the 12h critical path.

🏗️ **Archie:** B wastes only ~3,900 noise vectors' transient compute. A is cleaner-on-paper; B is faster-to-unblocked. Deciding question: does Tobias want it running tonight, or one clean pass a session later?

🗺️ **Flora:** Agenda 4 — re-converting with new code *stops new bloat* (no data-URI → NER can't mis-extract), but the amendment contract is set-union merge: it won't *remove* existing garbage entities. That's what `zkm scrub zkm-eml` is for. Separate follow-up regardless of A/B.

**DECISION (Zommuter):** **A** — feature-first, one clean rebuild. B rejected as a waste of time and resources: the 12h baseline runs regardless, so there is no deadline that justifies burning a full GPU run on noise vectors that then get re-converted and re-embedded. Existing 14-file bloat → **separate `zkm scrub zkm-eml` follow-up** (keeps the detach PR focused). GPU probe runs regardless, before/at the start of the clean rebuild.

## Decisions

- **D1 — Root-cause the ETA via content fix, not endurance.** The ~19.5h ETA decomposes into ~12h irreducible baseline (53.7k docs @ ~1.25 texts/s) + ~3–7h dense-base64 slice. The base64 is also pure retrieval noise. Fix the content; do not "just let it run" (a) — (a) is correct but permanently banks noise vectors. Out of scope: a general chunk-quality scorer; empty-HTML-table cleanup (a handful of files, defer).
- **D2 — Inline data-URI images detach to CAS, reusing the attachment path.** Decode `<img src="data:...">` → `write_object(store,"mail",bytes)` → synthesized `ParsedAttachment` (`filename=inline-<sha8>.<ext>`, `part_index=-1`, `is_inline=True`) → existing `write_original`/`symlink_with_sidecar`/`_att_entry` machinery → drop the tag from the body. Insertion **before** markdownify in `convert.py`. Out of scope: inventing a body-link format (attachments don't appear in body); a bespoke strip.
- **D3 — Sequencing A: feature-first, single clean rebuild.** Build + test the detach, re-convert the affected files (verify churn is ~15, not thousands), run the GPU probe, then run one clean schema-3 rebuild to completion. B (resume-now/detach-later) rejected: no deadline justifies a full GPU run on noise that gets redone. Out of scope: parallelizing the rebuild with feature work.
- **D4 — Existing entity bloat is a separate `zkm scrub` follow-up.** The detach stops new bloat; set-union merge can't remove old garbage entities in the 14 files. `zkm scrub zkm-eml` over them, filed independently, run after the detach lands. Not folded into the detach PR.
- **D5 — GPU contention probe runs regardless.** `nvidia-smi dmon` during a live batch; if the baseline is contention-bound, pause always-on gemma4-e4b for the rebuild window.

## Action items

- [ ] **zkm-eml: inline data-URI → CAS detach (new feature, prerequisite for [402c]).** Before markdownify in `plugins/zkm-eml/.../convert.py` (where `store_path`/`msg`/`dest`/`inbox` are in scope), parse `msg.html_body`, extract `<img src="data:<mediatype>;base64,...">`, decode to bytes, `write_object(store_path,"mail",bytes)`, synthesize a `ParsedAttachment` (`filename=inline-<sha8>.<ext>` from mediatype, `part_index=-1`, `is_inline=True`, `cid_referenced` if applicable), feed the existing `write_original`/`symlink_with_sidecar`/`_att_entry` path, and drop the `<img>` tag so markdownify emits a clean body. Test: fixture HTML email with a data-URI img → CAS object created + frontmatter `attachments[]` entry (`inline: true`) + body contains no `data:` string. Bump-and-tag zkm-eml (minor; `uv publish` deferred — gated on Session B / no PyPI creds). Contract: `zkm convert zkm-eml` on a data-URI email produces a clean body + CAS object + attachment entry. <!-- id:15b2 -->
- [ ] **Re-convert affected files + verify churn bound, then run the clean rebuild [402c].** After 15b2 lands: re-run `zkm convert zkm-eml`; confirm only the ~15 data-URI files (+ handful) get rewritten (mtime churn small, per Riku's bound) before embedding. Then run the GPU probe (88f8) and one clean schema-3 `zkm index` to completion (resumes 1796 checkpoint; re-embeds the re-converted files; backgrounded, checkpoints every 100). This is the existing [402c] item, now gated behind 15b2. <!-- id:402c -->
- [ ] **GPU contention probe before the clean rebuild.** `nvidia-smi dmon` (or `nvidia-smi -l 1`) during a live bge-m3 embed batch on zomni; determine if the ~12h baseline is GPU-bound or contention-bound against always-on gemma4-e4b. If contention-bound, pause/stop gemma4-e4b in llama-swap for the rebuild window. Record finding (one line) in `docs/embed-rebuild-500-investigation.md`. <!-- id:88f8 -->
- [ ] **Run field-test 7c typed-value probe + close E9.** After the clean rebuild (`zkm doctor` embed docs == md count, schema 3): derive a real IBAN prefix from an `entities[].type: iban` value, `zkm search "<prefix>" --no-dense -k 5`, verify top hit has IBAN in `entities[]` not body; repeat for `amount`. Record in `docs/field-test-bge-m3.md` step 7. Close E9 in TODO.md. <!-- id:2c6e -->
- [ ] **`zkm scrub zkm-eml` over the 14 base64-bloated-frontmatter files (separate follow-up).** Removes existing base64-derived garbage `value:` entities that set-union merge can't drop. Run after 15b2 lands (so re-convert doesn't re-introduce them). Independent of the detach PR. <!-- id:541f -->
