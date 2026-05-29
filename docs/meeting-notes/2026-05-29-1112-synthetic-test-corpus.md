# 2026-05-29 — Synthetic test corpus of fake markdown emails

**Started:** 2026-05-29 11:12
**Session:** 5cf6bef2-2630-4e29-9244-8f4adab484f3
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 📬 Pim (PIM engineering — email realism; re-onboarded from registry)
**Topic:** Build a small synthetic corpus of fake markdown emails to test/iterate against, instead of waiting for the multi-hour real `~/knowledge` embed rebuild — and if so, how?

## Agenda
1. Purpose & scope: throwaway dev store, committed durable test fixture, or both? (N=2 check)
2. Generation method: hand-author `.md` (A) vs synthesize `.eml` → real `zkm convert eml` (B) vs deterministic generator (C). The title/subject drift trap.
3. Realism & pathological anchors: happy-path only, or regression anchors?
4. Privacy/genericness + offline coverage.

## Discussion

### Agenda 1 — Purpose & scope

🏗️ **Archie:** The trigger is being blocked behind the [402c] embed rebuild (~12h+) wanting something to run `zkm search`/`query` against *now* — a throwaway dev store. But "for tests" means a committed fixture. Different artifacts, different lifetimes — but they can share one source. Today the suite has *no* committed `.md`; every test hand-writes notes inline via a `_write_note` helper copy-pasted across `test_search.py:15-27` and `test_index.py`. Centralization win regardless.

✂️ **Petra:** N=2 check. Inline `_write_note` already covers unit tests. New consumers: (1) a CLI-runnable dev store to eyeball search without the rebuild, (2) an end-to-end index→search→query fixture more realistic than three-word notes. Legitimate N=2. Resist a sprawling "realistic corpus" that becomes its own maintenance project.

😈 **Riku:** Lifetime mismatch. A `/tmp` dev store rots harmlessly; a *committed* fixture is forever and pins shape. "Both" is fine only if the committed part is small, regenerable, drift-guarded.

📬 **Pim:** Real email is threads, quoted replies, signatures — not isolated messages. Even a "small" representative fixture needs ≥1 reply chain. Cheap if generated right, expensive if hand-authored — scope interacts with method (Agenda 2).

🏗️ **Archie:** Rec: **both, sharing one source** — committed happy-path corpus under `tests/fixtures/corpus/` + `scripts/seed_dev_store.py` copying it into a store and running `zkm index --no-embed` for sub-second offline iteration.

**DECISION (Agenda 1):** Both, sharing one source. **Forward-flag (Tobias):** "maybe later even some actual email-based privacy-filtered fake messages as well?" — future input: real `.eml` → scrub PII → realistic anonymized fixtures. Out of current scope, but load-bearing on Agenda 2: treat `.eml`/`.mbox` as the interchange format so synthetic *and* future scrubbed-real messages flow through the same `zkm convert eml` producer.

### Agenda 2 — Generation method (the drift trap)

🏗️ **Archie:** (A) hand-author `.md`; (B) synthesize `.eml` → real `zkm convert eml`; (C) deterministic generator. Decisive fact against pure A: the **title/subject drift trap** — indexer (`index.py:65`) and embed prefix (`embed.py:479`) read frontmatter `title`, but the real converter (`zkm_eml/frontmatter.py:44`) writes `subject`, never `title`. Hand-authored `.md` encodes a guess that's wrong-but-looks-right or faithful-but-unindexed; either way teaches tests a schema that doesn't match production.

📬 **Pim:** The forward-flag seals it. Privacy-filtered real emails are `.eml` in → scrubbed `.eml` out → converted. If the corpus pivots on `.eml`, synthetic and scrubbed-real share one code path. Hand-authored `.md` strands the forward-flag.

😈 **Riku:** B couples generation to zkm-eml. Condition: converted `.md` committed once, regenerated only on schema change → plugin is a *generation-time* dependency (hand-run script), not run-time. Then B is clean.

✂️ **Petra:** B+C for happy-path; **pathological anchors stay hand-authored (A)**, separate dir. Mixing off-schema docs into the faithful corpus corrupts the schema reference.

