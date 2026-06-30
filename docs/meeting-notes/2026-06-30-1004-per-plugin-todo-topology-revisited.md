# 2026-06-30 — Per-plugin TODO topology, revisited (f98d)

**Started:** 2026-06-30 10:04
**Session:** b24fb4f3-707b-4701-a280-b8ac4f7fcccc
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), ⚙️ Sage (skill-runtime lens, re-onboarded)
**Topic:** Revisit the 2026-05-13 "central-all-in-zkm-TODO" decision — per-plugin TODO independence (B) vs central ledger + guard machinery (A) vs central + enforced id-reuse (C); and resolve the fate of the guard items it gates (ddb8, dotclaude-skills 69f4 / d097).

## Surfaced grounding (from setup)
- Every plugin (17) already has BOTH a `ROADMAP.md` (real executor specs) AND a `TODO.md` that is a **stub pointer** ("central ledger = ~/src/zkm/TODO.md; specs = ROADMAP.md") carrying only a one-line relay summary.
- Central `TODO.md` holds plugin-scoped sections (W/V/C/… prefixes). Plugin ROADMAPs "reuse" central ids by declaration but **drift in practice** — verified this session: zkm-pdf ROADMAP open ids `02bd/3801/8aa4/9475` vs central pdftext `d3c9/1681/c63c/835c`; zkm-photo has 3 open ROADMAP items (`62cb/8740/a711`) with **no central section at all**; ticks don't propagate back → central "open plugin" count inflated.
- Relay already sweeps all repos (`discover-repos` / `unpromoted-scan` / `gather-human-backlog` / `proj relay`) — it IS the aggregator now.
- dotclaude-skills `id:69f4` (cross-PROJECT sync) exists to GUARD the drift; `id:d097` blocks the 69f4 build on THIS meeting; `id:2840` is a larger "derived ledger index" vision subsuming cross-ledger+cross-project.
- No tooling parses the W/V/C prefix (grep of `src/`, `relay/scripts/`, skills came back empty) — pure human convention, safe to retire.

## Agenda
1. Core topology: A (status quo + build cross-project guard) vs B (per-plugin owns TODO+ROADMAP, central = core/cross-cutting only) vs C (central + mechanically enforce id-reuse).
2. If B: the boundary rule for "stays central".
3. All-plugin visibility — how the human sees every plugin's open work at a glance.
4. Migration sequencing + joint call with GH-Issues-as-inbox + fate of W/V/C prefix table.
5. Fate of the guard items: ddb8 (zkm), dotclaude-skills 69f4 + d097.

## Discussion

### Agenda 1 — Core topology
🏗️ **Archie:** Ground truth changed since 2026-05-13. Back then plugins had only a ROADMAP; central was the one place to see plugin work. Today every plugin carries a `TODO.md` — but a stub that points back to central. We're choosing whether those files are real or decorative. The drift is structural: `core d3c9 ↔ zkm-pdf cd59` shipped under two ids; ticking a plugin ROADMAP box never reaches its central twin.

😈 **Riku:** Drift-aversion was my 2026-05-13 argument against a *hybrid* (central plugin ledger + plugin-local). Option B isn't that — B says central stops holding plugin items entirely, so the plugin repo is the single home and `orphan-scan --cross-ledger` (already intra-repo TODO↔ROADMAP) catches the drift for free. B *dissolves* my old objection; A/C *keep* the cross-repo seam and pay to guard it.

⚙️ **Sage:** The constraint that justified central has lapsed. "Central = single pane" was decided when nothing could sweep repos; now the relay does (`discover-repos`/`unpromoted-scan`/`proj relay`). dotclaude-skills `id:d097` was filed to bring this here: if B wins, handoff C2's "central by design" flips, `--cross-ledger` starts serving plugins, and 69f4 "is likely OBSOLETED — don't build it before the meeting decides." A means building new machinery to preserve a lapsed constraint — guard-a-vestige.

