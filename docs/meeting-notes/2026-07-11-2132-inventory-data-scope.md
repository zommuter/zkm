# 2026-07-11 — Descriptive-inventory data in zkm (drives + hardware): scope & merge

**Started:** 2026-07-11 21:32
**Session:** a8d9bb87-380a-4153-a944-87200152b12f
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🛰️ Hank (host-fleet config-management, new), 🗺️ Flora (information-flow routing, new), 🗄️ Cassi (derived-data persistence / sync-vs-backup, onboarded in Agenda 3)
**Topic:** How zkm should hold descriptive/mutable *asset-inventory* data (external drives, hardware/RPis/IoT), routed in from it-infra as inbox items routed:5ea3 + routed:4279 — and whether they merge into already-filed central items id:f22d (drives) / id:d35e (home-knowledge/devices).

## Agenda
1. **Merge vs. fresh** — routed:5ea3 (external-HDD data map, from it-infra) vs existing id:f22d (HDD/external-drive asset inventory, from zomni). routed:4279 (hardware/RPi/IoT inventory) vs existing id:d35e (BIM/home-knowledge, room+device inventory). Duplicate topics or distinct?
2. **Data shape** — how does zkm hold *mutable descriptive* inventory data given its append-only, git-as-temporal-index, md-source-of-truth model? Notes-doc convention vs plugin vs entity pages. The currency problem: a catalog goes stale.
3. **Scope / MVP / sequencing** — is there a unified "inventory" concern here, and what (if anything) is the near-term deliverable vs a deferred scoping item?

## Discussion

### Agenda 1 — Merge vs. fresh
- Petra: 5ea3 (from it-infra) ≡ id:f22d (from zomni) — same "drive inventory / which-drive catalog" topic, two requesters. Fresh ids would manufacture TODO↔TODO drift.
- Hank: 4279 (RPi/IoT roster) ⊂ id:d35e (BIM/home-knowledge umbrella). Fold in as the concrete device-roster sub-case; d35e is the umbrella, 4279 is its first real payload.
- Riku: preserve the it-infra provenance + admit-rule rationale in f22d's text BEFORE `inbox-done 5ea3` deletes the inbox line, else the "why is a drive map zkm's job" trail is lost.

### Agenda 2 — Data shape
- Flora: inventory is *born inside* zkm (hand-authored), no external source → routes to `notes/`, not `plugins/`. But drive *content* search ("which drive has file X") does have a source (mount + `find`) = a real converter.
- Riku: currency failure — hand-maintained inventory rots; the mutability is why it-infra pushed it out.
- Archie: git-as-temporal-index makes hand-edited `notes/` the intended model (HEAD=current, log=history); append-only applies only to plugin-converted content, not `notes/`.
- Hank: hardware "dust-collecting status" is subjective/low-churn → manual is the only honest option; N=2 (drives+devices) warrants a shared convention.
- **USER STEER:** chose the *plugin* route (not notes-only), and added two threads: (a) integrate **git-annex** for the backup/redundancy dimension from it-infra; (b) **zomni is now integrated into it-infra** → the zomni-sourced f22d and it-infra-sourced 5ea3 are the *same project's* asks (reinforces D1; provenance = "it-infra (formerly zomni)").

### Agenda 3 — git-annex boundary, scope, sequencing
- Cassi: the it-infra ask is a *location-tracking* problem; git-annex already IS a location tracker (`whereis`/`info`). Re-deriving redundancy by hand = a second, instantly-stale copy of the annex log. sync≠backup: annex owns redundancy (copy-count), manifest owns freshness (`last-sync`).
- Archie: partition drive contents — annex-managed subset (machine-derived), non-annex data (hand-authored manifest), physical/descriptive fields (always hand-authored).
- Riku: two input surfaces; annex enrichment must degrade gracefully (annex missing / drive offline) like `--no-dense`.
- Hank: read the SAME named-remote registry `zkm push` (id:998b) / future `zkm fetch` (routed:12fc) use — drives ARE the annex remotes; N=2+ justifies one shared registry.
- **USER FACTS:** (a) 0 external HDDs are git-annex today → annex path has nothing to enrich yet; (b) whole-disk annex-onboarding is an in-flight it-infra 3-2-1-backup decision.
- Cassi/Hank: whole-disk annex-onboarding (incl. foreign non-zkm data) is a 3-2-1 backup-architecture call; `zkm-inventory` is an OBSERVER of the topology, never its setter.
- Riku: observe-before-preventing on the *code* — with 0 annex drives, don't write annex-enrichment yet; build manifest→entity→search, document the seam, switch on at ≥2 annex drives.

