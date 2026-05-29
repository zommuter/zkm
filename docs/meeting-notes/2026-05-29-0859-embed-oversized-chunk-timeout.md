# 2026-05-29 — `zkm index` embed phase: oversized chunks + fatal timeout

**Started:** 2026-05-29 08:59
**Session:** 858a2c4e-3f90-4c71-9a34-ba2bada61638
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🔧 Quinn (inference-server internals, re-onboarded)
**Topic:** `zkm index` embed rebuild dies after ~37 min — oversized chunks trigger a pathologically slow split fallback, then one transient timeout aborts the entire multi-hour run.

## Agenda
1. Why do 10–12k-token chunks exist at all, when the chunker targets 2000 chars?
2. Why does one transient ReadTimeout at text 1024 abort the entire run?
3. Throughput + rollout (resume vs clean rebuild, data scrub)

## Discussion

### Agenda 1 — why do 10–12k-token chunks exist?

🏗️ **Archie:** Found it — it's not CJK density as the filenames suggest. `_chunk_texts` (`embed.py:485-496`) windows the body at 2000 chars, but line 490 prepends `title + tag_str + entity_str + participant_str` to **every** window. That prefix is unbounded. Worst offender `回复-回复-loan.md`: body 64,902 chars, **75 entities, `entity_str` = 22,631 chars**, 2 participants. Every "2000-char chunk" is actually ~24,700 chars ≈ the 12,410-token server rejection, repeated on every window. Body is 0% CJK — the Chinese title is a red herring.

🔧 **Quinn:** bge-m3's max sequence is 8192 tokens — that's why the server's physical batch is 8192. A 12k-token chunk isn't just slow, it's **unembeddable** (the model truncates). The server is right to reject it. The fix must be client-side: never assemble a text over the model's sequence limit. The reactive split-fallback (`embed.py:131-146`) halves by characters and mean-pools — so a chunk that's 90% identical entity-prefix produces two near-identical halves whose mean ≈ the prefix embedding: garbage vector, N recursive HTTP round-trips to compute it.

😈 **Riku:** So the 2026-05-21 fix (server batch 8192 + split fallback + 180s timeout) was symptomatic: it tried to *survive* oversized chunks instead of *not producing* them. What's the minimum that makes oversized chunks structurally impossible?

🏗️ **Archie:** Two layers. (1) **Embed-side (load-bearing):** bound the prefix and cap total assembled text to a safe char budget (pre-split body into more windows). Server never sees an oversized input; split-fallback reverts to rare safety net. (2) **Data-side (hygiene):** those 75 entities are NER garbage — new bloated docs will keep appearing, so the cap is the durable fix.

✂️ **Petra:** The embed-side cap earns its keep — a few lines in `_chunk_texts`. Don't fold a NER re-run in. Just cap inline.

🔧 **Quinn:** Don't cap the prefix to zero — title/tags/entities carry the retrieval signal. Bound it (~500 dedup'd chars of entity_str) so high-value short entities survive but a 22k-char garbage dump can't dominate.

### Agenda 2 — why does one ReadTimeout abort the whole run?

🏗️ **Archie:** The batch loop (`embed.py:325-363`) retries `(0,15,30,60)` then `raise EmbedUnavailable` — aborts the **entire** rebuild. The timeout at text 1024 is most likely the server wedged by the preceding split-fallback storm (texts 224–800 hammered it with recursive single-input requests).

🔧 **Quinn:** That's the causal link: agenda-1's split storm probably *caused* agenda-2's timeout. Sustained recursive single-text load wedges llama-server embedding mode (`[88f8]` confirmed GPU-bound). Fix agenda 1 and the timeout likely never fires — but you still want isolation for genuine blips.

😈 **Riku:** A 10h run that aborts on one transient timeout is fragile. Making it non-fatal leaves a few docs un-embedded — a hole, not a crash. Strictly better.

✂️ **Petra:** Resilience fix: on final give-up, **log + checkpoint + skip batch + continue**, report skipped docs at end. No queue/supervisor. Handful of lines.

🔧 **Quinn:** Extend the backoff ladder one rung (`…,60,120`) — the server's self-recovery window is ~30–40s but can need longer under a wedge.

😈 **Riku:** Gate: after the agenda-1 cap, a clean pass must show **zero** "oversized chunk"/split-fallback lines in the first ~500 chunks. If they reappear, re-tune before trusting a 10h run.

### Agenda 3 — rollout

🏗️ **Archie:** The running rebuild (`[402c]`, PID 95944) was built with the buggy chunker. The cache key is per-doc mtime (`embed.py:292-300`), not chunk content, so a resume after changing `_chunk_texts` would **reuse the stale garbage vectors**. We must invalidate.

🔧 **Quinn:** Bump `_STORE_SCHEMA_VERSION` 3→4. `load_embed_store` (`embed.py:234`) returns `None` on mismatch → `prev_es` is `None` → everything re-embeds clean. One-line invalidation.

✂️ **Petra:** Single serial pass (~12h baseline). Concurrency rejected — re-creates the server wedge per Quinn.

### Amendment — "scrub first" depends on a scrub that doesn't exist yet

