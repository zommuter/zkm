# Roadmap <!-- fables-turn roadmap v1 -->

Executor-facing task spec. Each item is sized for ONE Sonnet session. Items are
the single source of truth — TODO.md carries only a summary line. Executors tick
checkboxes; only the reviewer adds, removes, or re-scopes items.

**Scope rule for this repo**: every item below is runnable in the zkm core repo
alone — `plugins/` is empty in a fresh worktree and the suite must stay green
without any plugin repo present. Plugin-repo work stays in TODO.md (central
ledger by design) and is NOT mirrored here.

## Phase 2 "done" definition (CONFIRMED — owner 2026-06-13)

Phase 2 is declared done when all three hold:

1. **γ schema shipped** — DONE (E1–E13 closed 2026-05-21).
2. **Store hygiene + management landed** — DONE (`zkm rm`/`zkm gc` dry-run-first,
   `zkm remote/clone/push/pull` backend-aware).
3. **Observation-period gate** — 14 consecutive days of real-store operation
   (mbsync-triggered converts + manual index/search) with zero manual
   interventions for data integrity (no orphaned CAS objects beyond `zkm gc`
   dry-run noise, no sidecar duplicate-producer recurrences, no run-guard
   false positives). Clock starts when the last [ROUTINE] item below ships;
   any intervention restarts the window.

Rationale: 1–2 are already true, so the binding criterion is 3 — it follows the
"observe before preventing" heuristic and avoids declaring victory on the same
day the last feature merges. FP-rate targets for NER are explicitly NOT part of
the gate (N9c/N9d accepted-as-is decisions stand).

## Items

