# 2026-06-11 — Parallel-agent workflow for new plugin repos

**Started:** 2026-06-11 08:35
**Session:** 17996d58-6bfc-4700-8727-6620d947154e
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🎛️ Orla (multi-agent orchestration — fan-out topology, isolation, verify-before-merge gating), 🔩 Gil (git object-model / plumbing — remotes, worktree lifecycle, push semantics)
**Topic:** Define the dispatch + remote convention for building NEW (gitignored, no-remote) plugin repos with parallel agents, so the 2026-06-10 false-done failure can't recur.

## Surfaced discoveries
- [2026-06-04 dotclaude-skills] D6 dispatch contract: Workflow tool, worktree-per-item, Sonnet verify, children own code commits + return ledger fragments, main owns shared ledger + push — see 2026-06-04-1048-subagent-parallel-class1.md
- [2026-05-10 helferli] `pushurl = no_push` git convention for blocking accidental pushes; detect via `git remote get-url --push`.

## Grounding facts
- Parent `~/src/zkm/.gitignore` line 11: `plugins/` — every plugin repo is invisible to the parent; each is its own independent git repo.
- Remote landscape (2026-06-11): eml/ner → fievel; photo/pdf/scan/notmuch → github; vcard/calendar/claude-ai → git repos with NO remote; social → fievel remote added after the 2026-06-10 incident.
- Memory `feedback_todo_not_done_until_pushed`: standing rule "plugin TODO not done until pushed to fievel:src/zkm-plugins/<name>.git" — exists, but unenforced and silent on *when* the remote is created.
- D6.4 (2026-06-04) assumed items live *inside* the parent repo with an existing `origin`: children commit in worktree branches → main merges `--no-ff` → main pushes. New plugin repos satisfy NONE of these preconditions.

## The 2026-06-10 failure (id:0b03)
SOC1–3 dispatched via Workflow to parallel Sonnet agents. zkm-social was scaffolded as a fresh local git repo with no remote. Agents committed directly to its shared local `main` (no worktree isolation — worktree-per-item assumes the repo pre-exists with a baseline). TODO items SOC1–3 were marked `[x]` done. But "done" per the standing rule = pushed; there was no remote, so nothing was pushed. The done-marks were false; a later session had to create the fievel remote, push, and re-open SOC1–3.

## Agenda
1. Remote-first bootstrap — when must the remote be created for a new plugin?
2. Dispatch topology — does D6.4 map onto a fresh single-repo plugin build?
3. "Done" gate — how to make `[x]` provably mean "pushed"?

## Discussion

### Agenda 1 — Remote-first bootstrap

🏗️ Archie: The whole D6 contract pivots on one invariant — a shared `origin` that "main owns push" can target. For a new plugin repo it's absent unless we mandate creating-and-pushing-the-remote as a step before any code or dispatch. Make remote bootstrap step 0: `git init` → create bare repo on fievel via SSH → `git remote add origin` → initial commit → `git push -u origin main`. Only then does any code (sequential or parallel) get written.

🔩 Gil: Mechanically clean. One wrinkle: creating the bare repo on fievel is a remote SSH side-effect against a shared host — wants user confirmation, not silent automation inside a workflow agent. Keep remote *creation* in the human-confirmed main session; children only ever see an already-wired repo.

🎛️ Orla: Agreed — if the remote exists before dispatch, the fan-out problem reduces to the already-solved D6 shape. Worktree machinery earns its keep once there's a baseline to branch from.

😈 Riku: Cost push. Creating a bare repo + push for every new plugin, even throwaways abandoned after one exploratory session, is premature when the "is this plugin even real" question isn't settled. Lighter gate: remote-first only at *parallel-dispatch* or *done-mark*, not at `git init`.

✂️ Petra: That's the right seam. Two distinct moments: (a) first scratch/skeleton — local repo is fine, cheap, reversible; (b) the moment you dispatch parallel agents OR mark any item done — remote must exist. Binding to *dispatch-or-done* keeps throwaway experiments free while making the failure impossible exactly where it bit.

🏗️ Archie: I can live with "remote-first before parallel dispatch or before first done-mark, whichever comes first" — weaker but sufficient.

**Tobias:** chose "remote-first before dispatch-or-done."

### Agenda 2 — Dispatch topology

🎛️ Orla: D6.4 says worktree-per-item + merge `--no-ff`. The question: in a fresh plugin build, do the parallel items contend on the plugin repo or the parent repo?

🔩 Gil: The 2026-06-10 session blurred this. Agents weren't contending on the parent — they all committed to the *plugin's* single local `main`, no worktrees. `git worktree add` off a repo with no baseline commit is incoherent. The skeleton (SOC1) must land first; only then can SOC2/SOC3 branch.

🏗️ Archie: So the build is inherently staged: stage 1 = skeleton (creates baseline), stage 2 = parser modules fan out in parallel off the baseline. A Workflow `pipeline()` — SOC1 as the hard barrier, SOC2/SOC3 as the parallel fan-out.

😈 Riku: Is worktree isolation even worth it? Two agents, two disjoint files, one small repo. Does a 2-file split clear the fan-out-pays bar?

🎛️ Orla: Borderline — only 2 units, each a real parser (non-trivial). Marginally worth, but I would NOT mandate worktrees for a single-repo plugin build. Alternative (B): agents write disjoint files and return summaries, NO agent runs git, main does staged commits. Lighter.

🔩 Gil: Two safe topologies: (A) worktree-per-item — each agent gets its own worktree+branch, commits independently, main merges `--no-ff`. (B) single-worktree, disjoint-write, main commits — agents write files, return summaries, do NOT touch git. Index contention only bites on concurrent `git commit` on one index.

