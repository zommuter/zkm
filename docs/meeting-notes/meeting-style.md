# Meeting-Note Format

Used for design decisions that need multiple viewpoints before committing to code.
Invoke with: *"Do a meeting à la `docs/meeting-notes/...`"*

## Personas

| Name | Role | Lens |
|------|------|------|
| **Tobias** | Product owner | Frames the question; makes the final call |
| **Archie** | Architect | Knows the code; proposes architecturally sound solutions; anchors claims in file paths and line numbers |
| **Riku** | Devil's advocate | Names specific risks; applies rules mechanically; pushes back until the proposal survives scrutiny |
| **Petra** | Productivity | Enforces scope; applies the N=2 rule; names what is explicitly out of scope |

### The N=2 rule (Petra's lens)
Before landing a new abstraction, name at least two distinct consumers. If you can't, defer.
Both must be real — "future plugin X" counts only if X is already on the near-term roadmap.

### Riku's checklist
- What breaks if this goes wrong?
- What bias does the proposed aggregation or design introduce?
- What is the minimum evidence that would change this decision?

## Onboarding new personas per meeting

When a meeting needs a perspective the four standing personas don't cover, add an ad-hoc persona for that meeting only. Give them a short intuitive name and a one-sentence lens statement. Examples: **Mira** (multimodal ML — classifier cost, failure modes, privacy); **Flora** (information-flow architecture — content-type vs file-format, routing topology). List them in the **Attendees** line with "(new)" suffix.

Ad-hoc personas persist only in the meeting note; they are not added to the standing table above unless they recur across multiple meetings.

## Warrantability self-check

Before facilitating a meeting, evaluate the request against the "When to call a meeting" criteria below. If the request fails (e.g., looks like a bug fix, a one-liner, or an already-decided feature), respond with an "are you sure you want a meeting?" prompt and a brief reason it might be overkill — before running the agenda. If the request clearly passes, note that it was warranted and proceed.

## Past-meetings audit

At the start of each new meeting, briefly audit prior meetings' action items against `TODO.md` and the current codebase state. Flag any orphans (action items neither done nor tracked in `TODO.md`) before the new agenda starts. "Tracked but not yet implemented" is acceptable; "neither done nor tracked" is not.

## Format

Each note lives at `docs/meeting-notes/YYYY-MM-DD-<slug>.md`.

```
# YYYY-MM-DD — Short title

**Attendees:** Tobias (product owner), Archie (architect), Riku (devil's advocate), Petra (productivity)
**Topic:** one sentence

## Agenda
Numbered list of questions the meeting will resolve.

## Discussion
Named exchanges. Each speaker owns a viewpoint; they can be corrected but not abandoned
without argument. File paths and line numbers are cited when code is discussed.

## Decisions
Bullet list. Specific enough to serve as an implementation spec.
Each decision names what is explicitly out of scope.

## Action items
Checklist. Each item names the session, the file, and the contract
(what a future test would verify).
```

## Interactive mode

Meetings can run interactively with Tobias participating turn-by-turn. Protocol:

1. The assistant accumulates the meeting transcript in the plan file turn-by-turn during plan mode.
2. At each natural Tobias decision point (roughly every 4–8 exchanges), the assistant poses the decision via `AskUserQuestion` with:
   - **Embedded tl;dr** in the question text — standalone-readable even if the prior transcript is not visible in the prompt UI. Summarise the state of play in 2–3 sentences before stating the choice.
   - **3 implication-driven options** — derived from the personas' reasoning, not from generic pro/con pairs. Each option label is 1–5 words; description explains what it commits to and what it defers.
   - **Recommended option first**, labelled "(Recommended)" at the end, when the personas converge.
   - Freeform "Other" is provided automatically by the tool.
3. The assistant continues the meeting in the next turn based on Tobias's answer, appending to the transcript.
4. When all agenda items reach decisions, the assistant exits plan mode and writes the final transcript to `docs/meeting-notes/YYYY-MM-DD-<slug>.md`.

Interactive mode is appropriate whenever Tobias wants to steer the design in real time rather than review a completed transcript.

## When to call a meeting

- A TODO item's scope is ambiguous (plugin vs. core, Phase 2 vs. Phase 3).
- A design decision has a non-obvious trade-off that would be questioned later.
- Two or more plausible approaches exist and the wrong choice is hard to reverse.

Do **not** call a meeting for:
- Bug fixes with a clear root cause.
- Adding a test or doc for an already-decided feature.
- One-liner changes.

## Past meetings

- [2026-05-07 — Object storage scope](2026-05-07-object-storage.md) — CAS/sidecar/inbox as core library vs. plugin code; `zkm rm` / `zkm gc` sequencing
- [2026-05-08 — Doc chunking scope](2026-05-08-doc-chunking.md) — embed-side chunking as core feature; char-window MVP; file-level RRF aggregation
- [2026-05-08 — Next plugins](2026-05-08-next-plugins.md) — photo→pdf→scan order; fan-out overlap policy; whatsapp deferred to scoping meeting
- [2026-05-08 — Information flow](2026-05-08-information-flow.md) — drop A/B/C; extraction-cache + frontmatter-amendment replace pipeline; zkm-notmuch as first amender; meeting now interactive
