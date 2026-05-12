# 2026-05-12 — zkm status ETA column

**Started:** 2026-05-12 14:41
**Session:** 7349b898-9516-440a-a4fc-1f249401329c
**Mode:** Class 1 dispatch (impl-ready — no plan mode, no meeting)
**Topic:** Add ETA column to `zkm status` output and ETA field to the PID file schema.

## Context

TODO item carried since the SIGUSR1 meeting (2026-05-08-1913-sigusr1-status.md). Picked from the Class 1 bucket in a no-arg `/meeting` audit on 2026-05-12.

## Plan

- `RunSession`: add `eta_seconds` field + phase-relative `_phase_start_time`; `tick()` accepts optional `eta_seconds` kwarg (caller forward hook); fallback computes `elapsed / current * remaining` from phase start; `set_phase()` resets ETA + phase timer; SIGUSR1 handler emits `ETA ~Xm00s` / `~Xs`; `_payload()` includes `eta_seconds`.
- `cli.py`: `cmd_status` header adds `ETA` column, row shows `~Xm` or `~Xs`, suppressed when `eta_seconds is None` or `current == 0`. Progress callbacks unchanged (session.tick first; tqdm-first restructuring was attempted but Pyright cannot narrow `bar: tqdm | None` through nonlocal closure mutations — see discoveries.md 2026-05-12).
- Tests: 7 new tests in `test_runstate.py` covering caller override, fallback computation, current-zero suppression, payload key, set_phase clear, SIGUSR1 with ETA, SIGUSR1 without ETA.

## Decisions

- ETA is **phase-relative** (`_phase_start_time` resets on `set_phase()`) — avoids carry-over from BM25 phase polluting the embed-phase ETA.
- `eta_seconds` kwarg exists as a **forward hook** for callers that have a better (tqdm-smoothed) ETA; current progress_cb callers don't use it — internal fallback is sufficient.
- Suppress ETA when `current == 0` (no rate data yet) or `eta_seconds is None`.
- Out of scope: `zkm status --follow` watch mode; tqdm ETA forwarding from progress_cb (Pyright issue; deferred).

## Action items

- [x] `src/zkm/runstate.py` — ETA field, phase timer, tick kwarg, SIGUSR1 update
- [x] `src/zkm/cli.py` — ETA column in `cmd_status`
- [x] `tests/test_runstate.py` — 7 new ETA tests (350 core tests passing)
- [x] `TODO.md` — item marked done
