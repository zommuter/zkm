# 2026-06-05 — C1: zkm-calendar plugin build

**Started:** 2026-06-05 13:00
**Session:** 60295232-f9df-4f0e-984b-b7c6648b6c4a
**Mode:** Class 1 dispatch (design already decided in 2026-06-01-1334-contacts-calendar-plugins.md — no meeting held; direct implementation)
**Topic:** Build the zkm-calendar ingest-only plugin (gate fired: zkm-vcard v0.3.0 shipped)

## Context

TODO item C1 (`<!-- id:cca0 -->`) — create `plugins/zkm-calendar/`: VEVENT→message-like md,
dedup-on-UID, participants[], ATTACH→CAS, standards-parser only.
Gate condition: zkm-vcard ships (build order vcard → calendar). Gate fired 2026-06-03 (vcard v0.3.0).

Design decisions from 2026-06-01-1334 meeting (Decision 4) carried forward plus three
forks decided in this session:
- **Parser: icalendar** (better VTIMEZONE/RRULE/tz than vobject)
- **Thread index files: deferred** (RRULE not expanded → threads are singletons in v1)
- **entities[]: populated scope:event** (structured-first recipe, mirrors vcard)

## Plan

Mirrored `plugins/zkm-vcard/` structure exactly:
- Single-module `convert.py` + `plugin.yaml` + `pyproject.toml`
- Own git repo under `plugins/zkm-calendar/` (parent `.gitignore` covers `plugins/`)
- Core helpers: `zkm.atomic.write_atomic`, `zkm.cas.write_object`, `zkm.encoding.decode_bytes`,
  `zkm.canonical.email`, `zkm.canonical.iso8601`
- Frontmatter: base contract (`source`/`date`/`tags`/`sha256`/`original`/`processor`/
  `processor_version`) + messaging extension (`message_id`/`thread_id`/`participants`)
- `entities[]` scope:event — `email_address` (rfc5321), `person` (CN), `place` (LOCATION)
- `reprocess()` — re-derives body + scope:event, preserves foreign scope:body + tags
- 40 unit + integration tests; `zkm test calendar` conformance (manifest + interface + dynamic)

## Implementation findings

- `icalendar` library (v7.1.2 installed) handles VTIMEZONE correctly; `vevent.get("DTSTART").dt`
  returns a tz-aware `datetime` when TZID is set, naive `datetime` for floating, or `date`
  for all-day. All three paths produce conformance-passing tz-aware ISO 8601 dates.
- Multiple ATTENDEEs: `vevent.get("ATTENDEE")` returns a list when >1, single value when =1.
  Guard with `if not isinstance(attendees_raw, list): attendees_raw = [attendees_raw]`.
- `standard` field: wrote it unconditionally for email_address (even when canonical == value)
  so consumers always know the normalization contract. Differs from vcard's "standard only with
  canonical" convention — noted in CLAUDE.md.
- `vevent.to_ical()` gives deterministic re-serialized VEVENT bytes for the archived original
  and sha256 computation. Idempotency confirmed by test.

## Decisions

1. **icalendar library** for parsing (not vobject); better TZ/RRULE handling for calendar data.
2. **Thread index files deferred** (C3, `<!-- id:9fb8 -->`): emit messaging frontmatter that
   satisfies conformance; skip generating `calendar/threads/*.md` until RRULE expansion or
   retrieval pain surfaces. Out of scope: any thread-index generation.
3. **entities[] always populated** (scope:event): email_address + person + place extracted from
   ORGANIZER/ATTENDEE/LOCATION. `standard: rfc5321` written unconditionally for email_address.
4. **store_timezone config** (optional, default `Europe/Zurich`): used for floating/all-day events.

## Action items

- [x] `plugins/zkm-calendar/` repo: initial commit, tag v0.1.0. 40 tests pass, `zkm test calendar` ✓. <!-- id:cca0 --> (marks C1 done)
- [ ] **C3 (deferred): calendar thread-index files** — `calendar/threads/<thread_id>.md`. Trigger: RRULE override instances ingested OR retrieval pain with per-series queries. See TODO.md. <!-- id:9fb8 -->
