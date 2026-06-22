# zkm architecture — decisions and rationale

Companion to `CLAUDE.md` (layout, commands, gotchas). This file records WHY the
system is shaped the way it is, including alternatives that were considered and
rejected. Decision provenance lives in `docs/meeting-notes/` — cited inline.

## Pipeline shape

```
fetch (external, optional)        zkm fetch / mbsync / Syncthing
        │ deposits raw files into <store>/inbox/…
        ▼
convert (plugins)                 source → frontmatter'd .md under typed dirs
        │ auto-commit, then amenders run scoped to created files
        ▼
store (git repo)                  markdown tree = single source of truth
        ▼
index                             BM25 (rank-bm25) + dense embeddings (numpy)
        ▼
search / query                    hybrid RRF fusion; LLM only at query time
```

## D1 — Markdown tree + git, not a database

The store is a plain git repo of human-readable `.md` files with YAML
frontmatter. All derived metadata (auto-tags, NER entities) is **written back
to frontmatter** — the md is always source of truth; every cache/index under
`.zkm-index/` and `.zkm-state/` is re-derivable (`docs/restore.md`).

- **Rationale**: greppable, diffable, survives zkm itself dying; git history
  doubles as the temporal index (HEAD = now, log/diff = evolution —
  DiffMem-inspired, `docs/temporal-queries.md`); sync = `git pull`.
- **Rejected**: SQLite/local DB as primary store. A pivot trigger is on record
  (local DB with git-tracked autoexport-on-write) if (a) sidecar concurrent-write
  bugs become frequent, (b) WebUI read-write load makes file locking painful, or
  (c) cross-machine sync stops being git-based. See TODO.md "Future re-evaluation
  trigger".

## D2 — BM25 first; dense embeddings as additive hybrid

Phase 1 shipped BM25-only (`index.py`, rank-bm25 + snowballstemmer). Phase 2
added an OpenAI-compatible `/v1/embeddings` dense index (`embed.py`, plain
numpy arrays on disk) fused with BM25 via Reciprocal Rank Fusion; `--no-dense`
and graceful fallback keep BM25 the floor. See `docs/hybrid-search.md`.

- **Rationale**: zero-infra (no vector DB process), index is re-derivable,
  endpoint is swappable (llama-swap/bge-m3 in the field test).
- **Rejected**: vector DB (Milvus/Chroma) — operational weight for a one-user
  CLI; LangChain — dependency policy is stdlib > small lib > framework.

## D3 — Plugin polyrepo with dual discovery

Each converter is its own git repo (own version tags, own PyPI wheel).
Discovery is the union of `importlib.metadata.entry_points(group="zkm.plugins")`
and a `plugins/*/plugin.yaml` filesystem scan, deduped by name with
**filesystem winning** (a dev symlink shadows the installed wheel).

- **Rationale**: end users get `uv tool install zkm --with zkm-<name>` (sealed
  env, deps resolved); developers get live-editable symlinks/clones. Shadowing
  makes "test my local change against the real store" a non-event.
- **Rejected**: monorepo (couples release cadences; plugins have heavy,
  disjoint deps — spaCy, pypdf, vobject); single discovery path (either breaks
  dev flow or breaks wheel installs).
- **Consequences**: `zkm plugin remove` refuses on wheel-origin plugins
  (rmtree into site-packages would be destructive); dev-symlink plugins get
  their own `.venv` site-packages injected at load (`_inject_plugin_venv`,
  SB2) because the core venv lacks plugin-only deps.

## D4 — Object storage: CAS + sidecars in core, not per plugin

`zkm.atomic`, `zkm.hashing`, `zkm.cas`, `zkm.sidecar`, `zkm.inbox` are the
single implementation of the binary-object contract (`docs/object-storage.md`):
originals live as content-addressed objects, inbox symlinks point at them, and
`.origin.json` sidecars track producer .md files. `zkm rm` decrements
producers and removes orphaned links/objects; `zkm gc` sweeps unreferenced
objects. Both are **dry-run by default** (`--apply` to execute) — the
repo-wide convention for destructive commands (also `zkm scrub`).

- **Rejected**: per-plugin copies of CAS/sidecar code (drifted in practice —
  Phase 2 session 4 deleted them); a generic content-management API
  (`zkm add`, `store.put()`) — explicitly out of scope, it turns zkm into a
  filesystem manager and every new plugin would touch core.

## D5 — Amender model: additive set-union, scoped sweeps

Amenders (`kind: amender`, currently zkm-ner) run automatically after every
`zkm convert <plugin>` (`--no-amenders` to skip) and enrich frontmatter via
set-union merge — they only add, never replace.

- **Sweep scoping** (id:63bb, `docs/meeting-notes/2026-06-11-1012-…`): the CLI
  passes the triggering convert's `created: list[Path]` to amenders that
  declare the param (capability-probed). Chosen Option A (created-only) over
  B (∪ missing-sidecar — entity-less files would be re-walked forever) and
  C (∪ cache-stale — detecting staleness costs a read+hash per file ≈ full
  sweep). Stragglers (files created under `--no-amenders` or after an amender
  crash) are picked up only by an explicit `zkm convert ner`.