😈 **Riku:** Determinism: converter hashes raw `.eml` bytes, derives `thread_id` from root Message-ID. Generator must emit **byte-identical** `.eml` (fixed `Date:`, hardcoded Message-IDs, no `random`/now()). `CORPUS_MANIFEST.json` (plugin version + input sha256s, asserted by a test) turns a schema bump into a loud "regenerate" failure.

**DECISION (Agenda 2):** B+C hybrid. (Tobias: "but eml tests should reside in the eml plugin repo, no?" → Agenda 2b.)

### Agenda 2b — Repo ownership split

🏗️ **Archie:** **zkm-eml** owns: synthetic `.eml` generator, expanded `.eml`/`.mbox` fixtures (extends the ~32 there), convert-faithfulness **roundtrip test** (drift sentinel). **core zkm** owns: frozen committed `.md` corpus under `tests/fixtures/corpus/` (opaque static input, core never imports `zkm_eml`), centralized `conftest.py` fixtures, `scripts/seed_dev_store.py`, index/search/query/embed tests.

😈 **Riku:** Resolves the coupling objection — core run-time dependency on the plugin is zero. Plugin enters only at manual regeneration (documented cross-repo step). Drift sentinel lives in the only repo that can compare converter output to expectation.

📬 **Pim:** Core's corpus is a snapshot frozen at regen time; if schema drifts and you forget to regenerate it silently ages — but zkm-eml's roundtrip test fails loudly, so "core corpus stale" is implied by "zkm-eml red." Document that causal link.

### Agenda 3 — Realism & pathological anchors

📬 **Pim:** Happy-path floor: handful of messages + **≥1 reply chain** (`In-Reply-To`/`References` so `thread_id`/`thread`/`in_reply_to` are real), varied `tags`/`participants`/`date`/`entities`. Reuse the `chain_{a,b,c,d}.eml` pattern.

✂️ **Petra:** Pathological anchors hand-authored (A), separate `tests/fixtures/pathological/`. Three: (1) `oversized_entities.md` — `_chunk_texts` prefix ≤500; (2) `html_entity_ner.md` — indexer skips `valid:false`; (3) `subject_only.md` — subject absent from BM25, flips on a future converter change.

😈 **Riku:** #1 non-negotiable (just hit it, cap just landed). #2/#3 cheap, document gotchas. Don't balloon beyond *known* bugs.

**DECISION (Agenda 2b/3):** Split as described; all three pathological anchors.

### Amendment session — a `zkm test <plugin>` command? (raised by Tobias mid-meeting)

🏗️ **Archie:** Two meanings: (1) test *runner* (shells out to plugin pytest); (2) contract *conformance validator* (core checks plugin-spec conformance — `plugin.yaml`, `convert()` signature, `creates_dirs`, frontmatter schema). Interpretation 2 is core-worthy (core owns the contract; N=2 across eml/photo/pdf/scan/notmuch/ner).

✂️ **Petra:** Interpretation 1 doesn't earn a command (`make test-plugins` loop does it — lever-first). Interpretation 2 is real but *not this meeting*.

😈 **Riku:** Interpretation 2 *consumes* today's work — the synthetic-`.eml`-through-convert harness is the fixture it would run. Build corpus + roundtrip first; conformance command sits on top later.

📬 **Pim:** Today's roundtrip test is the prototype of interpretation 2 scoped to one plugin. Generalizing to core `zkm test <plugin>` is a natural Phase-2 follow-up with real evidence of what to assert.

**DECISION (Amendment):** Defer `zkm test <plugin>`; conformance-validator interpretation, builds on the roundtrip harness. File as TODO.

## Decisions

