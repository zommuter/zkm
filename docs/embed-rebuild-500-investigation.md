# Embed rebuild 500 — RESOLVED (root cause + fixes) + handover

**Date:** 2026-05-21
**Status:** ROOT-CAUSED AND FIXED. Rebuild **paused mid-run** at a 1796-doc checkpoint (resumable).
Remaining: resume the rebuild to completion, then the 7c probe, then close E9.
**Meeting:** `docs/meeting-notes/2026-05-21-1011-embed-rebuild-500.md`

## TL;DR

The "embed 500" was **not** a transient slot/KV server bug (the original hypothesis in this
doc's earlier version was wrong). It was a **deterministic chunk-size vs. server-batch-size
mismatch**, uncovered by capturing the actual 500 body:

```
input (2501 tokens) is too large to process. increase the physical batch size
(current batch size: 2048)
```

The 2000-char chunker assumes ~6 chars/token, but dense content (CJK / encoded / quoted-printable
email) tokenizes at ~1.25–2.5 tok/char → chunks of 2500+ tokens. The bge-m3 llama-server rejected
any single input exceeding its **logical** batch size (`--batch-size`, default 2048).

Three distinct problems were found and fixed in sequence (each by direct evidence):

1. **Chunk > server batch.** Fixed both ends:
   - **zomni** `/etc/llama-swap/config.yaml`: bge-m3 `--batch-size 8192` **and** `--ubatch-size 8192`
     (was `--ubatch-size 2048`, no explicit `--batch-size`). **The logical `--batch-size` (default
     2048) was the real limiter** — `--ubatch-size` clamps to it, and the error's wording "physical
     batch size" is misleading. Backup: `/etc/llama-swap/config.yaml.bak-20260521`.
   - **zkm v0.9.0**: client-side belt-and-suspenders — on a "too large to process" 500 (deterministic),
     do **not** backoff-retry; embed each text individually and recursively split + mean-pool any
     oversized chunk (`_embed_single_with_split`). One bad chunk never aborts the rebuild.
2. **`--ubatch-size` alone was insufficient** — the running process already had ubatch 8192 yet
   still errored at "2048", proving `--batch-size` (logical) is the gate. Adding `--batch-size 8192`
   fixed it (verified: a 27750-char ~3700-token input now embeds at 200; was 500).
3. **60s client timeout too tight.** After (1)+(2), dense chunks embed natively, but a 32-chunk batch
   of dense content can total ~150k+ tokens and take ~75–100s on bge-m3 → httpx ReadTimeout aborted
   the whole embed. **zkm v0.9.1**: raised `build_embed_store` timeout 60→180s.

After all three, the rebuild runs clean (no 500s, no timeouts, no aborts), verified past the
previous failure points.

## Remaining work (next session)

1. **Resume the embed rebuild to completion.** `zkm index` (resumes from the 1796-doc checkpoint;
   schema 3). The dirty-tree guard requires a clean `src/zkm/` tree — commit first or
   `ZKM_BYPASS_DIRTY_CHECK=1`. Run it backgrounded; checkpoints every 100 texts make it resumable.
2. **Run the 7c typed-value probe.** Derive a real IBAN prefix from an `entities[].type: iban`
   value (not the `CH56` placeholder), `zkm search "<prefix>" --no-dense -k 5`, verify the top hit
   has the IBAN in `entities[]` but NOT in body; repeat for an `amount`. Record into
   `docs/field-test-bge-m3.md` step 7.
3. **Close E9** in `TODO.md`; note `convert ner` was redundant (entities[] already populated).

## OPEN DECISION — the rebuild is slow (~per-session blocker)

At pause, the guard projected **ETA ~19.5h** (~1.25 texts/s) for the full 89546-chunk re-embed,
dragged down by dense early-corpus email batches (75–100s each). It is *correct and unattended*
(resumable), but ~19h is a lot. Levers for the next session to weigh:

- **(a) Just let it run** overnight/backgrounded. Simplest; correctness is fine.
- **(b) Chunking quality** — many dense chunks are likely HTML / base64 / quoted-printable email
  cruft that embeds to noise. Excluding/cleaning them would cut tokens *and* improve retrieval
  quality. This is a separate chunking/quality question (out of the original 500 scope).
- **(c) GPU throughput / contention** — bge-m3 shares the GPU with always-on gemma4-e4b. Check
  whether throughput is GPU-bound or contention-bound.
- **NOT a lever:** reducing `_EMBED_BATCH` — same total tokens, no throughput gain. (User flagged
  batch-reduction as diagnostic-only anyway.)

## What was RULED OUT during the (wrong) transient hypothesis — for history

The earlier investigation chased a transient slot/KV-cache server bug and ruled out: TTL eviction,
individual-text content, whole-batch payload size, sequential replay in isolation, stale httpx
connections, RAM OOM. All correct findings, but the conclusion (transient, self-recovering) was
wrong — the failure was deterministic. The v0.8.0 wider backoff (0/15/30/60s) built for that
hypothesis is retained only for genuinely transient errors; deterministic 500s now fail-fast/split.

**Lesson (vindicated in the meeting):** capture the actual error body before theorizing. One
`resp.text` read collapsed weeks of the wrong hypothesis.

## State / paths / commands

- Embed state: `zkm doctor` — at pause: embed docs **1796**, schema 3, stale ~53710. Store `~/knowledge`.
- zkm fixes: `src/zkm/embed.py` — `_EMBED_RETRY_SLEEPS`, `_is_too_large_error`,
  `_embed_single_with_split`, `_post_embed_batch`, `_log_embed_stall`; `build_embed_store(timeout=180.0,
  checkpoint_every=100)`. Tags v0.8.0 / v0.9.0 / v0.9.1. **`uv publish` deferred** (no PyPI creds).
- zomni config: `/etc/llama-swap/config.yaml` bge-m3 entry; restart `sudo -A systemctl restart
  llama-swap`; tracked in `~/src/zomni/TODO.md`.
- Stall log lines (`[zkm-embed] ...`) go to stderr — they captured the diagnostic body and any splits.