- [x] Lift zkm-whatsapp `state.py` → `src/zkm/state.py` (`zkm.state`) [ROUTINE] <!-- id:f399 -->
  - **Acceptance**: a core `zkm.state` module provides `load_state(store, plugin, source)`
    and `save_state(store, plugin, source, state)`, generalizing the whatsapp module with a
    `plugin` parameter → state file `<store>/.zkm-state/zkm-<plugin>.json`, keyed by the
    resolved absolute source identifier (multi-account independence). Behavior-preserving
    LIFT, not a redesign: same atomic write (`zkm.atomic.write_atomic`), same "watermark is
    speed-only, deleting the file is safe" invariant. zkm-whatsapp's `state.py` becomes a
    thin wrapper that calls core with `plugin="whatsapp"` (its existing watermark tests must
    still pass unchanged — but that lives in the plugin repo, out of this repo's suite).
  - **Tests**: `tests/test_state.py` — `test_round_trip`, `test_keyed_by_source_multi_account`,
    `test_per_plugin_file` (all `# roadmap:f399`, currently RED).
  - **Done-check**: `uv run pytest tests/test_state.py` then the full suite green.
  - **Context**: model is `plugins/zkm-whatsapp/state.py` (43 lines). New consumers:
    zkm-signal, zkm-threema (and whatsapp). Core-runnable alone (no plugin needed).

- [x] Shared byte-identical-reemit contract helper (`zkm.testing.assert_reemit_identical`) [ROUTINE] <!-- id:ab8b -->
  - **Acceptance**: `src/zkm/testing.py` exports `assert_reemit_identical(emit)` where `emit`
    is a zero-arg callable that writes files and returns the iterable of written `Path`s; the
    helper calls `emit()`, snapshots returned-path bytes, calls `emit()` again, and asserts
    every path is byte-identical (raising `AssertionError` naming the offending path on
    difference). Document the helper in `docs/messaging-spec.md` (deterministic-emission
    section) as the contract every messaging plugin links.
  - **Tests**: `tests/test_messaging_reemit.py` — `test_deterministic_emit_passes`,
    `test_nondeterministic_emit_raises` (`# roadmap:ab8b`, currently RED).
  - **Done-check**: `uv run pytest tests/test_messaging_reemit.py` then the full suite green.
  - **Context**: used by zkm-telegram (id:6e67 reemit test) + signal/threema post-pilot.
    Core-runnable alone.

- [x] Core `zkm.pdftext` — own the scanned-only PDF routing decision (kills the zkm-pdf↔zkm-scan two-probe drift) [ROUTINE] <!-- id:9e13 -->
  - **Acceptance** (meeting D1/D2, `docs/meeting-notes/2026-06-22-1546-pdf-routing-unify-pdftext.md`):
    `src/zkm/pdftext.py` exports `PdfTextProbe(total_chars, n_pages)` (frozen dataclass),
    `probe(reader) -> PdfTextProbe`, `is_scanned_only(probe, threshold) -> bool`
    (`== total_chars < threshold`, strict), `resolve_threshold(store_config)`, and
    `DEFAULT_TEXT_THRESHOLD = 100`. `probe` accepts an already-open `pypdf.PdfReader`
    (caller owns the single parse — no double extraction); it only reads `.pages` and each
    page's `.extract_text()` (duck-typed). **Canonical measurand pinned in the docstring AND
    core `ARCHITECTURE.md` §Routing contract**: `total_chars = Σ len(page.extract_text().strip())`
    over pages, empty pages contribute 0 (adopts zkm-pdf's strip+skip-empty semantics).
    `resolve_threshold`: top-level `pdf_text_threshold:` wins → else per-plugin section →
    else `DEFAULT_TEXT_THRESHOLD`; warn (best-effort, NEVER fail) when two per-section values
    are present and differ. **Out of scope**: per-page `page_chars` (deferred to the gated
    density pilot id:c63c); the plugin migrations (d3c9/1681, plugin repos, stay in TODO.md);
    a mandatory shared-config tier (rejected — breaks M2 per-section convention).
  - **Tests**: `tests/test_pdftext.py`, marked `# roadmap:9e13` (currently RED):
    `test_probe_canonical_measurand`, `test_is_scanned_only_strict_less_than`,
    `test_one_shared_verdict_for_whitespace_heavy_pdf`, `test_resolve_threshold_default`,
    `test_resolve_threshold_top_level_wins`, `test_resolve_threshold_per_section_fallback`.
  - **Done-check**: `uv run pytest tests/test_pdftext.py` then the full suite green.
  - **Versioning**: minor bump (new public module) + tag in the same commit; the bump cascades
    every plugin `uv.lock` — that lock cascade lands with the plugin-migration items (d3c9/1681),
    not here. Core-runnable alone (pypdf not a hard runtime import — duck-typed reader).
  - **Context**: drift confirmed in the note — zkm-pdf `_extract_text`
    (`plugins/zkm-pdf/src/zkm_pdf/convert.py:389`, threshold `:62`) strips; zkm-scan
    (`plugins/zkm-scan/src/zkm_scan/convert.py:403`, threshold `:106`) does NOT → a
    whitespace-heavy PDF is skipped by BOTH. First of 3 ordered items of HARD cross-repo
    id:02bd (core → zkm-pdf d3c9 → zkm-scan 1681). TODO.md §PDF routing unification.

- [x] Refuse to start convert/scrub/index while the gamemode lock is present [ROUTINE] <!-- id:1098 -->
  (executor 2026-06-12; review-verified 2026-06-12: spec tests byte-identical
  to checkpoint, 6 RED→green confirmed by running them against the checkpoint
  tree. `GAMEMODE_LOCK_DEFAULT` in `runstate.py`, guard inside
  `RunSession.__enter__` before PID write, doctor row informational.
  ARCHITECTURE.md §D7 updated. First half of TODO id:f631.)

- [x] Self-scope `zkm index` under systemd-run for freeze/thaw control [HARD — strong model] <!-- id:62f3 -->
  (done in handoff C5, 2026-06-12: `src/zkm/selfscope.py` + cmd_index hook;
  10 tests in `tests/test_selfscope.py` green; smoke-verified on zomni —
  journal shows zkm-index.scope starting the re-exec'd command. Judgment
  calls flagged in REVIEW_ME.md.)
  - **Why HARD**: environment-dependent (systemd user manager presence,
    `INVOCATION_ID` semantics differ between service and scope units, Termux/
    Raspbian fallback), re-exec must be loop-proof and absolutely must not fire
    inside pytest/CliRunner, and the "scope exists but is frozen" collision
    case needs a judgment call (join-and-block vs fail-clean).
  - **Acceptance**: `zkm index` re-execs itself under
    `systemd-run --user --scope --collect --unit=zkm-index` when not already
    scoped, so `systemctl --user freeze zkm-index.scope` (zomni gamemode
    toggle) can freeze a running index. Skip conditions (run unscoped):
    `ZKM_SELF_SCOPED` set (loop guard, injected on re-exec), `INVOCATION_ID`
    set (already under systemd), `ZKM_NO_SELF_SCOPE=1` (opt-out; autouse in
    conftest), `systemd-run` not on PATH, or any precheck error (fail-open —
    indexing must still work on fievel/pixel). If `zkm-index.scope` already
    exists (frozen or active), exit 75 with a message stating the scope state.
    Second half of TODO id:f631; see zomni meeting note
    2026-06-11-1328-memory-swap-failsafe-llama-swap.
  - **Tests**: `tests/test_selfscope.py` marked `# roadmap:62f3` (written
    red-first during execution; monkeypatch `shutil.which`/`subprocess.run`/
    `os.execvpe` — no real systemd calls in tests).
  - **Done-check**: `uv run pytest tests/test_selfscope.py` (then full suite)

- [x] Skip the amender pass when the triggering convert created zero files [ROUTINE] <!-- id:dd89 -->
  (executor 2026-06-12; review-verified 2026-06-12: spec tests byte-identical
  to checkpoint, 2 RED→green confirmed against the checkpoint tree; both
  GUARDs still green. `not created` branch + skip notice in `cmd_convert`.
  Encoded judgment call — queued amendments wait when zero files are created —
  spawned the id:83c7 observability item below.)

- [x] Conformance: warn when an amender's convert() lacks the `created` parameter [ROUTINE] <!-- id:e1fc -->
  (executor 2026-06-12; review-verified 2026-06-12: spec tests byte-identical
  to checkpoint, 2 RED→green confirmed against the checkpoint tree; both
  GUARDs still green. Warn-level finding in `check_interface` +
  docs/plugin-spec.md §Frontmatter amendments paragraph.)

- [x] Surface the pending amendment queue in `zkm doctor` and the zero-created skip notice [ROUTINE] <!-- id:83c7 -->
  - **Acceptance**: When `<store>/.zkm-state/amendments/` holds ≥1 pending
    record (any emitter subdir), `zkm doctor` prints an `amendment queue` row
    with the total pending count and a per-emitter breakdown, e.g.
    `amendment queue 3  (ner: 2, notmuch: 1)` — informational only (does not
    flip doctor's exit code; mirrors the `gamemode lock` row). No row when the
    queue is empty or absent. Additionally, the id:dd89 skip notice appends
    the pending count when the queue is non-empty:
    `Skipping amenders (0 files created; N queued amendment(s) pending)`;
    the queue-empty message stays byte-identical to today's. User-observable:
    after a no-op mbsync convert, `zkm doctor` shows whether enrichment is
    still waiting — the observation half of the id:dd89 trade-off (queued
    amendments wait for the next non-empty convert or an explicit
    `zkm convert ner`).
  - **Tests**: `tests/test_doctor_amendment_queue.py`, marked
    `# roadmap:83c7`. RED spec:
    `test_doctor_reports_pending_amendment_queue`,
    `test_doctor_queue_row_keeps_exit_code`,
    `test_zero_created_notice_mentions_queued_amendments`.
    Already-green GUARDs (do not break):
    `test_doctor_no_queue_row_when_queue_empty`,
    `test_skip_notice_unchanged_when_queue_empty`.
  - **Done-check**: `uv run pytest tests/test_doctor_amendment_queue.py`
    (then full suite)
  - **Context**: `src/zkm/amendments.py` (`_QUEUE_DIR = ".zkm-state/amendments"`;
    queue files are `<emitter>/<sha1>.json`); `src/zkm/cli.py` `cmd_doctor`
    (informational-row pattern: `gamemode lock`) and `cmd_convert` (skip notice
    from id:dd89). Count = number of `*.json` files under the queue root — do
    NOT parse or validate record contents (cheap row, not a linter). Defer any
    new import inside the function (CLI import-speed convention).
    TODO.md §Amendment contract backlog; ARCHITECTURE.md §D5/§D7 and the
    "observe before preventing" heuristic.

- [x] `zkm doctor --entities`: census of `valid: false` entity slots [ROUTINE] <!-- id:1a6f -->
  - **Acceptance**: `zkm doctor --entities` sweeps the frontmatter of all
    store `.md` files (same exclusions as the existing md-files count: skip
    paths containing `.zkm-index` or `.git` parts) and prints a
    `suspicious entities` row: total count of `entities[]` slots carrying
    `valid: false`, plus a per-type breakdown, e.g.
    `suspicious entities 3  (iban: 2, date: 1)`. With the flag the row prints
    even when the count is 0. Slots with `valid: true` or no `valid` key are
    NOT counted; files with malformed frontmatter are skipped silently
    (doctor is a health report, not a linter). Without `--entities`, doctor
    performs no frontmatter sweep and prints no such row (the sweep is
    O(store) and parses every file — opt-in by design). The row never changes
    doctor's exit code. User-observable: the TODO.md deferral triggers
    ("entity-DB checksum-fail policy at ≥50 `valid: false` entries";
    "`valid: false` forward-flag after ≥1 month observation") finally have a
    counter to read.
  - **Tests**: `tests/test_doctor_entities.py`, marked `# roadmap:1a6f`.
    RED spec: `test_doctor_entities_counts_valid_false`,
    `test_doctor_entities_reports_zero_with_flag`,
    `test_doctor_entities_keeps_exit_code`.
    Already-green GUARD (do not break):
    `test_doctor_default_has_no_entities_row`.
  - **Done-check**: `uv run pytest tests/test_doctor_entities.py`
    (then full suite)
  - **Context**: `src/zkm/cli.py` `cmd_doctor` (reuse the `md_count` rglob
    filter); `python-frontmatter` is already a dependency. γ schema:
    `entities[]` slots are dicts with an optional `valid` bool — see
    docs/entity-model.md and `src/zkm/canonical.py`. ARCHITECTURE.md §D6 and
    the "observe before preventing" heuristic.

- [x] **Convert the 5 T1 @manual BDD scenarios in features/cli-journeys.feature to executable tests [ROUTINE]** <!-- id:9878 -->
  - **Context**: per `dotclaude-skills/docs/bdd-automation-triage-2026-06-13.md`,
    these 5 scenarios are pure CLI subprocess/file assertions and need no new
    harness: hybrid-search degraded (mock a stopped server), concurrent-lock
    exit 75, gamemode-lock exit 75 (id:1098), no-op amender skip (id:dd89),
    doctor-on-healthy-store. The other 4 scenarios stay `@manual` (fresh-machine
    quickstart, store-hygiene needing a populated CAS store, gamemode-freeze via
    `systemctl` id:62f3, progress-visibility — T2/T4).
  - **Acceptance**: each of the 5 scenarios has an executable test (subprocess
    against a scratch store, asserting exit code / stdout / files); `@manual`
    removed from each converted scenario; the repo's test command is green.
  - **Done-check**: `cd ~/src/zkm && uv run pytest -q` (or the documented test
    command in CLAUDE.md) fully green.

- [x] **Declarative-set retract primitive in `src/zkm/amendments.py`** [HARD — strong model] <!-- id:25ec -->
  (relay HARD-execute 2026-06-19: `emit_set()` declarative path added alongside
  byte-identical additive `emit()`; per-producer `producer_sets` block in
  `<md>.amendments.json` (schema 1→2, graceful read/bootstrap, no migration);
  ref-count-to-zero removal (D2), no-op-on-empty (D4a), run-scoped diff (D4b),
  fcntl-locked sidecar RMW (D4c). Dry-run via `apply_queue(dry_run=True)` +
  `plan_retractions()` (D3). 9 green tests in `tests/test_amendments_retract.py`
  (sole-producer drop, multi-producer keep, no-op-empty, idempotence,
  additive-unaffected, run-scoped, graceful-read, dry-run); full suite 578 green.
  docs/plugin-spec.md + CLAUDE.md updated; pyproject 0.14.0→0.15.0. NOTE: the
  `v0.15.0` tag + `uv publish` are OWED at integration — a relay child must not
  tag/push/publish (see REVIEW_ME). Stage 2 (zkm-notmuch f103) is routed:8b00.)
  - **Why HARD**: makes the append-only attribution sidecar AUTHORITATIVE
    per-producer state (today it is a log); a botched diff *wrongly removes
    user data* (the meeting's named failure mode). Three hard preconditions
    must land together: an fcntl writer lock (the module has NONE today —
    only `write_atomic`, which does not serialize read-modify-write; closes
    the 2026-05-14 `_apply_to_md` race), a `_SCHEMA` bump 1→2, and a
    graceful-read bootstrap of each producer's stored set from legacy
    append-only sidecars (no data migration). The destructive-failure
    blast-radius + schema/lock/migration coupling + `uv publish` is why this
    is strong-model, not [ROUTINE].
  - **Acceptance** (design D1–D5,
    `docs/meeting-notes/2026-06-18-1944-f103-tag-removal-core-semantic.md`):
    - **D1 declarative-set model**: new `emit_set()` (or `asserted_set=` on
      `emit`) records a producer's FULL current asserted set for a key. Core
      stores each producer's set per md-key in `<md>.amendments.json` and
      computes removals by diffing prior-vs-new. Additions stay
      `merge_fields` set-union — the legacy additive `emit()` path is
      byte-identical (do NOT rewrite the addition path).
    - **D2 ref-count-to-zero**: drop tag T iff (1) T ∈ producer's stored set,
      (2) T ∉ producer's new set, (3) T asserted by no other producer's
      current set. Otherwise drop only this producer's claim, keep the tag.
      Mirrors `sidecar.py:remove_producer`.
    - **D4a no-op-on-empty**: a producer that emits no/empty asserted set for
      a key retracts NOTHING — never a bulk-retract (guards an empty notmuch
      dump).
    - **D4b run-scoped diff**: removals computed ONLY for keys reported in the
      current run; a key absent this run keeps its stored set untouched
      (created-scoping, id:63bb).
    - **D4c lock**: amendments-sidecar writer is fcntl-locked (mirror
      `sidecar.py:_sidecar_lock`).
    - **D4d graceful read**: `_SCHEMA` bumped with graceful read of legacy
      append-only sidecars — stored set bootstrapped from the union of prior
      applied `fields` for that producer; no data rewrite.
    - **D3 dry-run**: non-mandatory dry-run listing of pending retractions
      before apply (free under the declarative diff).
    - Docs: update `docs/plugin-spec.md` (amendment section) + the CLAUDE.md
      multi-producer note. Bump `pyproject.toml` version, tag `vX.Y.Z` in the
      same commit, `uv publish`.
  - **Tests**: `tests/test_amendments_retract.py`, marked `# roadmap:25ec`
    (written red-first; currently SKIPs on missing `emit_set`). Required green
    once shipped: sole-producer drop, multi-producer keep (D2),
    no-op-on-empty (D4a), idempotence, additive-emit unaffected. Add a
    run-scoped-diff (D4b) and a graceful-read/bootstrap (D4d) case during
    implementation.
  - **Done-check**: `uv run pytest tests/test_amendments_retract.py` then the
    full suite green.
  - **Context**: `src/zkm/amendments.py` (221 lines: `emit`, `apply_queue`,
    `merge_fields`, `_apply_to_md`, `_read_applied_hashes`, sidecar at
    `<md>.amendments.json`); the lock/remove-producer pattern to mirror is in
    `src/zkm/sidecar.py`. Stage 2 (zkm-notmuch declarative emit = f103) is a
    SEPARATE session against the released API — already routed to the
    zkm-notmuch inbox (`routed:8b00`); do NOT bundle repos. TODO.md
    §Amendment contract backlog.

- [x] Add `entities` to `_SET_FIELDS` so declarative set-retraction applies to entities (not just tags) [ROUTINE] <!-- id:29ac -->
  - **Acceptance** (meeting D1, `docs/meeting-notes/2026-06-23-1807-zkm-amendments-removal-coherence.md`):
    `emit_set` / `apply_queue` / `plan_retractions` retract values from the `entities`
    frontmatter field by the same D2 ref-count-to-zero rule already applied to `tags`. The
    shipped retraction machinery (id:25ec) iterates `_SET_FIELDS = ("tags",)`; this adds
    `"entities"`. Because entity records are typed dicts `{scope, type, value}` (NOT
    hashable strings), the producer-set storage (`_producer_stored_set`,
    `_all_current_sets_excluding`), the diff (`_retractable_values`), and the apply-path
    filter (`_apply_to_md`, ~line 429) must key entities by their `(scope, type, value)`
    tuple — the SAME dedup key `merge_fields` already uses (`_ent_scope(e), e["type"],
    e["value"]`) — not by string identity. Additive `emit()` for entities stays
    byte-identical (`merge_fields` entity-union path unchanged). A producer's empty asserted
    entity set retracts only its own claims (D4a, mirrors tags). Entities ride the existing
    `producer_sets` block; store each producer's asserted entity set in a JSON-serializable
    keyed form and document the chosen representation.
  - **Tests**: `tests/test_amendments_entity_retract.py`, marked `# roadmap:29ac` (RED):
    `test_entity_sole_producer_dropped_when_unasserted` (the genuine RED — an unasserted
    entity is currently NOT retracted because `entities ∉ _SET_FIELDS`),
    `test_entity_kept_when_other_producer_still_asserts` (D2 keep, keyed on the tuple).
  - **Done-check**: `uv run pytest tests/test_amendments_entity_retract.py` then the full
    suite green.
  - **Context**: `src/zkm/amendments.py` — `_SET_FIELDS` (line 51), retraction helpers
    (lines 362–408), apply-path filter (lines 427–438), `merge_fields` entity dedup
    (lines 249–258), `_ent_scope` (line 269). Prerequisite for the zkm-ner scrub↔cache
    tombstone fix (TODO/meeting id:7b4e; children 0566/fa5a are zkm-ner *plugin* repo work,
    NOT this ROADMAP). Core-runnable alone. TODO.md §Amendment contract backlog.

- [x] Embeddings index → annex T3 with a drop-superseded-key hook; `bm25.pkl` → regenerate-on-restore (D3) [ROUTINE] [INTENSIVE — local-llm] <!-- id:7e21 -->
  - **Acceptance** (storage-tiers meeting D3, `docs/meeting-notes/2026-06-24-1350-storage-tiers-restore-sync.md`):
    (1) The store gitattributes template (`src/zkm/store.py`) annexes the embeddings
    artifact (`.zkm-index/embeddings.npz`, written by `embed.py:211`
    `np.savez_compressed`, a full non-append rewrite) — i.e. it is NOT forced to git like
    the CAS-json sidecars; it stays under the `annex.largefiles=anything` regime (add an
    explicit rule if the current globs don't already cover `.zkm-index/`). (2) `save_index`
    (`src/zkm/index.py:256`) / the post-`zkm index` path drops the *superseded* annex key
    once the new `embeddings.npz` is committed (`git annex drop --force` the old key), so
    exactly one `embeddings.npz` annex key is present after two successive index runs — no
    annex pileup of stale embedding blobs. (3) `bm25.pkl` (`index.py` full pickle rewrite,
    cheap TF-over-markdown, no model) is **never synced**: regenerate-on-restore; ensure it
    is NOT annex-pinned in a way that would carry stale copies. Compression stays on (the
    whole-file transfer is inherent and accepted; the escape hatch — uncompressed `.npy` +
    rsync-delta — stays documented-but-unbuilt).
  - **Tests** (`tests/test_index.py` or a new `tests/test_index_annex_drop.py`,
    marked `# roadmap:7e21`, RED): a hermetic test that stubs the embedder
    (monkeypatch as the existing `test_index.py` tokenize-spy tests do — do NOT load a real
    model in CI) and asserts that after two index/save cycles exactly ONE `embeddings.npz`
    annex key remains (`git annex find` / key-count under `.git/annex/objects`), the old key
    being dropped. A `check-attr` assertion that `.zkm-index/embeddings.npz` resolves to
    `annex.largefiles=anything` (not `nothing`). The **real-store** done-check (two live
    `zkm index` runs on `~/knowledge`, model-loading) is the INTENSIVE part — run under
    `--allow-intensive`/`--afk`, serially-alone; the hermetic test is the suite gate.
  - **Done-check**: `uv run pytest tests/test_index*.py` then the full suite green; one
    `embeddings.npz` annex key after two stubbed index cycles.
  - **Context**: `src/zkm/embed.py:34` (`_NPZ_FILE = ".zkm-index/embeddings.npz"`), `:211`
    (`np.savez_compressed`); `src/zkm/index.py:256` (`save_index`), `:269` (`load_index`).
    The D1 CAS-json rule (`**/_objects/**/*.json annex.largefiles=nothing`, id:6c4f, shipped
    this window) is the sibling pattern but the OPPOSITE direction — embeddings STAY annexed.
    Carried by the future `zkm push` annex copy (id:998b, separate item); no separate
    index-sync lever. `[INTENSIVE — local-llm]`: the real done-check loads the embedding
    model. TODO id:7e21.

- [x] Document the day-file footer-manifest layout in `docs/messaging-spec.md` [ROUTINE] <!-- id:2b0b -->
  - **Acceptance** (footer meeting D5, `docs/meeting-notes/2026-06-26-1746-day-file-frontmatter-footer-manifest.md`):
    replace the pre-w6f minimal-manifest schema (`docs/messaging-spec.md:229-237`) with the
    end-of-file `<!-- zkm:manifest … -->` footer layout, AND document the shipped
    `text` / `quoted_key_id` / `media` manifest fields (current spec gap). Make explicit that
    signal/threema stubs inherit the footer shape, NOT the old frontmatter-manifest shape.
    No code change — `docs/messaging-spec.md` only.
  - **Done-check**: `grep -q 'zkm:manifest' docs/messaging-spec.md` and the
    `messages:`-in-frontmatter schema block is gone; full suite still green
    (`uv run pytest -q`).
  - **Context**: pairs with the shipped whatsapp footer migration (TODO id:767e, plugin repo).
    TODO.md §Frontmatter field governance. Core-runnable alone.

- [x] Add the sidecar-vs-in-document heuristic to `docs/object-storage.md` [ROUTINE] <!-- id:68fc -->
  - **Acceptance** (footer meeting D4): document the heuristic in `docs/object-storage.md` and
    cross-ref it from `docs/messaging-spec.md`: single-producer + in-band + primary-data →
    in-document (frontmatter/footer); multi-producer + out-of-band + machine-bookkeeping
    (values mirrored to frontmatter) → sidecar. State that the amendment ledger is a sidecar
    under this rule, consistently. No code change — docs only.
  - **Done-check**: the heuristic text is present in `docs/object-storage.md` with a
    cross-ref from `docs/messaging-spec.md`; full suite still green.
  - **Context**: `docs/meeting-notes/2026-06-26-1746-day-file-frontmatter-footer-manifest.md` D4.
    Core-runnable alone.

- [x] Spec/conformance note: footer-manifest layout is the `messaging-spec.md` contract [ROUTINE] <!-- id:03ae -->
  - **Acceptance**: add an explicit conformance note in `docs/messaging-spec.md` that the
    per-chat-day footer-manifest layout IS the contract signal/threema (and future chat
    plugins) must inherit, so a new plugin stub does not ship the old frontmatter-manifest
    shape. Smallest of the trio; lands with id:2b0b/68fc in one execute session. Docs only.
  - **Done-check**: the conformance note is present in `docs/messaging-spec.md`; full suite green.
  - **Context**: `docs/meeting-notes/2026-06-26-1746-day-file-frontmatter-footer-manifest.md`.
    Core-runnable alone.

- [x] Unify `build_index` file enumeration on the TOCTOU-safe guard + surface dropped files [ROUTINE] <!-- id:f1d7 -->
  - **Reverse-handoff context**: the full-rebuild crash hotfix (commit `6dc0132`, `index.py`
    full-rebuild loop `try/except FileNotFoundError: continue`) is **VERIFIED GREEN this review**
    — `tests/test_index_toctou.py::test_full_rebuild_skips_vanished_file` passes against the
    shipped implementation (genuine fix, not a weakened spec). Two follow-ups remain open:
  - **Acceptance**: (1) the *incremental/fast* path (`index.py:204-206`) still does
    `if not path.exists(): continue` then a bare `path.stat()` — the same TOCTOU window the
    full-rebuild path now guards. Unify both paths on the `try/except FileNotFoundError: continue`
    form so a file that vanishes between the existence check and `stat()` is skipped, not fatal.
    (2) the skip is currently silent; per the repo's "no silent caps" instinct, count and `log()`
    the dropped-vanished paths so a truncated index isn't mistaken for a complete run (decide the
    surface — a `log()` line per drop and/or a returned/logged count; do not invent a noisy default).
  - **Tests**: `tests/test_index_toctou.py` — `test_incremental_path_survives_stat_toctou`
    (`# roadmap:f1d7`, currently **RED**: the incremental loop crashes when `stat()` raises after
    `exists()` passed). Add an assertion for the drop-count/log surface once (2)'s interface is chosen.
  - **Done-check**: `uv run pytest tests/test_index_toctou.py` green, then the full suite green.
  - **Context**: real production incident — a live `zkm index` over `~/knowledge` crashed at 43%
    on a path removed mid-walk (chat by-id rename / Syncthing churn). TODO id:f1d7. Core-runnable alone.

## Pointers (NOT executor items — wrong repo or gated)

- zkm-whatsapp W-series (W6f media manifest, W-key secret source, W8 owner-JID
  autodetect, W10 Syncthing auto-decrypt, W11 number-change tracking) — live in
  `plugins/zkm-whatsapp` (own repo). W9 WAL-safe backup handling shipped
  v0.3.0 (2026-06-11); no core-side blocker remains.
- NER FP backlog (N9c pipe-cell filter, HTML-entity artefacts) — fix paths are
  in zkm-ner / zkm-eml repos per TODO.md; core `scrub.py` is only the dispatcher.
- SOC1–SOC6 zkm-social — gated on GitHub remote + user review (TODO id:e395).
- Stage 2 OIDC trusted publishing — cross-repo CI work across all 7 repos.