- **Replace-mode** (single-producer-per-field) is deliberately NOT built;
  `zkm scrub <plugin>` is the workaround for stale entities. Meeting trigger:
  a third amender wants replace semantics, or scrub stops sufficing.
- **Current direction (2026-06): stabilize the amender contract before adding
  new amender/extractor types.**

## D6 — γ typed-entity schema; no identity merge

Frontmatter `entities[]` carries typed slots (person, org, place, amount,
iban, fingerprint, …) deduped on `(scope, type, value)`. Values are **mention
strings, never UIDs** — no `id:`, no `same_as:`, no cross-document clustering.
`scope:` separates provenance lanes (body NER vs `contact` vs `profile.*` vs
signature/salutation) so structured-first sources coexist with NER output.

- **Rationale**: names are not unique; heuristic auto-merge poisons the store
  silently. Alias linking and mention→entity promotion are Phase 4,
  human-confirmed pairs only. PGP fingerprints are join-grade values but
  still NOT a person-merge license (2026-06-04 meeting).
- **Rejected**: entity UIDs + resolution layer (research-grade, unbounded FP
  cost); gazetteer recognition overlays (forward-flagged, not v1).

## D7 — Concurrency: PID-file guards, not locks or daemons

`convert`/`scrub`/`index` refuse to start when a conflicting run exists
(conflict matrix in `docs/concurrent-runs.md`), exiting **75** (`EX_TEMPFAIL`)
so cron/mbsync hooks can retry. Liveness via `os.kill(pid, 0)`; stale PID
files self-clean. `RunSession` doubles as the `zkm status` progress surface
(SIGUSR1 → dd-style progress line). The same machinery hosts the gamemode
lock guard (shipped id:1098, 2026-06-12): when the lock file exists
(`$ZKM_GAMEMODE_LOCK`, default `/tmp/zomni-gamemode.lock`), `RunSession`
exits 75 before writing any PID file so triggered jobs don't compete with a
game for CPU/RAM. `ZKM_BYPASS_RUN_GUARD=1` bypasses both guards; `zkm doctor`
reports the lock informationally.

- **Rejected**: flock-per-file (the race is a cross-file sidecar
  read-modify-write, not single-file); a queue daemon (deferred to Phase 3
  behind an N=2 attach-semantics trigger). Known TOCTOU window between
  precheck and PID write is accepted — `zkm doctor` reports race survivors
  (observe before preventing).
- A second guard (`zkm.devcheck`) blocks editable-install WIP code from
  touching the live store: state-modifying commands require a clean source
  tree (`ZKM_BYPASS_DIRTY_CHECK=1` to override).

## D8 — LLM only at query time, endpoint-agnostic

Ingest is deterministic (parsers, spaCy NER); no LLM writes to the store.
`zkm query`/`expand`/`doctor` speak to any OpenAI-compatible endpoint
(local llama-swap or remote). Embeddings ditto.

- **Rationale**: store integrity must not depend on model availability or
  drift; local-first privacy; endpoints are config, not code.

## Conventions that encode decisions

- **Exit codes**: 75 = temporary refuse-to-start (retry later); 130 = user
  cancel (SIGINT convention); 1 = real error.
- **Dry-run by default** for anything destructive (`rm`, `gc`, `scrub`);
  `--apply` + auto-commit with scoped `git add`.
- **Conformance over review**: `zkm test <plugin>` (`conformance.py`)
  machine-checks the plugin contract (manifest, interface signature,
  frontmatter of dynamic-tier output) — see
  `docs/meeting-notes/2026-06-01-1616-zkm-test-conformance.md`.
- **Versioning**: bump-and-tag per repo (`vX.Y.Z`, loose-0.x); every
  `pyproject.toml` version change is tagged in the same commit.

## Routing contract

`zkm.pdftext` owns the single decision for scanned-only PDF routing (ROADMAP id:9e13).
All plugins that need to distinguish scanned-only PDFs from text PDFs MUST call this
module — never reimplement the measurement locally.

**Canonical measurand (pinned)**:
```
total_chars = Σ len(page.extract_text().strip()) over all pages
```
Pages whose `extract_text()` returns `None` contribute 0. Empty pages (stripped to `""`)
contribute 0.

**Decision**: `is_scanned_only(probe, threshold)` is `total_chars < threshold` (strict
less-than). A PDF at exactly the threshold is NOT scanned-only.

**Threshold resolution** (`resolve_threshold(store_config)`):
1. Top-level `pdf_text_threshold` wins.
2. Per-plugin-section `pdf_text_threshold` fallback; warns if two sections disagree.
3. `DEFAULT_TEXT_THRESHOLD = 100`.

## Plugin contract

Two cross-plugin rulings confirmed 2026-06-13 (batch triage):

- **RuntimeError error-contract**: A zkm plugin signals runtime/CLI failure by
  raising `RuntimeError`; the core amender loop catches it and prints a one-line
  WARN (does not abort the sweep).
- **Version derivation**: Canonical version = `pyproject.toml` metadata; a
  plugin's `PLUGIN_VERSION` is derived via `importlib.metadata` with a
  `plugin.yaml` fallback.
