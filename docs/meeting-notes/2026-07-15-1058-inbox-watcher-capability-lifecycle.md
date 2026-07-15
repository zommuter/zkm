# 2026-07-15 — Inbox-consuming watcher, plugin capability registration & inbox lifecycle (e7c1)

**Started:** 2026-07-15 10:58
**Session:** ad67f738-cb62-484a-b1ef-f9e0ea91f372
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🗺️ Flora (information-flow routing, new), 🛰️ Sven (systemd .path/.timer edge-trigger, new), 🧮 Reni (ref-counted multi-producer retraction, new)
**Topic:** Design the inbox-consuming daemon / `zkm watch` (id:e7c1) together with (a) how plugins register producer/consumer capabilities, (b) its relationship to the existing `zkm fetch`, and (c) the lifecycle of processed inbox files.

## Surfaced context (code state at meeting start)
- `zkm fetch <source>` **already exists** (`src/zkm/cli.py:481`): runs a configured shell `command` from `core.fetch.sources` to deposit bytes, optionally chains a single `zkm convert <plugin>`.
- Capability declaration today: `plugin.yaml` has `creates_dirs`, `config`, `gitignore_patterns`, `conformance` — but **no producer/consumer graph**. Cross-plugin chaining ("zkm-pdf consumes what zkm-eml deposits") is convention + hardcoded knowledge (`docs/plugin-spec.md:353`).
- Inbox ownership: `.origin.json` sidecar `producers[]` (schema v1, `plugin`+`message`+`sha256`, **no version**). Consumers must skip items they don't own (`plugin-spec.md:96, :353`).
- N=2 gate for the daemon: **MET** — systemd embed timer (`contrib/systemd/zkm-embed.timer`) now exists alongside the mbsync post-commit hook = two distinct background callers.
- Tightly coupled open items: id:b7e2 (CAS processed-by-version + git-as-byte-source), id:906c (`zkm queue`/attach), id:7c3f (multi-source per plugin), concurrent-run guard (exit-75).

## Agenda
1. Capability registration — how does a plugin declare "I produce X into inbox / I consume Y from inbox" so a trigger can derive the processing chain instead of hardcoding it?
2. `zkm fetch` relationship — how do fetch / watch / convert compose? Is `watch` just the daemon form of the same trigger?
3. Inbox file lifecycle — after an item is processed, what happens? (leave / mark / move / prune) under: external rewriters (mbsync, Syncthing), multiple consumers, "processed" must be visible.
4. Scope now vs deferred — N=2 is met; what actually gets built vs. gated.

## Discussion

### Item 1 — Capability registration
- 🗺️ Flora: eml→{pdf,photo} edge is implicit today (sidecar `producers[]` + hardcoded convention). A watcher can't derive the chain; it can only re-run everything.
- 🏗️ Archie: two candidate graph keys — by plugin name (`consumes_producers: [eml,whatsapp]`) vs by content type (`consumes_types: [application/pdf]`).
- 😈 Riku: real edges are a tiny near-static DAG (eml/whatsapp/scan → pdf/photo). MIME bus = premature message broker; a mis-typed sidecar → bank statement to photo captioner. Would change mind at ≥3 churning producers per consumer.
- ✂️ Petra: N=2 on the abstraction — pdf+photo already work via the hardcoded check, so the graph only earns its keep coupled to the watcher, at the fidelity the watcher consumes.
- 🧮 Reni: register in the existing `producers[]` sidecar; it needs a `version` field and consumers must appear in it (shared datum with Item 3 / id:b7e2). Don't invent a second registry.
- 🗺️ Flora (concede): keep routing name-based, but record `content_type` per sidecar entry now — free at write, un-backfillable later.

**Tobias:** *(no option selected)* "anything else is an immediate step that'll double workload or bite us later." Later correction (Item 4): this did **not** mean MIME routing is rejected — only that building it now is out.

