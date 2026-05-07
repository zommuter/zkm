# zkm Phase 2 plan

## Goals

- Daily usable for one user end-to-end (stable rescan, real store indexed and queryable)
- Publishable for external use: one-screen quickstart, no data-loss footguns
- No YAGNI: every item has a named user need or a second-plugin justification

## In scope

1. **Hot-fix**: zkm-eml producer-dedup invariant (sidecar duplicate entries on rescan)
2. **Core library modules**: `zkm.atomic`, `zkm.hashing`, `zkm.cas`, `zkm.sidecar`, `zkm.inbox` — single, tested implementation of the plugin-spec CAS + sidecar contract
3. **Plugin migration**: zkm-notes (fix atomic write) and zkm-eml (drop in-plugin copies)
4. **Hygiene commands**: `zkm rm`, `zkm gc`
5. **Store management** (`zkm remote/clone/push/pull`) — git-annex/lfs aware (already in TODO.md)
6. **Field-test loop** on a real store with bge-m3 via llama-swap (already in TODO.md)

## Explicitly out of scope (Phase 3)

- Generic content-management API (`zkm add`, `zkm.store.put()`): turns zkm into a filesystem manager; every additional plugin requires touching core. No named use case that isn't served by the smaller library helpers.
- Entity extraction / NER
- WebUI / FastAPI server
- New plugins beyond what the field test concretely demands

## Sequencing (each session independently shippable)

| # | Session | Output |
|---|---------|--------|
| 1 | Hot-fix zkm-eml | Patched `originals.py` dedup key + `thread_index.py` except + regression test |
| 2 | Phase 2 docs | `docs/phase2-plan.md`, `docs/object-storage.md`, `docs/meeting-notes/`, CLAUDE.md + plugin-spec.md + TODO.md updated |
| 3 | Core library | `zkm.atomic/hashing/cas/sidecar/inbox` + unit tests |
| 4 | Plugin migration | zkm-notes + zkm-eml import from core; in-plugin copies deleted |
| 5 | Hygiene commands | `zkm rm` + `zkm gc` (only after one week of session 4 in real use) |

Sessions 1–2 unblock everyday use and data-loss correctness. Sessions 3–5 are the architecture cleanup, each independently shippable.

## Ready-to-publish criteria

- `zkm init` → `zkm plugin add` → `zkm convert` → `zkm search` works on a fresh machine in under 5 minutes from the README
- Rescan is a no-op when source hasn't changed (regression-tested in zkm-eml)
- One external user has installed zkm and reported a usable result
