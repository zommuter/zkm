# Embed rebuild blocked by recurring 500 — investigation handoff

**Date:** 2026-05-21
**Status:** BLOCKED — embed index rebuild cannot complete; root cause not yet fixed.
**Context:** This started as the E9 follow-up (see `field-test-bge-m3.md` step 7c, `TODO.md`
Phase 2.5 γ section, meeting `docs/meeting-notes/2026-05-21-0816-gamma-schema-gap-audit.md`).

## What E9 actually needs (scope correction)

The TODO premise was **stale**. Live-state audit on 2026-05-21:

- `zkm convert ner` is **redundant** — the mail corpus `entities[]` is already fully populated
  with the γ schema including value types. Histogram: `iban`×367, `amount`×19565,
  `email_address`×14833, `phone_number`×15632, `url`×29840, `registration_code`×2089. The newest
  doc (`mail/messages/2026/05/2026-05-14-1550-...-scandit.md`) carries full `scope`/`standard`/
  `type`/`value` records. The zkm-ner `model_version` (plugins/zkm-ner/src/zkm_ner/version.py:23)
  already includes `iban-v1+email-v1+phone-v1+url-v1+invoice-v1+...`, so a re-run is cache-hits only.
- The genuinely stale artifact is the **dense embed index**. `embeddings-meta.json` is at
  `schema_version: 2`; code (`embed.py:31`) is at `_STORE_SCHEMA_VERSION = 3`. `load_embed_store`
  (embed.py:169) returns `None` on version mismatch ⇒ **full re-embed of all 55506 docs**, not
  incremental. Schema 3 is what adds `entities[].value/canonical` + `participants[].address` to the
  embedded text (E8).
- After the embed rebuild succeeds: run the **7c typed-value probe** (IBAN + amount frontmatter-only
  search) and record results in `field-test-bge-m3.md` step 7.

**So the only remaining E9 work is: complete the embed rebuild, then run 7c.** `convert ner` is out.

## The blocker

`zkm index` (BM25 phase succeeds in ~160–306s, 55493 docs) but the **dense embed phase consistently
fails** with:

```
Dense index failed: embed_texts failed: Server error '500 Internal Server Error'
for url 'http://localhost:8080/v1/embeddings'
```

The `zkm index` process exits 0 anyway (the embed failure is a non-fatal warning in cli.py ~line 801–853).

### Failure signature (confirmed across 4 runs)

- The 500 always fires at the **same absolute position**: after ~27 batches of 32 texts from the
  start of the embed run = **absolute flat-text index ~864–895** (docs around
  `mail/messages/2008/09/2008-09-23-...` onward). Confirmed: run-1 (from scratch) failed at the same
  absolute texts as run-2/3 (which resumed from the 335-doc checkpoint at text 512).
- The 500 response is immediate (~720–750 ms, 161-byte body) — an immediate server-side rejection,
  not a timeout. **The 161-byte error body was never captured — capturing it is the #1 next step.**
- After the failure, the endpoint recovers on its own within ~30–40s (manual curl + keepalive
  succeed). BUT the recovery takes **longer than 15s** — see retry-fix result below.

### Embed checkpoint state (frozen here)

- `embeddings.npz` / `embeddings-meta.json`: **schema_version 3, n_docs 335** (partial checkpoint
  from run-1, saved at ~512 texts via `checkpoint_every=500` in build_embed_store).
- The 335 cached docs span `inbox/first.md` .. `mail/messages/2010/04/2010-04-06-0916-...` (first
  ~1080 docs in sorted order, of which 335 had been embedded when the checkpoint fired).
- BM25: 55493 docs, version 4 (current; 13 perpetually "stale" — likely unparseable, not blocking).

## What was RULED OUT (do not re-investigate)

1. **bge-m3 TTL eviction during BM25 phase** — ruled out. Ran a keepalive loop (`curl bge-m3 every
   60s`) concurrently with `zkm index`; the embed phase still failed at the same point. bge-m3 stays
   loaded (process PID 1228, `ps aux | grep llama-server`).
2. **Specific bad document/chunk content** — ruled out. Tested every one of the 32 texts in the
   failing batch (absolute 864–895) individually via `/v1/embeddings` → all 200. Also tested batches
   352–383 individually.
3. **Whole-batch payload too large** — ruled out. Sent the full 32-text failing batch in one request
   → 200, 32 embeddings. Total batch ~27k chars / ~9k tokens, max single text 2000 chars (~500 tok),
   well under bge-m3's `--ctx-size 8192`.
4. **Sequential replay in isolation** — ruled out. A standalone Python script sending batches 0–13
   sequentially (32 texts each, urllib) → all 200, faster than the live run (3–13s vs 6–20s/batch).
   The failure does NOT reproduce outside the live `zkm index` process.
