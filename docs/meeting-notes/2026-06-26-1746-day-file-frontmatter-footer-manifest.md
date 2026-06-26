# 2026-06-26 — Day-file frontmatter weight: footer manifest, not sidecar (id:3322)

**Started:** 2026-06-26 17:46
**Session:** b746e44e-53a5-4ff4-877d-55b4f6748e85
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity)
**Topic:** A WhatsApp day-file is ~27+ frontmatter lines (per-message `messages:` manifest) to ~1 body line for short chats — frontmatter dominates. Move the manifest out, and where to?

## Grounding
- `_render_file` (`plugins/zkm-whatsapp/convert.py:442-562`) writes frontmatter+body in one pass. Manifest per message: `key_id/timestamp/sender_jid/status` + conditional `text`, `quoted_key_id`, `media:{mime,sha256}`.
- **w6f (D5, 2026-06-13, `plugins/zkm-whatsapp/ARCHITECTURE.md:106-113`):** inline manifest = rewrite source-of-truth; `text` duplication blessed *conditionally* (WA source ephemeral — no durable original — AND manifest is rewrite truth-source).
- **Self-contained `.md`:** `_reconstitute` (`:1006-1080`) rebuilds messages from the manifest alone (not the DB); CAS media path re-derived from stored sha256.
- **`<md>.amendments.json`** (`zkm.amendments`): frontmatter *field attribution* (tags/entities), multi-producer, queue + `fcntl.flock` apply, values mirrored back to frontmatter.
- **Cross-cutting:** shape shared via `docs/messaging-spec.md`; live in whatsapp **+ telegram** (`plugins/zkm-telegram/convert.py:134-145`); signal/threema are stubs.
- **Spec gap:** `messaging-spec.md:229-237` still documents the pre-w6f minimal manifest (text/quoted_key_id/media undocumented).

## Agenda
1. Is moving the manifest to a sidecar warranted, given the costs?
2. If it moves — where? (dedicated sidecar vs in-document footer)
3. Spec coherence + cross-cutting migration.

## Discussion

