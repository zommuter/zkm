# 2026-06-03 — zkm-vcard hardening series V1–V5

**Started:** 2026-06-03 16:03
**Session:** 2c8efdbd-9810-4a4d-bc40-2ff16d2f3cca
**Mode:** Class 2 planning record (no meeting was held — plan-mode output)
**Topic:** Triage and implement spec-compliance gaps in zkm-vcard v0.1.0

## Context

No-arg `/meeting` picked "zkm-vcard V-tasks" as a Class 2 item. Exploration found the plugin already shipped v0.1.0 (tagged, 23 tests, `id:e5f9` closed). The TODO.md vcard section held only scope-prose and one bookkeeping item (`id:2638`). Exploration surfaced 8 spec-vs-impl gaps; 3 were dropped as correctly deferred; 5 became the V-series.

## Plan

**Triage of the 8 gaps:**

| # | Gap | Disposition |
|---|-----|-------------|
| 1 | `decode("utf-8", errors="replace")` in `_iter_vcards` — silently corrupts legacy latin1 | **V1** |
| 2 | Local `_canon_email`/`_canon_phone` duplicate `zkm.canonical` | **V2** |
| 3 | No `reprocess()` — no path to re-derive from originals after extractors improve | **V3** |
| 4 | `scope: contact` not in `entity-model.md` scope table | **V4** |
| 5 | `except Exception: pass` hides dropped vCards | **V5** |
| 6 | No `scrub()` | Dropped — structured-first contacts have no NER-pollution to sweep |
| 7 | No `.zkm-state` watermark | Dropped — observe-before-preventing; contact N is small |
| 8 | No inbox `.origin.json` | Dropped — correctly absent per spec §274 |

**Sequencing:** V4 + V2 (warm-ups, no core change) → V1 (new `zkm.encoding` module, N=2 with eml) → V3 (reprocess, benefits from V1/V2) → V5 (independent robustness).

**N=2 abstraction decision for V1:** zkm-eml was already using ftfy + charset-normalizer in `parse.py::_post_decode`. vcard is the 2nd consumer → extract to `src/zkm/encoding.py` with `decode_bytes()` and `post_decode()`. eml repoints `_post_decode` to `zkm.encoding.post_decode`.

## Implementation findings

- `zkm.canonical.email` is identical to the old `_canon_email` — safe drop.
- `zkm.canonical.phone` is naive strip-only; `_canon_phone` does real E.164 validation via `phonenumbers`. Kept `_canon_phone` as primary, added `canonical_phone_basic` as fallback when `phonenumbers` absent.
- latin1 detection via charset-normalizer requires enough European text (ö/ü/ä/ß) to disambiguate from CJK. Short blocks (< ~100 chars) are unreliable. Test fixture uses a multi-field German vCard.
- eml's pre-existing test failure (`test_slugify_ascii_fold_when_env_set`) confirmed pre-existing, unrelated to these changes.
- `reprocess()` uses inline `_merge_entities()` (avoid `zkm.amendments` coupling for a simple dedup).

## Decisions

- `zkm.encoding.decode_bytes` is the canonical bytes→str helper for plugins; plugins import it from core.
- `post_decode` is a public function (shared); `decode_bytes` is the full chain.
- `_canon_phone` keeps phonenumbers as primary; falls back to `zkm.canonical.phone` basic strip when absent (was returning `None` before).
- `reprocess()` scope: replaces `scope: contact` entity records; preserves all other scopes, tags, and body-level metadata.
- Failure count surfaced via `sys.stderr` only (not progress callback, since total is unknown until loop ends).
- Out of scope: `scrub()`, watermark, inbox integration, identity-merge.

## Action items

None — all items resolved in-session. Class 2 dispatch; no TODO.md items survive this session.
