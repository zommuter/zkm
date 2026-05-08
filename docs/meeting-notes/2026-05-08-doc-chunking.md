# 2026-05-08 — Doc chunking: plugin concern or core feature?

**Attendees:** Tobias (product owner), Architect, Riku (devil's advocate), Productivity expert
**Topic:** `TODO.md:33` — "Doc chunking for long emails/threads (current: first 2000 chars per doc, single embedding)". Is the per-plugin framing right, or is this a core feature?

## Agenda

1. What the 2000-char window actually does today
2. Plugin-specific or core: where does chunking belong
3. Scope guard — what we explicitly do not change
4. Sequencing relative to Phase 2 hygiene work

## Discussion

**Tobias:** The TODO entry scopes chunking to "long emails/threads". But every plugin can produce a long .md — notes, future PDFs, OCR scans, transcripts. Shouldn't this live in core, like the object-storage helpers we just landed?

**Architect:** It already does live in core. `src/zkm/embed.py:26` sets `_DEFAULT_EMBED_MAX_CHARS = 2000` and `_embed_text` at lines 309-327 truncates `post.content[:max_chars]` regardless of plugin. Plugins don't choose the cap; core does. The TODO framing is a core decision wearing plugin-shaped clothes.

**Riku:** Then the real question is just "remove the truncation", not "chunking, plugin vs. core". You're skipping a step.

**Architect:** Removing is not on the table. The comment at `embed.py:23-25` records the constraint: 2000 chars ≈ 335 German tokens, which fits llama-server's default `--ubatch-size 512`. Larger windows either fail at the embed endpoint or get silently truncated server-side. The choice is: truncate (status quo), require ops changes per user (raise ubatch on the embed server), or chunk (multiple embeddings per .md).

**Tobias:** What's the impact of the truncation today?

**Architect:** BM25 indexes the whole file (`index.py:63-68`, `_tokenize_doc` over full `post.content`). Dense sees the first ~10% of a long thread. RRF then merges file-level hits from both legs (`query.py:246-259`, keyed by `hit.path`). A query that matches paragraph 5 of a thread gets a BM25 hit but no dense reinforcement — exactly the "literal-match saturation" that session 6 widened the dense pool to compensate for. Wider pool was a workaround; chunking is the actual fix.

**Riku:** zkm-eml threads aggregate per message; zkm-notes copies whole files; OCR will produce single-blob pages. Three different shapes. A naive char-window chunker will split a thread mid-message and a note mid-sentence. You may degrade recall, not improve it.

**Architect:** Granted, naive char-window with overlap is crude. It is strictly better than the status quo, where everything past char 2000 is invisible to dense retrieval. Smart chunking — sentence boundaries, message boundaries, paragraph weights — is a quality knob to turn after the field test names a specific failure. Minimum viable change: chunk on char windows in core, embed each chunk, aggregate dense hits back to file-level by `max(score)` before RRF.

**Productivity expert:** N=2 rule. Who else needs chunking?

- zkm-eml threads — confirmed (`thread_index.py:_write_index` aggregates messages into one .md, easily multi-kB).
- zkm-notes — confirmed (any input file ≥ 2000 chars copied verbatim by `examples/zkm-notes/convert.py`).
- zkm-pdf (Phase 2/3 backlog) — confirmed by construction; PDFs are multi-page.
- Any plain-text dump from web scrape, OCR, transcription — confirmed.

N is 4+. Easily clears the bar.

**Riku:** The aggregation step — "max-score chunk per file" — is where this gets dangerous. If a file has 10 chunks and one matches well, that file outscores a more uniformly relevant file. You trade one bias for another.

**Architect:** True. But "uniformly relevant" doesn't survive the current truncation either. The LLM context step has the same head-bias today: `query.py:26` defines `_DEFAULT_MAX_DOC_CHARS = 500`, and `llm_stream` at `query.py:534-613` takes `post.content[:max_chars]` per hit — the answer leg is biased toward document head as well. Per-chunk LLM context is a separate fix and explicitly out of scope here.

**Tobias:** So embed-side chunks for recall; file-level retrieval unit unchanged?

**Architect:** Yes. `EmbedStore` (`embed.py:112`) gains a `chunk_index` column; rows become `(path, chunk_index, vector, mtime_ns)`. `search_dense` returns `(path, chunk_index, score)`; an aggregator collapses to `max(score)` per `path` before RRF. BM25 untouched. CLI snippets untouched. RRF untouched. Change localized to `embed.py` and a thin aggregator in `query.py`.

**Productivity expert:** Default chunk size?

**Architect:** 2000-char window with 200-char overlap, both env-overridable (`ZKM_EMBED_CHUNK_CHARS`, `ZKM_EMBED_CHUNK_OVERLAP`). The 2000 stays — same ubatch reasoning. The change is producing multiple chunks instead of one truncation.

**Riku:** Cost. A 20 kB thread becomes ~10 embeddings instead of 1. Embed runs are already the slow step.

**Architect:** Linear in document length. Long-tail documents pay more; short ones pay nothing extra. Session 2's atomic checkpoint already handles partial runs. Cost is real but bounded, and gated by an `mtime_ns` check that already skips unchanged files.

**Tobias:** Plugin-supplied chunk hints — `chunk_offsets` in frontmatter at message or page boundaries?

**Architect:** Defer. zkm-eml *could* emit message-boundary offsets and the chunker *could* prefer them over char windows. The gain over a 200-char-overlap windower is small, and we have no field-test evidence it matters yet. Naive windows first; smart hints if and when a field-test step names a recall failure that hints would fix.

**Productivity expert:** Phase placement? Phase 2 is currently object-storage and hygiene.

**Architect:** Phase 2 session 8, after session 7 closes. It's a query-quality follow-up, not a hygiene one — but it directly fixes a known retrieval gap that sessions 6 and 7 worked around, so it earns its place before Phase 3. Doesn't block hygiene; doesn't depend on it.

**Riku:** Last skeptic question. What field-test signal proves chunking helped?

**Architect:** Add step 6 to `docs/field-test-bge-m3.md`: pick a known-long thread where the matching content lives past char 2000, query for it, expect non-zero dense hits. Today that query returns BM25-only.

**Productivity expert:** Out-of-scope reminder, written down so we don't slide:

- Smart sentence/paragraph chunking — Phase 3 quality work.
- Per-chunk LLM context (passing the matching chunk, not the document head) — separate decision, separate session.
- Chunk-level snippets in CLI output — no user request, no benefit yet.
- Moving BM25 to chunk-level — no benefit; BM25 already sees full text.

**Tobias:** Agreed.

## Decisions

- **Chunking is a core feature, not plugin-specific.** Lives in `src/zkm/embed.py`. `TODO.md:33` reframed: drop "for long emails/threads".
- **Embed-side chunks only.** BM25 unit stays whole-document. RRF unit stays whole-document. Multiple embedding rows per .md, aggregated by `max(score)` to file-level before fusion.
- **Naive char-window chunker with overlap** as MVP. Defaults: 2000 chars / 200 chars overlap. Env-overridable. Plugin-supplied hints deferred until field-test demands them.
- **No change to LLM context assembly** (`query.py:_DEFAULT_MAX_DOC_CHARS`, `llm_stream`). Per-chunk LLM context is a separate decision.
- **Phase 2 session 8.** Lands after session 7 closes; does not block object-storage or hygiene work.

## Action items

- [ ] Session 8a: `embed.py` — replace single-truncation `_embed_text` with chunking; add `chunk_index` column to `EmbedStore`; bump store version with rebuild-on-mismatch (existing single-row stores rebuild on next `zkm index`); env knobs `ZKM_EMBED_CHUNK_CHARS` (default 2000) and `ZKM_EMBED_CHUNK_OVERLAP` (default 200); retire `ZKM_EMBED_MAX_CHARS` with a deprecation notice on read.
- [ ] Session 8b: `query.py` — `search_dense` aggregates `(path, chunk_index, score)` to `max`-per-path before returning to RRF. CLI output unchanged.
- [ ] Session 8c: tests — `test_embed.py` chunk count and overlap correctness; `test_query_recall.py` long-document recall (matching content past char 2000 returns dense hits).
- [ ] Session 8d: docs — add step 6 to `docs/field-test-bge-m3.md` (long-document recall probe). Update `docs/hybrid-search.md` to remove the "first 2000 chars per doc" caveat and document chunk aggregation.
- [ ] Session 8e: `TODO.md` — close line 33 with reference to this meeting; reword scope (drop "emails/threads"); add session 8 subsection.