✂️ Petra: For a fresh single-plugin build, (B) is the right default. Reserve (A) for ≥3 independent items in an *established* repo.

**Tobias:** picked (A) worktree-per-item — "we already discussed this." Ruling: D6.4 is NOT re-litigated. The 2026-06-10 failure was D6.4 *never being applied*.

🔩 Gil (revised): The new-plugin adaptation of D6.4 is two added preconditions, not a new topology: (1) remote-first (D1); (2) skeleton-first baseline barrier — the skeleton stage lands the first commit so subsequent agents have something to `git worktree add` off. After that: vanilla D6.4, each parser agent in its own worktree+branch, commits in-worktree, returns `{branch, diary_fragment, todo_item_id, done_summary, contract_met}`, main merges `--no-ff` and pushes.

🎛️ Orla: D6.4 verbatim. The only delta: skeleton stage is a hard barrier; everything else unchanged.

✂️ Petra: Scope-locked. Only delta from 2026-06-04: "for a from-scratch repo, the remote and the baseline commit are prerequisites of the fan-out."

### Agenda 3 — The "done" gate

😈 Riku: The actual fire. The memory rule existed and was violated. A rule already on the books that still got broken needs a *mechanical check*, not a louder restatement.

🔩 Gil: Cheapest provable check: flip to `[x]` only if `git -C plugins/<name> rev-parse HEAD` equals `rev-parse @{u}` AND `@{u}` resolves at all (tracking remote exists). One command, exit-code gate. Same shape as the existing dirty-tree guard — a precondition, not a new subsystem.

🏗️ Archie: Bind to the actor who owns done. Main session is sole committer/pusher. The gate lives in main's fold-in step: for each `todo_item_id` with `contract_met: true`, run the HEAD==upstream check before writing `[x]`. Child assertions never directly flip the ledger.

🎛️ Orla: Two-key close from the D6.4 schema — `contract_met` (code correct) is necessary but not sufficient; push-landed is the second gate. Both required before `[x]`.

✂️ Petra: Universal invariant for *any* plugin TODO close, established repos included.

😈 Riku: Uses `@{u}` (tracking upstream), not a hardcoded remote name — works for fievel `origin` and github remotes alike.

🔩 Gil: Three pieces interlock: remote-first (D1) sets up `@{u}`; D6.4 makes main the sole pusher; the done-gate checks `@{u}`. No new infrastructure.

**Tobias:** "1 for now, but let's consider a todo modifying script/tool 'somehow' for later." Ruling: adopt the `@{u}` check as the immediate gate; forward-flag a write-time enforcement tool.

## Decisions

- **D1 — Remote-first before dispatch-or-done.** A new plugin repo may start as a local-only `git init` skeleton, but MUST have its remote created and an initial `git push -u origin <branch>` landed *before* either (a) parallel agents are dispatched against it, or (b) any of its TODO items is marked `[x]` — whichever comes first. Remote *creation* stays in the human-confirmed main session, never inside a dispatched child. *Out of scope:* mandating a remote at first `git init`; auto-creating remotes inside workflow agents.
- **D2 — D6.4 verbatim + two from-scratch preconditions.** The 2026-06-04 D6.4 contract is NOT re-litigated. For a from-scratch plugin repo, add exactly two preconditions to the fan-out: (1) remote-first (D1); (2) **skeleton-first baseline barrier** — the skeleton stage lands the first commit so subsequent parser agents have a baseline to `git worktree add` off. Express as a Workflow `pipeline()`: skeleton stage = hard barrier, parser modules = parallel fan-out off the baseline. *Out of scope:* single-worktree variant; any other change to D6.4.
- **D3 — Universal plugin-done gate: HEAD == `@{u}`.** Before any plugin-scoped TODO item flips to `[x]`, the main session verifies `git -C plugins/<name> rev-parse HEAD` equals `git -C plugins/<name> rev-parse @{u}`, and that `@{u}` resolves at all. Fails closed: no upstream, or HEAD ahead of upstream → item stays open. Remote-name-agnostic via `@{u}`. Universal for ALL plugin-scoped item closes, not just new plugins. *Out of scope:* applying the gate to core/cross-cutting items; hardcoding a remote name.
- **D4 — Forward-flag: write-time enforcement tool (deferred).** D3 check is, for now, a documented step main runs at fold-in. A TODO-mutating tool that enforces `@{u}` at `[x]`-write time is wanted but deferred. *Gate:* design it when todo-update skill is next revised OR a second enforcement need appears.

## Action items
- [x] Document the new-plugin dispatch convention (D1 + D2) in `~/src/zkm/CLAUDE.md` "Plugin system" section: remote-first before dispatch-or-done; skeleton-first baseline barrier; then D6.4 worktree-per-item (cite `2026-06-04-1048-subagent-parallel-class1.md` + this note). **Done this session.** <!-- id:e6eb -->
- [x] Document the universal plugin-done predicate (D3) in `~/src/zkm/CLAUDE.md` "Plugin system" section, including the exact `git -C plugins/<name> rev-parse HEAD` vs `@{u}` check command. **Done this session.** <!-- id:425d -->
- [x] Update memory `feedback_todo_not_done_until_pushed` to name the mechanical `@{u}` check (rule is now a command, not just prose). **Done this session.** <!-- id:75f5 -->
- [ ] (Forward-flag, deferred — D4) Design a TODO-mutating script/tool that enforces the `@{u}` done-gate at write-time. Gate: next todo-update skill revision OR second enforcement need. Contract: marking a plugin item `[x]` through the tool is impossible unless that plugin's HEAD is pushed to `@{u}`. <!-- id:f1cf -->
