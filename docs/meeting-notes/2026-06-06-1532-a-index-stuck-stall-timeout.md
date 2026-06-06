# 2026-06-06 — A-index-stuck: embed stall-timeout

**Started:** 2026-06-06 15:32
**Session:** 808ac56b-9b3e-4900-bf86-866b0fd6c688
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Add a dead-man's stall timeout to `zkm index` embed phase to prevent 8+ hour hangs caused by the bge-m3 persistent-500 (500-wall) state.

## Context

On 2026-06-01 a `zkm index` run (pid 6888) hung for 8+ hours in the embed phase. Root cause: the known bge-m3 embed server "500-wall" — the server starts returning 500s at a fixed absolute text position, and every subsequent batch exhausts all 5 retry attempts (summing ~1125 s per batch) before being skipped. Across hundreds of batches this runs effectively forever. `TODO.md` item `A-index-stuck <!-- id:141a -->`.

## Plan

A **stall timeout** — not a total wall-clock deadline — is the correct mechanism. A total deadline would kill a healthy full rebuild (legitimately 12+ hours with steady progress). A stall timeout (time since last *successful* batch) distinguishes the 500-wall grind (zero successes) from a slow-but-healthy run (timer resets every ~75–100 s on each success).

Default 1800 s (30 min): a recovering batch succeeds within the ~225 s retry ladder; 30 min of zero successes unambiguously indicates a wedged server. Configurable via `embed.stall_timeout` in `zkm-config.yaml` or `ZKM_EMBED_STALL_TIMEOUT` env var; `0` disables.

Files touched:
- `src/zkm/config.py` — add `stall_timeout: 1800.0` to `_CORE_DEFAULTS["embed"]` and `ZKM_EMBED_STALL_TIMEOUT` to `_ENV_KEY_MAP` (mirrors `expand.timeout` precedent)
- `src/zkm/embed.py` — extend `resolve_embed_config` return type to 4-tuple `(endpoint, model, key, stall_timeout)`; add `stall_timeout` param to `build_embed_store`; add `_check_stall()` inner function; check at top of each batch and after each failed batch; reset `last_success = time.monotonic()` on each successful batch
- `src/zkm/cli.py` — unpack 4-tuple from `resolve_embed_config`, pass `stall_timeout` to `build_embed_store`; fix second `resolve_embed_config` call site (`cmd_info`)
- `src/zkm/query.py` — fix two `resolve_embed_config` call sites (return 4-tuple)

## Implementation findings

- Three `resolve_embed_config` call sites required updating: `cli.py` (two), `query.py` (two), and one test mock in `test_query_recall.py`.
- Stall check position matters: checking only at the top of each batch (before first attempt) misses the single-batch case. Added a second check after `last_exc is not None` (after all retries exhausted) so the abort fires immediately after the failure.
- Test uses `patch("zkm.embed.time.monotonic", side_effect=[0.0, 0.001, 9999.0])` to simulate the three monotonic calls in the stall path: init, top-of-loop check (don't fire), after-failure check (fire).

## Decisions

- Stall timeout = 1800 s default; configurable; `0` disables.
- Check fires at (a) top of each batch iteration and (b) after all retries exhausted per batch. Both are needed to handle single-batch and multi-batch corpus sizes.
- `EmbedUnavailable` is raised on stall — already caught by CLI (`cli.py:950–953`) as a graceful exit. Checkpoints already on disk so next `zkm index` resumes from partial progress.
- Out of scope: server-side 500-wall root cause (routes to `~/src/zomni/`); watchdog thread (unnecessary given bounded httpx timeouts).

## Action items

- [x] Close `A-index-stuck <!-- id:141a -->` in `TODO.md` — done in this session.
