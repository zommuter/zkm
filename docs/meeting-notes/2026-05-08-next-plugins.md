# 2026-05-08 — Most sensible next plugins, and what they force on core

**Attendees:** Tobias (product owner), Archie (architect), Riku (devil's advocate), Petra (productivity)
**Topic:** Pick the next 1–3 plugins to build, sort by implementation simplicity, and name any core capability the choice exposes as missing.

## Agenda

1. Sort the plugin shortlist by implementation effort.
2. Resolve the pdf / photo / scan(OCR) content overlap — do they collide, chain, or fan out?
3. Decide whether a plugin dependency tree / pipeline mechanism is needed now or is overengineering.
4. Per chosen plugin: name the core gap (if any) it forces.
5. Pick the order; explicitly defer the rest.

## Discussion

**Tobias:** I have four plugins on the realistic shortlist — `zkm-photo`, `zkm-pdf`, `zkm-scan` (OCR), `zkm-whatsapp`. I can't prioritize. Sort by simplicity so we have more reference plugins to stress-test the contract, and tell me whether the photo/pdf/scan overlap needs a dependency-tree story or whether that's overengineering.

**Archie:** Effort ordering, with what each forces on core:

| Plugin | LOC est. | New core capability needed | Key risk |
|---|---|---|---|
| `zkm-photo` | ~150 | None — pure consumer of `zkm.cas` + `zkm.sidecar` + `zkm.atomic` + `zkm.hashing` | EXIF tooling choice (`exifread` pure-Python vs `exiftool` subprocess) |
| `zkm-pdf` (text PDFs only) | ~250 | None — same shape as photo, plus `pdfplumber`/`pypdf` text extraction | Pages with mixed text+image; encrypted PDFs |
| `zkm-scan` (OCR) | ~400 | None *new*, but exercises long-running `progress` callback under tesseract subprocess for the first time in anger | Tesseract install footprint; per-page vs per-doc md |
| `zkm-whatsapp` | ~700+ | **Three gaps**: (a) non-git source state/watermark — eml's `state.py` watermark assumes source is a git repo (`zkm-eml/src/zkm_eml/state.py`); (b) per-store YAML/JSON config — eml's TODO.md flags long comma-separated env vars as a pain point that gets worse with multi-account messaging; (c) synthesized stable IDs — WhatsApp has no `Message-ID` equivalent | crypt14/15 decryption; multi-database/device merging; schema reverse-eng |

So the cheap-to-build group (photo, pdf-text, scan) needs zero core changes. WhatsApp is the one that punctures core.

**Riku:** Two challenges. First, "needs zero core changes" is suspicious — eml is the only production plugin. If photo needs nothing new, that's evidence the libraries generalize, not proof. Build it and find out. Second, on simplicity ordering: are you sure pdf is harder than photo? Both are "binary in → md+sidecar out." pdf has the parsing burden but no metadata-tooling-choice debate.

**Archie:** Photo has a smaller surface than I was crediting — EXIF read is one library call, schema is fixed. PDF has a real surface: text extraction is an active battle (`pypdf` vs `pdfplumber` vs `pymupdf`, each with different licensing and quality trade-offs). I'll concede the order is photo → pdf, but pdf is genuinely harder, not just longer.

**Petra:** Stop. Apply N=2 to anything we're tempted to extract. What does photo need that isn't in `zkm.{atomic,cas,sidecar,inbox,hashing}`?

**Archie:** Nothing. It writes `photos/YYYY/MM/<datetime>-<slug>.md`, drops the original via `zkm.cas.write_object`, writes a sidecar with `zkm.sidecar.merge_producer`, deduplicates by sha256. The EXIF date supplies frontmatter `date`. Tags from camera model + GPS lookup later (defer GPS).

**Petra:** Then there's no abstraction to extract. Build it. If three plugins later we see a pattern repeated thrice, we extract.

**Tobias:** The overlap question. A scanned PDF, a JPEG of a receipt, and a "real" vacation photo — three plugins might claim the same file. What's the policy?

**Riku:** "Plugins might collide" is not a problem unless plugins *do* collide. Today eml is the only writer; the future plugins write to disjoint dirs (`photos/`, `documents/`, `scans/`). The overlap is a *content classification* question, not a plugin coordination question. Don't conflate.

**Archie:** Three handling options:

1. **Single-producer routing** — core (or a triage plugin) classifies each `inbox/` item and dispatches to exactly one downstream plugin. Adds a content-classifier to core. New abstraction. **N=1 today.**
2. **Fan-out, plugins self-gate** — every plugin scans all of `inbox/`, decides whether to emit md based on content. Photo always emits if EXIF is present. Scan emits only if tesseract finds text above a confidence threshold. PDF emits for `application/pdf` only. The CAS dedupes the binary; the sidecar's `producers[]` already lists every md that points at the object. **No new core machinery.**
3. **Pipeline / dependency tree** — plugins declare consumer relationships (`zkm-pdf consumes inbox/scans/`). Core orchestrates ordering. New abstraction, new config, new failure modes.

**Riku:** Option 3 is the "dependency tree" question. It's overengineering today. The argument for it is "what if zkm-scan should run before zkm-pdf for image-based PDFs?" Counter: zkm-pdf reads PDFs and decides per-page whether text extraction succeeded; if not, it can either skip (and zkm-scan picks up the image) or call out to OCR itself. Either way it's the plugin's call, not core's.

**Petra:** N=2 on dependency-tree machinery: name two pairs of plugins that need declarative ordering, where ad-hoc "run them in any order, idempotently" doesn't already work. Today: zero pairs. Defer.

**Archie:** Option 2 is the answer. Plugins fan out, gate themselves, dedup via CAS. The contract change is small: `docs/plugin-spec.md` should add an explicit rule — *"a plugin MUST be safe (no-op, no error) when run against `inbox/` items it does not own."* That's already implicit in the eml/notes design; making it explicit unblocks the fan-out pattern.

**Tobias:** What about the pdf/scan boundary specifically? A scanned PDF is image-based; a text PDF is text-based. Same extension.

**Archie:** zkm-pdf tries text extraction first. If the page has < N characters of extractable text, it leaves the page (or the whole doc) for zkm-scan to handle. zkm-scan reads the same file via OCR. They both write md (or one of them skips). The producer list in the CAS sidecar accommodates both.

**Riku:** That's two plugins writing two md files for one source PDF. Is that wanted, or is it noise?

**Archie:** It's *correct*. The text-extracted md captures what `pdfplumber` got. The OCR md captures what tesseract got. They're different views; for a hybrid PDF with text + scanned-page mix, both are useful. Search ranks them; the user clicks through.

**Petra:** Acceptable if it falls out for free. If it requires special-casing in either plugin to coordinate, we've leaked into option 3.

**Riku:** And the photo/scan overlap? A JPEG receipt is "scan content" and "has EXIF."

**Archie:** Both run. Photo writes `photos/.../YYYY-MM-DD-receipt.md` with EXIF + thumbnail link. Scan writes `scans/.../YYYY-MM-DD-receipt.md` with OCR text. The CAS holds one binary; both md files reference it via the sidecar. The user finds either via search.

**Tobias:** What about whatsapp? You said it punctures core in three places.

**Archie:** Yes. If we want it next, we need a separate scoping meeting first — at minimum to decide:
- **State mechanism**: a `.zkm-state/<plugin>.json` watermark format that's source-agnostic (last-imported timestamp, message-id set, or both). eml's `state.py` already has the right shape but is git-blob-watermark-specific. Before whatsapp we need to decide whether core publishes a reusable `zkm.state` helper or each plugin rolls its own.
- **Config**: per-store `<store>/.zkm/<plugin>.yaml` or stay on `.env` keys. The eml TODO.md explicitly flags long comma-separated env vars (`EML_FOLDERS_EXCLUDE` etc.) as a pain point that gets acute with multi-account messaging.
- **Stable ID synthesis contract**: when no native stable ID exists, what's the canonical sha256 input? Probably `sha256(canonicalized_payload_bytes)` with a per-plugin canonicalization function — but that contract belongs in `docs/plugin-spec.md` before whatsapp ships.

That's a session of design, not a session of plumbing.

**Petra:** So defer whatsapp to a Phase 2.5 scoping meeting, ship the cheap three first to harden the contract, then come back with whatsapp armed with what those three taught us. Three more in-anger plugins is the strongest possible input to the whatsapp design.

**Riku:** Counter — what if the cheap three teach us nothing because they're all "binary + sidecar md," same as eml? Then we shipped three plugins and learned zero about whatsapp's actual gaps.

**Archie:** They teach us at least one thing: whether `zkm.{atomic,cas,sidecar,inbox,hashing}` survives use by plugins that aren't email. If photo or pdf needs to bend the helpers, that's data. If they don't, that's confidence. Either outcome informs whatsapp.

**Tobias:** Order: photo → pdf-text → scan → (scoping meeting) → whatsapp. Are there core changes to land *before* photo, or is the contract already good?

**Archie:** Two pre-flight items, both small:
1. Add the explicit "MUST be safe on inbox items it does not own" rule to `docs/plugin-spec.md`. One paragraph.
2. Confirm in `docs/object-storage.md` that a single CAS object MAY list multiple different processor names in `producers[]`. eml uses `zkm-eml`; photo would use `zkm-photo`. The dedup key is the producer source-content sha256, which is fine, but the *semantics* of two distinct processor names pointing at one object need a sentence in the spec — otherwise it looks like a bug.

Anything else (per-store config, non-git state, ID synthesis) waits for whatsapp's scoping meeting.

**Petra:** Out of scope for this meeting and the three plugins it greenlights:
- Plugin dependency trees / pipeline orchestration.
- A core content-classifier / triage plugin.
- A `zkm watch` daemon. The mbsync post-commit hook (TODO.md backlog) is a separate, smaller item.
- WhatsApp / Threema / Signal / Telegram / Instagram / Facebook / LinkedIn / Diary / Chatlog plugins.
- GPS reverse-geocoding for photos (Phase 3 NER-adjacent).
- Per-page md vs per-doc md for scans — pick per-doc by default, revisit only if a real query fails because of it.

## Decisions

- **Order:** `zkm-photo` first, `zkm-pdf` (text-only) second, `zkm-scan` (OCR) third. Then a scoping meeting before `zkm-whatsapp`.
- **Overlap policy: fan-out, plugins self-gate.** Every plugin scans `inbox/`, decides whether to emit md based on content type / extraction success, dedupes binaries via CAS, lists itself in `producers[]`. No central classifier; no dependency tree.
- **Plugin-spec contract addition:** plugins MUST be no-ops (return `[]`, no error) when run against `inbox/` items they do not own. Land in `docs/plugin-spec.md` before `zkm-photo`.
- **Object-storage clarification:** a single CAS object MAY have multiple producer-plugin names in `producers[]`; this is normal and expected when pdf and scan both process the same binary. Land in `docs/object-storage.md` before `zkm-photo`.
- **Per-doc md for OCR**, not per-page. Re-open only if a real query fails because of it.
- **Plugin dependency-tree machinery deferred** by N=2 rule — zero pairs of plugins today need declarative ordering; idempotent fan-out covers all current cases.
- **WhatsApp deferred** to a dedicated scoping meeting that addresses (a) non-git source state / `zkm.state` helper question, (b) per-store config replacing long env-var lists, (c) stable-ID synthesis contract.
- **Out of scope** (named, with reasons) — see Petra's list above.

## Action items

- [ ] Session 9a (pre-flight): add the "no-op on unowned inbox items" rule to `docs/plugin-spec.md`. Contract: a plugin run against an inbox containing only items from another plugin exits 0 with `[]` written paths. (file: `docs/plugin-spec.md`, ~1 paragraph)
- [ ] Session 9b (pre-flight): add a paragraph to `docs/object-storage.md` confirming multi-producer-plugin sidecars are normal. Contract: round-trip test where photo and scan both produce against the same CAS object and `producers[]` lists both. (file: `docs/object-storage.md`)
- [ ] Session 10: build `zkm-photo` as a separate repo (`~/src/zkm-photo/`). Contract: `convert(store, {PHOTO_SOURCE_DIR}) -> [photos/...md]`; idempotent; uses only `zkm.atomic|cas|sidecar|inbox|hashing`; `creates_dirs: [photos, originals/photos]`; running twice on the same source produces zero new files.
- [ ] Session 11: build `zkm-pdf` (text-only). Contract: emits md only when text extraction yields ≥ N characters; silently skips otherwise; a test confirms a scanned-only PDF produces `[]` and is left untouched for `zkm-scan`.
- [ ] Session 12: build `zkm-scan`. Contract: per-doc md; tesseract subprocess wrapped in a `progress` reporter; cancellable mid-OCR via the cancellation contract (`docs/plugin-spec.md:121-146`).
- [ ] Session 13 (scoping, not implementation): meeting on the three core gaps `zkm-whatsapp` exposes — non-git source state, per-store YAML config, stable-ID synthesis contract. Deliverable: `docs/meeting-notes/YYYY-MM-DD-whatsapp-scope.md` with decisions on each plus a TODO.md update.
- [ ] Update `docs/meeting-notes/meeting-style.md` "Past meetings" index.
- [ ] TODO.md: add Phase 2.5 sessions 9–13; mark whatsapp as scoping-required.