5. **Stale httpx connection** — unlikely. `build_embed_store` uses a fresh `httpx.post` per batch
   (embed.py ~262), no shared client/pooling.
6. **RAM OOM** — unlikely. `free -h`: 30Gi total, ~7.9Gi available during the run; bge-m3 server RSS
   ~409MB. acc_vecs accumulation is trivial (~MB).

## Fix attempted (committed, did NOT resolve)

**v0.7.1 (commit 6bff48b)**: added a 3-attempt retry loop with 5s/10s sleep around the batch
`httpx.post` in `build_embed_store` (embed.py ~258–289). **Result: all 3 attempts failed** — the
500s fired at 09:51:41, 09:51:47, 09:51:57 (≈6s and 10s apart). So the server stays in the
500-state for **>15s**, longer than the retry window. The retry is still a reasonable safety net but
the backoff is too short for this failure mode.

This means: the recovery window is between 15s (3 retries failed) and ~30–40s (keepalive/manual curl
worked after abort). A longer backoff (e.g. 30s/60s) MIGHT get through, but that's a guess.

## Leading hypothesis

A llama.cpp/llama-server bug or resource limit in **embedding mode** triggered by sustained load:
after ~864 cumulative texts (~27 batches), some internal state (KV-cache slot, sequence counter,
memory pool) overflows; the server returns 500 for ~15–40s, then self-recovers. Not content-specific,
not client-specific — purely a function of cumulative request volume in one server session.

bge-m3 server launch (from `/etc/llama-swap/config.yaml`, machine = zomni):
```
llama-server --port 5801 --host 127.0.0.1 -m .../bge-m3-Q8_0.gguf -ngl 99 \
  --ubatch-size 2048 --ctx-size 8192 --threads 8 --embedding --pooling cls
```

## Next steps (in priority order)

1. **Capture the 161-byte 500 body.** Reproduce the failure (run `zkm index`, or replay ~30 batches
   in a loop against `/v1/embeddings` until it 500s) and print `resp.text`. This likely names the
   root cause (e.g. "failed to decode", "KV cache full", "no slot available"). Until we see it we're
   guessing.
2. **Check llama-server's own stderr/logs** for the bge-m3 process at the moment of the 500 —
   `journalctl` only shows llama-swap's proxy view (`status=500, 161 bytes`). The underlying
   llama-server log will have the real error. May need to find where llama-swap pipes child stderr.
3. **Try a longer retry backoff** (30s/60s) as an empirical test of the recovery-window hypothesis —
   cheap to try, and if it works it unblocks E9 immediately even without root-causing.
4. **Try smaller `_EMBED_BATCH`** (e.g. 8) — reduces per-request token volume; tests whether the
   limit is per-request or cumulative. (If cumulative, this won't help.)
5. **Consider a llama-server config change on zomni** (e.g. add `--no-kv-offload`, raise/lower
   `--ubatch-size`, set `--parallel`/`-np`, or a periodic restart) — this is a **zomni machine-config
   concern**, route to `~/src/zomni/` if it comes to that. Check upstream llama.cpp issues for
   "embeddings 500 after N requests" / KV-cache-not-reset-in-embedding-mode.
6. Once embed completes (`zkm doctor` shows embed docs = md count, schema 3):
   - Run `field-test-bge-m3.md` step 7c: derive a real IBAN prefix from an `entities[].type: iban`
     value (not the placeholder `CH56`), `zkm search "<prefix>" --no-dense -k 5`, verify the top hit
     has the IBAN in `entities[]` but NOT in body; repeat for an `amount`.
   - Record results into the step-7 live-results section of `field-test-bge-m3.md`.
   - Close E9 in `TODO.md`; note the convert-ner-was-redundant finding.

## Useful commands / paths

- State: `zkm doctor` (no `cd` needed; reads `$ZKM_STORE`, defaults to `~/knowledge`).
- Store: `/home/tobias/knowledge`; index dir `~/knowledge/.zkm-index/`.
- Re-run: `zkm index` (BM25 + embed). `--no-embed` = BM25 only. No `--no-bm25` / embed-only flag exists.
- Embed code: `src/zkm/embed.py` — `build_embed_store` (batch loop ~258), `load_embed_store` (~162,
  schema gate ~169), `embed_texts` (~64), `_EMBED_BATCH=32` (~23), `_STORE_SCHEMA_VERSION=3` (~31).
- The dirty-tree guard blocks `zkm index` with uncommitted changes in `src/zkm/`; commit first or
  `ZKM_BYPASS_DIRTY_CHECK=1`.
- Plan file from this session: `/home/tobias/.claude/plans/greedy-dancing-thacker.md`.

## Cleanup done

- Keepalive background loop killed.
- v0.7.1 retry fix committed + tagged (kept — it's a reasonable safety net even though its backoff
  is too short for this specific failure).