📬 **Pim (re-onboarded):** The 75 entities are **not** base64/data-URI bloat. 65/75 are type `org`; the longest values are HTML-entity-encoded quoted-reply markup: `&gt;&nbsp;&nbsp;&gt;...` runs up to 2178 chars — the `>` quote markers and `&nbsp;` of a deeply nested reply, NER-extracted as orgs. The body was rendered with HTML entities left **undecoded** pre-NER.

🏗️ **Archie:** `zkm scrub zkm-eml`'s `scrub()` (`convert.py:497-555`) filters **only** `_BASE64_FRAGMENT_RE` (40+ chars pure base64). `&gt;&nbsp;` strings don't match — existing scrub is a **no-op for this class**.

😈 **Riku:** Don't ship a scrub that no-ops. If we do scrub-first, the scrub must catch this class.

📬 **Pim:** Two depths: (1) targeted `scrub()` extension — add an HTML-entity-run pattern alongside `_BASE64_FRAGMENT_RE` (cheap, closed-set, correct); (2) root-of-root — zkm-eml render `html.unescape()` + quoted-reply stripping pre-NER (durable, re-opens corpus-wide re-extraction).

**User call:** Do **not** implement this session — update TODO only; land all fixes as Class 1 items in next sessions. PID 95944 kill left to user.

## Decisions
- **Root cause:** `_chunk_texts` (`embed.py:490`) prepends an **unbounded** `entity_str` prefix to every body window. Worst case: 22,631 chars → every chunk ≈ 24,700 chars ≈ 12,410 tokens (server limit: 8192 tokens). CJK filename = red herring.
- **Embed fix (Class 1):** bound prefix to ~500 dedup'd chars + cap total assembled text to token budget, pre-splitting body into more windows. Split-fallback reverts to rare safety net. Out of scope: token-aware tokenizer dep; concurrency.
- **Resilience fix (Class 1):** `_EMBED_RETRY_SLEEPS` → `(0,15,30,60,120)`; on final give-up log+checkpoint+skip+continue, report skipped docs at end. Out of scope: queue/supervisor.
- **Invalidation (bundled):** `_STORE_SCHEMA_VERSION` 3→4; v3 stores auto-discard on next `zkm index`.
- **New NER pollution class identified:** HTML-entity quoted-reply markup (`&gt;&nbsp;` runs, 65/75 type `org`) — distinct from the 4 documented classes (see `docs/meeting-notes/2026-05-10-1640-n9b-email-header-stoplist.md`). Current scrub **does not catch it**.
- **Scrub fix (Class 1):** extend `scrub()` with HTML-entity-run pattern. Forward/larger (not gating): zkm-eml render HTML-decode + quoted-reply strip pre-NER.
- **Operational sequence (user-run, next sessions):** kill PID 95944 → extend scrub → `zkm scrub zkm-eml` → `zkm index` clean. Riku's gate: zero "oversized chunk"/split-fallback lines in first ~500 chunks before walking away.

## Action items
- [ ] **[embed] Cap chunk assembly in `_chunk_texts`** (`src/zkm/embed.py:485-496`): bound prefix to ~500 dedup'd chars + cap total assembled text to a token budget; pre-split body into more windows. Regression test: synthetic 30k-char-entity doc yields only chunks whose assembled length ≤ budget. Contract: zero "oversized chunk" lines on a clean rebuild. — see `docs/meeting-notes/2026-05-29-0859-embed-oversized-chunk-timeout.md` <!-- id:95b9 -->
- [ ] **[embed] Non-fatal batch failure in `build_embed_store`** (`src/zkm/embed.py:325-363`): retry ladder `(0,15,30,60,120)`; on final give-up log+checkpoint+skip+continue; report skipped docs at end. Contract: one transient timeout does not abort the run. — see `docs/meeting-notes/2026-05-29-0859-embed-oversized-chunk-timeout.md` <!-- id:de33 -->
- [ ] **[embed] Bump `_STORE_SCHEMA_VERSION` 3→4** (`src/zkm/embed.py:36`), bundled with the above. Contract: v3 stores re-embed from zero on next `zkm index`. — see `docs/meeting-notes/2026-05-29-0859-embed-oversized-chunk-timeout.md` <!-- id:a600 -->
- [ ] **[M] Extend `zkm scrub zkm-eml`** (`plugins/zkm-eml/convert.py:497-555`): add HTML-entity-run pattern (`&gt;`/`&nbsp;`/`&amp;`-dominated values) alongside `_BASE64_FRAGMENT_RE`; zkm-eml minor bump. Contract: removes `&gt;&nbsp;` quoted-reply garbage entities. — see `docs/meeting-notes/2026-05-29-0859-embed-oversized-chunk-timeout.md` <!-- id:d1f2 -->
- [ ] **[M] (forward, larger) zkm-eml render HTML-decode + quoted-reply strip pre-NER** — durable root-of-root; re-opens corpus-wide NER re-extraction. Not gating; scope review before starting. — see `docs/meeting-notes/2026-05-29-0859-embed-oversized-chunk-timeout.md` <!-- id:8497 -->
- [ ] **[embed/ops] After the above land:** kill PID 95944, run `zkm scrub zkm-eml`, then `zkm index` clean; verify Riku's gate + `zkm doctor` embed docs == md count. Folds into `[402c]`/`[2c6e]`. — see `docs/meeting-notes/2026-05-29-0859-embed-oversized-chunk-timeout.md` <!-- id:30f5 -->