✂️ **Petra:** N=2 flipped. 2026-05-13 per-plugin TODOs were N=1 speculative; today 17 plugins, multiple with real local open work (photo/social/whatsapp 3 each; signal/threema/telegram 2). The speculative-abstraction veto is gone. But B is a ~10-repo migration — stage it: reconcile already-done inflated twins FIRST (don't migrate lies), then move open items.

🏗️ **Archie:** C still needs back-propagation sync even with identical ids — ticking a plugin ROADMAP doesn't tick the central twin without a job. C buys nothing A doesn't and keeps central bloated. The live choice is **B vs (A/C)**.

😈 **Riku:** Minimum evidence to change my mind toward A: if the relay sweep couldn't produce an all-plugin view as cheaply as central. It already does (`proj relay`). My pushback collapses provided Agenda 3 nails the rollup. I hold the line there.

**Decision 1 (Tobias):** **Option B.** Added: "each plugin can have gh issues once published" (→ Agenda 4).

### Agenda 2 — Boundary rule + Agenda 3 — Visibility
🏗️ **Archie:** f98d's rule (touches `src/zkm/` OR ≥2 plugins OR shared schema → central) is sound but needs sharp edges. Grey cases are the cross-cutting series: γ schema (core + zkm-ner), `zkm.pdftext`/`object-storage` shared libs, messaging-spec conformance. Those stay central by the ≥2-plugin/shared-schema clause; a pure zkm-photo parser bug is plugin-local.

✂️ **Petra:** State it so a Sonnet executor applies it without a meeting — three-line first-match test, default plugin-local. (1) edits `src/zkm/**` or core test → central; (2) shared schema/spec/lib ≥2 plugins import → central; (3) else → owning plugin's TODO.md. Always exactly one home.

😈 **Riku:** Failure mode: an item that grows a second consumer. No thrash — classify once at filing; re-home only on a deliberate 2nd-plugin pickup. Tiebreaker: would closing it touch ≥2 repos? → central; single-repo close → plugin-local.

⚙️ **Sage:** Visibility is the load-bearing replacement for central. The relay rollup is executor-facing; the human glance is `proj`/`/projects`. Extend that to walk `plugins/*/TODO.md` — no new aggregator (N=2: this need + the existing relay sweep both want the same walk).

🏗️ **Archie:** Don't delete the stub TODOs — promote in place (header inverts: was "central is the ledger" → becomes "this is the ledger; specs in ROADMAP.md"). Central loses its W/V/C plugin sections.

😈 **Riku:** Caveat to verify at migration: `proj`/`projects` must actually read plugin TODO files, else B trades inflated-central for invisible-plugin-backlog. Action item, not a blocker. With that, I release the B-hold.

**Decision 2 (Tobias):** First-match-wins 3-line test (above). **Decision 3 (Tobias):** Extend `proj`/`/projects` to walk plugin TODOs; relay `--all` stays executor-facing.

### Agenda 4 — Migration + GH-Issues + prefix table
✂️ **Petra:** Sequencing, order matters: (1) reconcile already-done inflated central twins by id; (2) move genuinely-open items into each plugin's TODO.md; (3) strip empty W/V/C sections. Doing 3 before 1 drops open ones; doing 2 before 1 migrates done work.

🏗️ **Archie:** Real content is ~10 repos (photo/social/whatsapp/signal/threema/telegram/calendar/chatgpt/pdf/claude-ai); the rest are fully closed.

😈 **Riku:** Relay polyrepo — a live pool would collide (10+ plugin TODO edits). Either run it as its own session with `claim.sh peek` per plugin, or confirm no pool is live. [Tobias confirmed: no live pool → run now.]

⚙️ **Sage:** GH-Issues compose with B via the existing 2026-06-26 "Issues = inbox channel" policy — issues triage into the plugin's OWN TODO now, not central. One-line policy update.

✂️ **Petra:** Prefix table retired under B — repo = namespace. E (γ)/S (status) items stay central but lose the letter. Don't rewrite historical closed ids (git history = archive).

😈 **Riku:** Verify no tooling parses the prefix before deleting the table. [Verified empty this session.]

**Decision 4 (Tobias):** Run migration **now, this session** (no live pool), strict order. **Decision 4b:** GH-Issues → plugin's own TODO. **Decision 5 (Tobias):** Retire prefix table.

### Agenda 5 — Fate of the guard items
⚙️ **Sage:** Three items exist only to police the drift B dissolves: zkm `ddb8` (polyrepo ROADMAP↔TODO drift), zkm `1d41` (bridge to 69f4's scanner), dotclaude-skills `69f4` (cross-project sync). Under B, ddb8/1d41 are obsoleted; 69f4's zkm justification evaporates.

😈 **Riku:** 69f4 is broader than zkm (cites toesnail+mathematical-writing `6ab8`, toesnail+zkm `4159`). B kills its strongest case but not the triad mirrored-id case. So 69f4 is **demoted, not closed** — and that's dotclaude-skills' call, not ours.

🏗️ **Archie:** `id:2840` (derived ledger index) lists cross-project in scope — 69f4 may be subsumed rather than built standalone. Either way the zkm pressure is gone.

✂️ **Petra:** Split by home. zkm-local (this session): migration + close ddb8/1d41 + CLAUDE.md rewrite. Routed to dotclaude-skills inbox: execute d097 relay-side outcome, demote 69f4, update the GH-issues policy line.

😈 **Riku:** Don't mint a zkm `id:` for the routed dotclaude-skills work — inbox `routed:` token only (dead-letter anti-pattern, 3947). The `proj` change is a dotclaude-skills skill → also routed, not zkm-local.

**Decision 6 (Tobias):** Close zkm-local, route the rest.

## Decisions
- **D1 — Topology: Option B.** Each plugin owns its own `TODO.md` (real tactical ledger); central `zkm/TODO.md` keeps ONLY core + genuinely cross-cutting items. single-id-two-views becomes intra-repo so `orphan-scan --cross-ledger` catches drift natively. *Out of scope:* A/C (preserve the cross-repo seam, must build 69f4/2840 to guard it).
- **D2 — Boundary rule (first-match wins):** (1) edits `src/zkm/**` or a core test → central; (2) shared schema/spec/library imported by ≥2 plugins (γ, pdftext, object-storage, messaging-spec, conformance) → central; (3) else → owning plugin's TODO.md. Default = plugin-local. Tiebreaker: "would closing it touch ≥2 repos?" → central. Classify once at filing; re-home only on a deliberate 2nd-plugin pickup. *Out of scope:* mid-flight auto-migration on drift.
- **D3 — Visibility:** extend `proj`/`/projects` to walk `plugins/*/TODO.md` (replaces central's single-pane). Relay `--all` rollup stays executor-facing. *Out of scope:* a new `zkm` aggregator command.
- **D4 — Migration (run now, this session — no live pool):** strict order (1) reconcile already-done inflated central twins; (2) move open plugin items into each plugin's own TODO.md (promote stubs in place, no `git rm`); (3) strip empty plugin sections + rewrite CLAUDE.md prefix section → boundary rule. *Out of scope:* running it under a live pool claim.
- **D5 — Prefix table retired** (W/V/C/S/E/M/N/A); repo = namespace. E/S items stay central, lose the letter. Historical closed ids untouched.
- **D6 — GH-Issues compose with B** via the existing 2026-06-26 "Issues = inbox channel" policy; issues triage into the plugin's OWN TODO, not central. *Out of scope:* the auto-topology-flip trigger (already superseded 2026-06-26).
- **D7 — Guard items:** close `ddb8` + `1d41` (zkm-local, obsoleted by B); route the `d097`/`69f4`/policy work to dotclaude-skills inbox (no zkm id). *Out of scope:* closing 69f4/d097 from this repo.

## Action items
- [x] **MIG-1.** Reconcile already-done inflated central twins (close central twins of shipped plugin ROADMAP items). `src/zkm/TODO.md`. (this session)
- [x] **MIG-2.** Move genuinely-open plugin-local items from central into each plugin's own `TODO.md` (promote the stub in place). (this session)
- [x] **MIG-3.** Strip the now-empty plugin sections from `src/zkm/TODO.md`; keep core + cross-cutting (E/S items sans letter). (this session)
- [x] **MIG-4.** Rewrite the CLAUDE.md "TODO prefix convention" section → the D2 boundary rule; cite this note. (this session)
- [x] **MIG-5.** Close `ddb8` + `1d41` in `src/zkm/TODO.md` (obsoleted by B), citing this note. (this session)
- [ ] → routed to dotclaude-skills inbox: execute d097 relay-side outcome — flip handoff C2 "central ledger by design"; make **`orphan-scan.sh` (forward) and `proj`/`projects` plugin-aware** (read `plugins/*/TODO.md`, not just central); demote 69f4 (drop zkm-polyrepo justification, triad case only); update 2026-06-26 GH-issues policy line → "plugin's own TODO". <!-- routed:2649 -->

## Known transitional state (until d097 ships)

`orphan-scan.sh` (forward) reads ONLY central `TODO.md`. After this migration the relocated-but-open plugin items now live in `plugins/zkm-*/TODO.md`, so a `/meeting` forward orphan-scan will **flag them as false orphans** until the routed d097 work makes orphan-scan plugin-aware. Currently expected on the next pass: `ac55` (zkm-telegram), `b043` (zkm-signal), `c89a` (zkm-threema), `b99e`+`f40c` (zkm-ner), `8d67` (zkm-whatsapp), and the SOC/STT/M relocations. These are **tracked** (in their plugin TODO), not orphaned — do not re-mirror them into central. The genuinely done/obsolete twins (`849f`, `8cf8`, `9e13`, `d3c9`, `1681`, `835c`, `0566`, `fa5a`) were ticked in their source notes this session.
