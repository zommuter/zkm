# 2026-06-11 — Amender sweep scoped to triggering convert's created files

**Started:** 2026-06-11 10:12
**Session:** 7165c98b-ca52-4a21-923a-b747cf13e891
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Scope amender sweep to the list of files the triggering convert created (id:63bb)

## Context

`zkm convert <plugin>` auto-runs amenders (currently only zkm-ner) after the
primary conversion. The amender's `convert()` swept the **entire store** via
`store_path.rglob("*.md")`, regardless of which files the triggering convert
actually created. So `zkm convert claude-code` re-walked all of `mail/`,
`chat/whatsapp/`, etc., even though only `sessions/claude-code/*.md` were new.

The extraction cache (content-hash keyed) already skips re-running spaCy on
unchanged docs, so this was a performance/scoping issue, not a correctness one.

## Plan

Thread an optional, capability-probed `created: list[Path]` kwarg from the CLI
amender loop down to the amender's `convert()`. Backward-compatible: amenders
that don't declare the parameter are called as before.

Three-layer change:
1. `src/zkm/convert.py` — add `_supports_created()` helper mirroring
   `_supports_progress()`; add `created` param to `run_convert()`; forward
   into `mod.convert()` kwargs when present and supported.
2. `src/zkm/cli.py` — pass `created=created` at the amender call site
   (`cli.py:695`). `created` was already in scope from the primary conversion.
3. `plugins/zkm-ner/src/zkm_ner/convert.py` — change signature to accept
   `created=None`; use `sorted(created)` when provided, `rglob("*.md")` when
   None (explicit `zkm convert ner` path).

**Sweep-scope decision: A — created-only** (chosen at this session).
- Rejected B (created ∪ missing-sidecar): entity-less files never get a sidecar,
  so every such file would be permanently "missing sidecar" → re-walked on every
  convert, eroding the win back toward a full sweep.
- Rejected C (created ∪ cache-stale): detecting cache-staleness requires
  read+hash per file ≈ status quo.
- Straggler files (created while `--no-amenders` or after an amender crash) only
  get NER'd on a later explicit `zkm convert ner`.

## Implementation findings

Changes landed cleanly across three files. `apply_queue(store_path)` at the end
of zkm-ner's `convert()` is intentionally untouched — it drains the pending queue
for the whole store (required for correctness; cheap when no queue files exist).

Tests added:
- Core (`tests/test_plugin.py`): `test_created_forwarded_only_to_plugin_that_declares_it` —
  verifies capability probe: plain plugins (no `created` param) don't receive it
  and don't raise; aware plugins do receive the list.
- zkm-ner (`tests/test_convert.py`): three new tests —
  `test_convert_created_restricts_sweep`, `test_convert_no_created_sweeps_full_store`,
  `test_convert_created_empty_list_processes_nothing`.

All suites pass: 529 core + 284 zkm-ner.

## Decisions

- `run_convert(name, store_path, ..., created=None)` — capability-probed forwarding; no
  breaking change to existing callers.
- `_supports_created()` mirrors `_supports_progress()` — same inspect.signature pattern.
- `apply_queue` scope unchanged — whole-store drain is correct; worth a separate
  optimization only if queue-file count grows large.
- Straggler-miss policy: accepted as-is; forward-flag if observed in practice.

## Action items

- [x] Implement `_supports_created` + `run_convert` `created` param in `src/zkm/convert.py` <!-- id:10a5 -->
- [x] Thread `created=created` at amender call site in `src/zkm/cli.py` <!-- id:10a5 -->
- [x] Update zkm-ner `convert()` signature + sweep selection <!-- id:10a5 -->
- [x] Tests in core + zkm-ner <!-- id:10a5 -->
