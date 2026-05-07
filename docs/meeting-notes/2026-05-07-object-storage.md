# 2026-05-07 — Object storage in zkm core: scope and sequencing

**Attendees:** Tobias (product owner), Architect, Riku (devil's advocate), Productivity expert
**Topic:** Sidecar duplication bug in `zkm-eml`; whether zkm core should own object storage / dedup / sidecars; scope of Phase 2.

## Agenda

1. The duplication bug — what's actually breaking
2. Should core own object storage / sidecars / dedup?
3. Scope guard — what do we explicitly *not* build
4. Sequencing for daily-usable + publishable

## Discussion

**Tobias:** zkm-eml's `.origin.json` sidecars in `inbox/` accumulate duplicate `producers[]` entries on rescan. I want to know whether the fix is plugin-side or whether core should own sidecars, dedup, CAS — and whether sidecars should list pointed-by locations. And I'm asking myself if a general "core can add/edit/remove store contents" API would help.

**Architect:** Two issues, not one. Proximate bug first: zkm-eml dedupes producer entries on the rendered `.md` path. That path shifts whenever the upstream Message-ID is synthesized from headers — header churn between runs creates a new ID, a new filename, a new producer entry that the merge logic doesn't coalesce. Dedup on the producer's source-content `sha256` instead. That's stable.

**Productivity expert:** The bug is bleeding daily. Hot-fix it in zkm-eml, with a regression test that survives the later refactor. Don't let the architecture conversation block a one-day fix.

**Tobias:** Agreed. Bug first.

**Riku:** Before we get to "core owns object storage" — why does zkm have a CAS at all? Git is content-addressed.

**Architect:** Because git-annex / git-lfs externalize the bytes. The CAS path stays valid regardless of where the bytes physically live. The date-sharded inbox symlinks then let downstream plugins read the inbox without knowing about CAS. Both reasons need to land in `docs/object-storage.md` — they'll get questioned again in six months.

**Riku:** Library in core for sidecars and CAS — one plugin uses this today. That's N=1 abstraction.

**Architect:** N=2. The sidecar merge logic was about to be reimplemented in zkm-pdf and zkm-photo, both of which are on the near-term list. The atomic-write helper is N=2 already — zkm-notes violates the spec today by not writing atomically. Each helper has a named second consumer. Without that, I'd defer too.

**Tobias:** What about a "core handles add/edit/remove of store contents" API? Plugins call `zkm.store.put(...)` and core decides paths, sidecars, CAS.

**Riku:** Veto. That turns zkm into a filesystem manager. Every plugin loses control over its own naming and layout, and every change requires touching core. It's a centralization trap.

**Architect:** Concur. Library helpers — atomic, hashing, CAS, sidecar, inbox — yes. A managed `put()` API — no. Plugins keep writing their own files; they just import small, well-tested helpers.

**Productivity expert:** Test for every helper: what's the *second* plugin that needs it? If you can't name one, defer.

- Atomic write → every plugin (zkm-notes is broken without it).
- Sidecar merge → zkm-pdf, zkm-photo.
- CAS object writer → same.
- Symlink-with-sidecar → same.
- `zkm.store.put()` → can't name a second use that wouldn't be served by the smaller helpers. Defer.

**Tobias:** What about `zkm rm` and `zkm gc`? I delete wrong-tagged emails and rotate plugins. I'll need both.

**Architect:** Belong in core, not in any single plugin. A per-plugin `rm` can't safely delete a CAS object that another plugin's producer still references. Cross-plugin coordination is exactly what core is for.

**Riku:** Gate them behind real use. Land the library, migrate the plugins, use them for a week, *then* design the commands. Otherwise you're building CLI ergonomics against an imagined workflow.

**Tobias:** Agreed — session 5 happens after a week of session 4 in anger.

**Productivity expert:** What's "publishable for customers"?

**Tobias:** Someone who isn't me installs zkm and uses it without me on call.

**Productivity expert:** Then the bar is concrete: (a) zero data loss on rescan; (b) round-trip `init → plugin add → convert → search` in under 5 minutes from the README on a fresh machine; (c) one external user installs and reports it usable. Not feature count. Note that (a) and (b) are already in reach after sessions 1–2.

**Riku:** Coming back to Tobias's original question — "should sidecars list pointed-by locations"?

**Architect:** They already do. `producers[]` is exactly that, with the symlink as the canonical pointer. The user is asking the right question; the spec already says yes. The reason it doesn't *feel* answered is that every plugin reimplements the protocol, so the answer isn't visible. Surfacing it in `docs/object-storage.md` is the deliverable.

**Tobias:** Symlinks vs. real files for the inbox entry?

**Architect:** Keep symlinks. `find inbox/` gives you a working filesystem; downstream tools read inbox without knowing CAS exists. The sidecar carries the metadata.

**Productivity expert:** Last rabbit-hole watch: NER / entity extraction / WebUI. Phase 3, not Phase 2. Phase 2 is dedup-correctness + library + hygiene, full stop.

**Tobias:** Agreed. Document them as out-of-scope with reasons, not just absent.

## Decisions

- **Producer-dedup invariant:** dedup on producer's source-content `sha256`, not on the rendered message path.
- **Phase 2 scope:** library helpers (`zkm.atomic`, `zkm.hashing`, `zkm.cas`, `zkm.sidecar`, `zkm.inbox`) + hygiene commands (`zkm rm`, `zkm gc`). Explicitly **not** a managed `zkm.store.put()` API.
- **CAS is for binary content only.** `.eml` and `.md` are not CAS-stored.
- **Symlinks stay** as the canonical inbox entry; sidecar is the metadata layer.
- **`producers[]` already answers "should sidecars list pointed-by locations".** Document it; don't redesign.
- **Hygiene commands gated** on one week of real use of migrated plugins.

## Action items

- [ ] Session 1: hot-fix `originals.py` producer dedup key + narrow `thread_index.py:41` except + regression test in zkm-eml
- [ ] Session 2: write `docs/phase2-plan.md`, `docs/object-storage.md`, `docs/meeting-notes/2026-05-07-object-storage.md`; update CLAUDE.md, plugin-spec.md, TODO.md ← **this session**
- [ ] Session 3: core library modules + unit tests
- [ ] Session 4: migrate zkm-notes (atomic write) and zkm-eml (delete in-plugin copies of helpers)
- [ ] Session 5: `zkm rm` and `zkm gc` (only after one week of session 4 in real use)