## Decisions
- **D1 — Merge, no new ids.** 5ea3 (external-HDD map) folds into **id:f22d** with provenance `routed:5ea3 from it-infra (formerly zomni; admit rule: descriptive/mutable data → zkm, not infra-as-code)`. 4279 (hardware roster) folds into **id:d35e** as the concrete device-roster sub-case (`routed:4279`: RPis/IoT model/location/in-use). Two `inbox-done` calls after provenance lands. *Out of scope:* minting parallel ids (would manufacture TODO↔TODO drift).
- **D2 — `zkm-inventory` plugin (not notes-only).** A converter from a hand-authored structured manifest → per-drive + per-device md with typed `entities[]` (drive, device), indexed & searchable via the existing pipeline. Own repo, follows the new-plugin dispatch convention; this meeting ratifies approach+boundaries as the scoping seed. *Out of scope:* implementing it inside this `/meeting`.
- **D3a — git-annex boundary.** Redundancy/location for the annex-managed subset is machine-derived (read-only `git annex whereis`/`info`, graceful-degrade); the manifest owns non-annex data, capacity, physical location, purpose, hardware dust-status, and `last-sync` freshness (sync≠backup). Reads the same named-remote registry as `zkm push`/`fetch`. *Out of scope:* hand-authoring redundancy (would duplicate/drift the annex log).
- **D3b — annex seam dormant; onboarding routed to it-infra.** v1 is manifest-driven; the annex-enrichment code is a documented dormant seam built only once ≥2 annex-managed drives exist (observe-before-preventing). Whole-disk annex-onboarding is routed to the in-flight it-infra 3-2-1-backup meeting, with the coupling flagged both ways. *Out of scope:* zkm deciding or blocking on the backup architecture.
- **D3c — lane separation (clarified post-meeting).** The plugin has TWO independent lanes and git-annex touches only ONE. (a) DRIVES: git-annex relevant only to redundancy/location of *annexed drive contents*. (b) HARDWARE (RPi/IoT) roster: pure hand-authored descriptive md — NO git-annex involvement ever (a device is not annexed content). The ≥2-annex-drives gate (D3b) applies to the drive-lane *enrichment seam ONLY*, NOT to the plugin and NOT to the hardware roster — both are fully buildable today at 0 annex drives. Riku's "count annex-managed drives" go/no-go is scoped to whether the annex-enrichment *code* earns its keep, not to whether the plugin ships.
- **D3e — find-dump drive-content lane un-deferred to fast-follow (post-meeting, 2026-07-11).** The Layer-2 `find`-dump drive-content index (mount each drive → record file listing → searchable per-drive content manifest; `zkm search "<title>"` → which drive) was deferred "gated on demonstrated need." That need surfaced immediately: locating favorite movies / bulk media that is NOT "worthy" of git-annex. So it becomes **lane (c) of id:e65e, a fast-follow after v1** (lanes a+b). It is **git-annex-INDEPENDENT** — it exists precisely for the bulk non-annex content that annex-`whereis` never covers; complementary to lane-a's annex seam (annex locates annexed zkm data, find-dump locates everything else). Heaviest lane: large manifests (per-drive chunking / compact format), mount orchestration; re-sweep = git diff = temporal "when did this file move/vanish."
- **Scope fence (all D):** out of scope for zkm-inventory — floor plans / 3D / BIM (d35e's broader umbrella beyond the device roster), live smarthome state, any write-back to drives. (Layer-2 `find`-dump drive-content search is NO LONGER out of scope — promoted to lane-c fast-follow per D3e.)

## Action items
- [ ] Merge 5ea3→id:f22d (append it-infra/formerly-zomni provenance + admit-rule + outcome-pointer to this note); `append.sh inbox-done 5ea3`. (session 2026-07-11-2132)
- [ ] Merge 4279→id:d35e (append device-roster provenance + outcome-pointer); `append.sh inbox-done 4279`. (session 2026-07-11-2132)
- [ ] Scope + build **`zkm-inventory` plugin** — manifest→per-drive/per-device md with typed entities, searchable; git-annex whereis/info enrichment as a DORMANT seam gated on ≥2 annex-managed drives; reads the shared push/fetch remote registry; go/no-go first check = count annex-managed drives. See this note. <!-- id:e65e -->
- [ ] → routed to it-infra inbox: whole-disk annex-onboarding of external HDDs is the 3-2-1-backup meeting's call; zkm-inventory carries a dormant annex-enrichment seam that lights up once ≥2 drives are annexed — flag the coupling. <!-- routed:cfc1 -->

## Amendment session — REVIEW_ME box (id:46f6), resolved before this meeting per user pick
- The `gated-on:` marker is id-typed (`orphan-scan.sh:295-311` checks each token against local `[x]` state). All three flagged items carry **external-condition** gates, not TODO-id dependencies: id:c63c (labeled-PDF-corpus evidence), id:f1cf (skill-revision-or-2nd-need), id:3174 (slice-0 miss-set data). None depends on another local TODO id, so an id-typed `gated-on:` edge does not apply. **Resolution: confirm prose-only** (tick the REVIEW_ME box with rationale). The UNMARKED-GATE backstop will keep re-firing on these (no non-hacky suppressor for external-condition gates) → routed a light dotclaude-skills suggestion for a durable `prose-only confirmed` marker so the loud detector shrinks rather than re-litigates.