### Item 1 — sidecar warranted?
🏗️ Archie: manifest buys 3 load-bearing properties (dedup truth-source / self-contained reconstitution / byte-identical re-emit); w6f put `text` inline because the WA DB is ephemeral. 😈 Riku: a sidecar WORSENS diff signal (split churn), DOUBLES day-file count (worsens the 500k-file working-tree walk re-id'd this session as id:6e13), and relaxing self-contained `.md` reintroduces the pre-w6f blank-on-rewrite bug. ✂️ Petra: short-chat heaviness looked cosmetic, no earned second consumer, blast radius hits live telegram + spec. *Initial persona lean: decline.*

**Zommuter (owner, verbatim):** "don't we already have amender sidecar files anyway? No matter what, the frontmatter is _way_ too long and must be shorter, no more than say ten lines, and not 80 so I have to scroll the screen before even remotely grasping what the message is about at all … if you _really_ insist on in-document, use something at the end instead of frontmatter, but still it's not ideal."

→ DP1 resolved by owner: "accept as-is" off the table. Frontmatter MUST be ~≤10 lines; the unbounded manifest MUST leave the frontmatter. Owner preference: sidecar > in-document-footer.

### Item 2 — where does it go?
🏗️ Archie: owner's right on the sidecar precedent — `<md>.amendments.json` exists per-md whenever an amender emits, and day-files get NER'd, so many already carry one; Riku's "doubling" overstated, conceded. But don't overload amendments.json (field-attribution engine) with message content. Real fork: dedicated `<md>.manifest.json` vs a footer block in the `.md`.

😈 Riku (vote change): the owner's real complaint is *ordering* — "scroll 80 lines before grasping the message." A **footer** fixes that completely (open → ~8 frontmatter lines → transcript → manifest below the fold) AND keeps the three properties a sidecar sacrifices: self-contained `.md` (git-mv/restore-safe), single-file diff, zero new files. The second consumer Riku/Petra demanded *is the human reader* — the premise of a markdown-first store, not a cosmetic nit. Withdraws the decline.

✂️ Petra: footer is also the smaller change — no new resolution path, no missing-sidecar branch, no `zkm rm`/`gc` learning a new sidecar species; `_load_existing_manifest`/`_reconstitute` just move read-locus to an end-of-file `<!-- zkm:manifest … -->` block. `assert_reemit_identical` preserved by construction.

🏗️ Archie (≤10-line caveat): move the *unbounded* `messages:` out; keep `participants:` inline flow-compacted (bounded, glance-worthy "who's here"). Very large groups may run slightly over → participants→footer follow-up if a hard cap is wanted.

→ DP2 resolved (owner): footer now, sidecar-capable seam later.

### Amendment session — why is `amendments.json` a sidecar, if footer is better here?
**Owner:** "what's the reason for using a sidecar there then? Was it that we might have non-md files, even binaries?"

🏗️ Archie: the binary guess isn't the driver — amendment records resolve to an md (`message_id`/`sha256`/`path`) and always write to that md's *frontmatter*; `sha256` is a matching key, not "binaries get amendments." The real reasons are the EXACT INVERSE of the manifest's:
1. **Multi-producer** — contract is "md body single-writer; frontmatter multi-writer." If attribution lived in the `.md`, every amender would rewrite a file OWNED by a different plugin, contending with the body-writer + each other. The sidecar decouples it; per-md flock serialises just the ledger.
2. **Out-of-band / async** — amendments queue (`.zkm-state/amendments/<producer>/…`) drained later by `apply_queue`; can emit before the md exists. The manifest is written in-band, same convert pass as the body.
3. **Machine-only bookkeeping** — sidecar holds `producer_sets` + ref-counts; the human-facing VALUES are mirrored to frontmatter. Nobody reads the ledger.

✂️ Petra → reusable heuristic: **single-producer + in-band + primary data → in-document; multi-producer + out-of-band + machine bookkeeping (values mirrored to frontmatter) → sidecar.** Manifest-in-document and amendments-sidecar are CONSISTENT under it. 😈 Riku: write it down so the next plugin author doesn't relitigate.

→ Owner ratified: record the heuristic in docs; participants stay inline flow-compacted.

## Decisions
- **D1 — Frontmatter must shrink to ~≤10 lines (owner mandate, overrides w6f "manifest in frontmatter").** The unbounded per-message `messages:` manifest leaves the frontmatter. *Out of scope:* changing the manifest field SET — `text`/`quoted_key_id`/`media` stay (w6f's ephemeral-source rationale holds).
- **D2 — Manifest moves to an END-OF-FILE footer block in the SAME `.md`, not a sidecar.** Format: `<!-- zkm:manifest\n<yaml>\n-->` after the transcript — machine-parseable, deterministic key order, invisible when rendered. Keeps self-contained `.md`, single-file diff, zero new files, byte-identical re-emit. *Out of scope:* a dedicated `<md>.manifest.json` sidecar — deferred behind a documented seam; revisit only if a real external manifest-query consumer earns it.
- **D3 — Frontmatter retains light fields + `participants:` inline, flow-compacted.** Keep `source/date/tags/thread_id/chat_jid/chat_name?/processor/processor_version` + flow-style `participants:`. *Out of scope:* moving participants out — revisit only if a hard ≤10 cap is wanted for very large groups.
- **D4 — Sidecar-vs-in-document heuristic recorded as a durable principle** in `docs/object-storage.md` (+ cross-ref `messaging-spec.md`): single-producer + in-band + primary → in-document; multi-producer + out-of-band + bookkeeping (values mirrored to frontmatter) → sidecar.
- **D5 — Close the messaging-spec gap.** Update `messaging-spec.md:229-237` to document the footer layout + the shipped `text`/`quoted_key_id`/`media` fields.
- **D6 — Cross-cutting migration.** zkm-telegram (live) migrates to the same footer; signal/threema stubs inherit via spec. `_load_existing_manifest` reads the footer with frontmatter fallback for pre-change files (one-pass heal on next rewrite). w6f reconstitution + `assert_reemit_identical` preserved.

## Action items
- [ ] [zkm-whatsapp / W] Move `messages:` manifest from frontmatter → end-of-file `<!-- zkm:manifest … -->` footer in `_render_file` (`plugins/zkm-whatsapp/convert.py:442-562`); update `_load_existing_manifest` (`:411-440`) + `_reconstitute` (`:1006-1080`) to read the footer with frontmatter fallback (pre-change heal). Flow-compact `participants:`. Contract: a short-chat day-file ≤10 frontmatter lines; `assert_reemit_identical` green; reconstitution lossless from footer-only; pre-change file heals on rewrite without data loss. See this note. <!-- id:767e -->
- [ ] [zkm-telegram] Mirror the footer migration in `_render_day_file` (`plugins/zkm-telegram/convert.py:110+`, manifest `:134-145`). Contract: telegram day-file ≤10 frontmatter lines; reemit-identical. See this note. <!-- id:ac55 -->
- [ ] [core docs] `docs/messaging-spec.md`: replace the minimal-manifest schema (`:229-237`) with the footer layout + document the w6f `text`/`quoted_key_id`/`media` fields (D5 spec gap). See this note. <!-- id:2b0b -->
- [ ] [core docs] `docs/object-storage.md`: add the sidecar-vs-in-document heuristic (D4) + cross-ref from `messaging-spec.md`. See this note. <!-- id:68fc -->
- [ ] [core] Spec/conformance note that the per-chat-day footer-manifest layout is the `messaging-spec.md` contract signal/threema stubs must inherit (footer, not the old frontmatter shape). See this note. <!-- id:03ae -->

## Verification
- `cd plugins/zkm-whatsapp && uv run pytest -k 'rewrite or reemit or render'` — reconstitution + byte-identical re-emit green.
- Synthetic short chat: render → assert frontmatter ≤10 lines and the footer round-trips losslessly.
- Pre-change day-file fixture (manifest in frontmatter): re-convert → assert heals to footer with zero message loss.
- `cd plugins/zkm-telegram && uv run pytest` — telegram reemit-identical.
- Core suite green (529+).