- **Both, one shared source.** Committed happy-path `.md` corpus + dev-store seed script sharing the same generated source. *Out of scope:* corpus-scale realism (thousands of docs); the "~864-text 500-wall" is a server-slot issue, not reproducible by doc count and explicitly not modeled.
- **Generation = B+C.** Deterministic generator emits byte-stable synthetic `.eml`; real `zkm convert eml` produces schema-faithful `.md`, committed once, regenerated only on schema change. Hand-authored `.md` (A) rejected for the happy path (title/subject drift trap: `index.py:65` / `embed.py:479` read `title`; `zkm_eml/frontmatter.py:44` writes `subject`). *Out of scope:* run-time generation — forces a core→plugin run-time dependency.
- **Polyrepo split.** zkm-eml owns the `.eml` generator + expanded fixtures + convert-faithfulness roundtrip test (drift sentinel). Core owns the frozen committed `.md` corpus (opaque static input — **no `import zkm_eml` at run time**), centralized `conftest.py` fixtures, `scripts/seed_dev_store.py`, index/search/query/embed tests. Regen is a documented **manual cross-repo step**; staleness signaled by zkm-eml's roundtrip test going red. *Out of scope:* core importing the plugin at test time.
- **Forward-flag (alive, not built):** `.eml`-as-interchange keeps open a future "privacy-filtered *real* email → scrub → `.eml` → convert" producer sharing the same converter path.
- **Three pathological anchors** (hand-authored, `tests/fixtures/pathological/`, separate from faithful corpus): (1) oversized-entities → `_chunk_texts` prefix-cap ≤500; (2) HTML-entity NER garbage → indexer skips `valid:false`; (3) subject-only → subject absent from BM25 (flips loudly on future converter change). *Out of scope:* anchors for unobserved bugs.
- **Centralize the duplicated `_write_note`** into a `conftest.py` `make_note` factory + `store` fixture; migrate `test_search.py` / `test_index.py`. Relative-date temporal tests **stay** on the factory (not frozen onto fixed-date corpus).
- **Offline dense coverage:** keep existing `patch("httpx.post", ...)` stub + direct `_chunk_texts` calls — no live bge-m3 server, no stub HTTP server, in core tests.
- **Deferred (own item):** `zkm test <plugin>` conformance-validator command.

## Action items

- [ ] **zkm-eml:** deterministic synthetic `.eml` generator (byte-stable: fixed `Date:` headers, hardcoded Message-IDs, no `random`/now()); expand `plugins/zkm-eml/tests/fixtures/` with a reply chain. Contract: regenerating produces byte-identical `.eml`. (see docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md) <!-- id:9e0e -->
- [ ] **zkm-eml:** convert-faithfulness roundtrip test — run `convert()` on synthetic `.eml`, assert emitted frontmatter matches expectation (drift sentinel). Contract: a schema change to `frontmatter.py` turns this test red. (see docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md) <!-- id:fc87 -->
- [ ] **core:** commit frozen faithful `.md` corpus under `tests/fixtures/corpus/` + `CORPUS_MANIFEST.json` (`processor_version` + input sha256s, provenance). Contract: corpus indexes cleanly with `build_index`; no `import zkm_eml` in core tests. (see docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md) <!-- id:ba5e -->
- [ ] **core:** centralize `store` fixture + `make_note` factory in `tests/conftest.py`; delete duplicated `_write_note` in `test_search.py` (keep relative-date tests on the factory) and `test_index.py`. Contract: existing tests pass unchanged after the swap. (see docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md) <!-- id:590b -->
- [ ] **core:** `scripts/seed_dev_store.py` — copy committed corpus into `$ZKM_STORE`/`/tmp`, run `zkm index --no-embed`, print a sample `zkm query --no-dense` line. Optional `--with-pathological` flag. Contract: searchable BM25 store offline in <1s. (see docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md) <!-- id:0af9 -->
- [ ] **core:** three pathological anchors in `tests/fixtures/pathological/` + tests: (1) `_chunk_texts` prefix ≤500; (2) `valid:false` skipped by `_tokenize_doc`; (3) subject-only absent from BM25. README noting these deliberately violate converter output. (see docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md) <!-- id:f918 -->
- [ ] **core:** document the cross-repo regen procedure (eml generator → `tests/fixtures/corpus/` → recommit; staleness signaled by zkm-eml roundtrip test) in `docs/` or corpus README. (see docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md) <!-- id:c582 -->
- [ ] **Deferred / future planning:** `zkm test <plugin>` conformance-validator command — builds on roundtrip harness; conformance-validator not bare-runner; advisory-vs-gating TBD. (see docs/meeting-notes/2026-05-29-1112-synthetic-test-corpus.md) <!-- id:aa77 -->
