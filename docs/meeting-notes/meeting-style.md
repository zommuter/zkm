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