**Decision 1:** Name-based consumer edges in `plugin.yaml` (`consumes_producers: [...]`) as the routing mechanism *for now*; producers record `content_type` (+ `version`) per `.origin.json` entry. **MIME/content-type routing is DEFERRED, not rejected** — the `content_type` field recorded now is its forward-compat enabler, so adopting type-routing later is a consumer-side change with no re-scan; revisit when producer churn warrants (≥3 churning producers per consumer). Out this session: **building the routing bus now** (premature = "double workload"). No-registration REJECTED (bites later — re-walks cluttered inbox). `version` on producer entries is the shared datum with id:b7e2 — one schema bump, not a second registry.

### Item 2 — `zkm fetch` relationship / watch topology
- 🏗️ Archie: three verbs — fetch (acquire, shipped `cli.py:481`) / convert (transform + may deposit attachments) / watch (react). Two byte sources (external tools + zkm's own convert) ⇒ trigger must drive a **cascade to fixpoint**: fetch → convert(eml) → attachments → convert(pdf,photo) → index.
- 🛰️ Sven: no resident python daemon. OS owns edge-triggering — systemd `--user` `.path` unit (Syncthing), existing post-commit hook (mbsync), existing `.timer` (embed). Missing piece = the **cascade command** those triggers call, not a daemon.
- ✂️ Petra: resident supervisor = deferred `zkm queue` (id:906c, Phase 3). Warranted now = thin `zkm process` verb: enumerate dirty → cascade via Item-1 graph → index. Invoked BY the OS triggers.
- 🗺️ Flora: step-1 enumeration must be the id:b7e2 "objects needing work" query, NOT a blind inbox re-walk (the item is explicit).
- 😈 Riku: cascade-to-fixpoint is the dangerous new bit — bound it (max-iter + journald-warn on self-retriggering output); lean on the existing exit-75 guard for overlap (free, no new lock). Keep `fetch` user/timer-initiated only; `.path`/hook triggers drive `process`, never `fetch`.
- 🛰️ Sven: drop the resident meaning of `zkm watch`; if the word is kept, `zkm watch install` = generate/enable the systemd units (installer helper); the running thing is systemd.

**Tobias amendment (incomplete-write filter):** must handle mid-write files (Syncthing/mbsync still writing). Can't rely on a sync-tool API (another process could be the writer) — it's a generic **"has finished being modified" filter**. zkm-wa already does a version: `plugins/zkm-whatsapp/scripts/systemd/zkm-whatsapp-decrypt.sh` uses an mtime newer-than guard PLUS a Syncthing-REST `db/completion` gate that **fails open** if the API is unreachable. The core primitive must be tool-agnostic: **stat-stability quiescence** (size+mtime stable across a debounce window) as the floor; a sync-API gate stays an optional per-plugin refinement on top (zkm-wa keeps its Syncthing gate).

**Decision 2:** Dissolve the "daemon" into **OS edge-triggers → thin `zkm process` cascade**. `zkm fetch` unchanged (acquire-only, user/timer-initiated). `zkm process`: (1) enumerate objects needing work via the id:b7e2 ledger (not an inbox re-walk); (2) apply a **tool-agnostic stat-stability quiescence filter** before treating an object as ready (optional per-plugin sync-API gate layered on top); (3) cascade convert→convert→index to a fixpoint, **bounded by max-iterations**, guarded by the existing **exit-75** run-guard. Resident python daemon REJECTED (reinvents systemd restart/journald/boot-persistence; overlaps deferred id:906c). `zkm watch` (if kept) = a systemd-unit installer helper, not a process.

### Item 3 — Inbox file lifecycle
- 🏗️ Archie: CAS is the byte store; inbox symlinks are a **regenerable navigation view** (`object-storage.md`). Retiring an inbox item ≠ deleting bytes (bytes are ref-counted in `_objects/`, swept by `zkm gc`). Item 3 is about the symlink/source-file, not content.
- 🧮 Reni: ref-count problem — a symlink is live while ≥1 declared consumer (Decision-1 graph) hasn't processed it at current version. Record consumers' `(plugin, version)` in the sidecar; satisfied-set == declared-set ⇒ ref-count 0 ⇒ retirable. "Processed" is a derivable sidecar property, never "symlink gone."
- 🗺️ Flora: **two ownership classes, separate lifecycles** — (1) zkm-produced symlinks (eml→inbox/mail): zkm owns, retirable; (2) externally-deposited source files (Syncthing→inbox/whatsapp/*.db, the `gitignore_patterns` inputs): **never delete** — external tool rewrites them; deletion → sync conflict/loop. Marked-only via watermark/sidecar.
- 😈 Riku: zero measured evidence clutter has hurt (b7e2 is a concern, not an incident). Eager pruner = speculative. Minimum clearly-correct increment = sidecar `version` field + read-only view. Prune/move gated on observing harm.
- ✂️ Petra: b7e2's schema bump (`version` on producers) + a `zkm inbox` view IS the whole shippable increment; it answers "processed should be visible" without deleting/moving.
- 🧮 Reni: retirement is idempotent+reversible by construction — `zkm inbox --rebuild` reconstructs symlinks from CAS+sidecars, so pruning is safe (prune wrong → regenerate). That's what lets "observe first" coexist with eventual pruning.
- 🛰️ Sven: the quiescence gate (Item 2) is the precondition for recording a processed-version on an external file still being rewritten.

**Tobias:** selected **"Visibility now, prune gated."**

**Decision 3:** Ship id:b7e2 sidecar `version` field + a read-only `zkm inbox` view (per-object `pending:`/`done:[plugin@ver]`). **Nothing deleted or moved.** "Processed" = derivable sidecar property. Prune/move of **zkm-owned symlinks only** (ref-count→0, regenerable via `zkm inbox --rebuild`, bytes stay in CAS) is DESIGNED-BUT-GATED — opt-in follow-up after observing clutter. **Externally-deposited source files are NEVER removed/moved** (marked-only). Answer to "is removal an option?": yes, but only zkm-owned symlinks, only lazily, only after the visibility layer exists.

### Item 4 — Scope & sequencing
- ✂️ Petra: sidecar `version` ledger (id:b7e2) is the hard foundation for both visibility and cascade enumeration; it goes first.
- 🏗️ Archie: decomposition A (sidecar v2) → B (`zkm inbox` view) → C (`consumes_producers` graph) → D (`zkm process` cascade + systemd `.path`).
- 😈 Riku: A+B impl-ready → pool; C+D carry the new risk (routing, cascade fixpoint, quiescence) → each needs its own RED spec. Don't fold D into one item (quiescence filter is a standalone testable unit).
- 🗺️ Flora: keep the deferred set explicit so it doesn't leak back.
- ✂️ Petra: all four are **central** (core `src/zkm/**` + ≥2-plugin shared schema), boundary rule → central.

**Tobias correction:** MIME bus was NOT agreed out — it is deferred WITH its enabler (`content_type`) built now. Only building the routing bus this session is out. (Decision 1 amended.)

**Tobias:** selected **"Phased items, A+B first."**

**Decision 4:** File A/B/C/D as sequenced **central** items under the e7c1 umbrella. **A** (sidecar schema v2; absorbs id:b7e2 part 1) and **B** (`zkm inbox` read-only view) go to the executor pool now as impl-ready. **C** (`consumes_producers` + loader) and **D** (`zkm process` cascade + systemd `.path` installer) are filed needing their own RED-spec, gated on A+B landing. DEFERRED: MIME/content-type routing (enabler shipped in A), prune/move (Decision 3 follow-up), resident daemon / attach semantics (id:906c), git-as-byte-source (id:b7e2 part 2), multi-source-per-plugin (id:7c3f).

## Decisions
1. **Capability registration** — name-based `consumes_producers` edges in `plugin.yaml`; producers record `content_type` + `version` per `.origin.json` entry. MIME routing deferred (enabler built now), not rejected. No-registration and building-the-bus-now both out. `version` = shared datum with id:b7e2.
2. **fetch/watch/convert** — no resident daemon. `zkm fetch` unchanged (acquire-only). New thin `zkm process` cascade: enumerate-via-ledger → tool-agnostic stat-stability quiescence filter → bounded convert→convert→index fixpoint, exit-75 guarded. Fired by systemd `.path` units + existing post-commit hook + existing `.timer`. Resident daemon = deferred id:906c. Out of scope: resident supervisor; driving `fetch` from `.path`/hook triggers.
3. **Inbox lifecycle** — bytes always in CAS (ref-counted, `zkm gc`); symlink is a regenerable view. Ship `version` field + `zkm inbox` visibility; nothing deleted/moved. Prune/move of zkm-owned symlinks only = gated follow-up. External source files never removed. Out of scope: eager prune, deleting external files.
4. **Scope/sequencing** — A+B to pool now (central, impl-ready); C+D central, gated on A+B with own RED-specs. Deferred set fixed above.

## Action items
- [ ] **A — Sidecar schema v2** (central, pool): add `version` + `content_type` to `producers[]` entries and record *consumer* `(plugin, version)` in the `.origin.json`/per-object sidecar; graceful-read migration from schema v1. Absorbs id:b7e2 part 1. Files: `src/zkm/sidecar.py`, `docs/object-storage.md`. Contract: a re-run records the consumer's current version; a version bump makes the object show as `pending` for that consumer. See `docs/meeting-notes/2026-07-15-1058-inbox-watcher-capability-lifecycle.md`. <!-- id:3628 -->
- [ ] **B — `zkm inbox` view** (central, pool): read-only CLI listing each inbox object with `done:[plugin@ver]` / `pending:[plugin]`, `--pending` filter, `--rebuild` (regenerate symlinks from CAS+sidecars). Files: new `zkm.inbox` surface + `src/zkm/cli.py`. Contract: after convert a processed object shows `done`; an unprocessed consumer shows `pending`; `--rebuild` is idempotent. See `docs/meeting-notes/2026-07-15-1058-inbox-watcher-capability-lifecycle.md`. <!-- id:d336 -->
- [ ] **C — `consumes_producers` graph** (central, needs RED spec, gated on A+B): `plugin.yaml` gains `consumes_producers: [...]`; loader/discovery exposes it; consumers adopt. Files: `src/zkm/convert.py`, `docs/plugin-spec.md`, per-plugin `plugin.yaml`. Contract: the declared edge set drives which consumers `zkm process` queues for a producer's deposits. See `docs/meeting-notes/2026-07-15-1058-inbox-watcher-capability-lifecycle.md`. <!-- id:4a4f -->
- [ ] **D — `zkm process` cascade + systemd `.path`** (central, needs RED spec, gated on A+B): cascade command (enumerate-needing-work via ledger → stat-stability quiescence filter → bounded convert→convert→index fixpoint → exit-75 guard, max-iter warn) + a `.path`-unit installer (`zkm watch install`?) in `contrib/systemd`. Reuse zkm-wa's fail-open sync-gate pattern as the optional per-plugin layer. Files: `src/zkm/cli.py`, `src/zkm/convert.py`, `src/zkm/inbox.py`, `contrib/systemd/`, `docs/install.md`. Contract: a file landing in a watched dir triggers exactly one bounded cascade after the file quiesces; overlapping triggers coalesce via exit-75. See `docs/meeting-notes/2026-07-15-1058-inbox-watcher-capability-lifecycle.md`. <!-- id:173f -->
- [x] **Ledger updates** (this-session bookkeeping): amend id:b7e2 (part 1 absorbed into A/3628; part 2 git-bytes stays deferred), re-scope id:e7c1 as the umbrella pointing at A–D, confirm id:906c / id:7c3f remain deferred. Done this session.

## Out of scope (explicit)
Building the MIME/content-type routing bus now (enabler `content_type` ships in A; adopt later); eager prune/move of any inbox item; deleting/moving externally-deposited source files (Syncthing/mbsync-owned); resident python watcher daemon / `zkm queue` attach semantics (id:906c); git-as-byte-source (id:b7e2 part 2); multi-source-per-plugin reprocess (id:7c3f); driving `zkm fetch` from `.path`/hook triggers (acquisition stays user/timer-initiated).
