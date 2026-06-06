# 2026-06-06 — zkm-claude-ai / zkm-claude-code scoping

**Started:** 2026-06-06 16:17
**Session:** ff6fd8ae-56ac-421a-ad66-9769756ad850
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🗺️ Flora (information-flow — content-type vs format, routing topology)
**Topic:** Scope the two AI-session import plugins: which to build first, document grain, content-block handling, shared helper extraction.

## Surfaced discoveries
- [2026-05-10 .claude] Claude Code Stop hooks receive `transcript_path` = full JSONL session incl. all tool-call records.
- [2026-05-10 claude-diary] claude.ai `docs[]` are a disk-content round-trip backup, NOT a unique corpus — interesting corpus is `conversations.json`.
- [2026-06-03 zkm] Hybrid plugin discovery (entry-points + filesystem scan, dev-symlink wins); entry-point install path = deps-clean.

## Grounding facts
- **Both corpora exist locally.** claude.ai export: `/home/tobias/src/claude-diary/claude.ai-export/conversations.json` (48.8 MB, 187 conversations, some with empty `chat_messages`). Claude Code: `~/.claude/projects/<sanitized-cwd>/*.jsonl` — 627 files, up to 2.5 MB each.
- **claude.ai schema:** array of conversations `{uuid, name, summary, created_at, updated_at, chat_messages[]}`. Message `{uuid, parent_message_uuid, sender (human/assistant), text, content[], attachments[], files[], created_at}`. Content blocks: text/thinking/tool_use/tool_result/token_budget. No per-turn token usage. Block histogram: text 2583, thinking 732, tool_use 1908, tool_result 1899, token_budget 463.
- **Claude Code schema:** newline-delimited event stream, `type ∈ {user, assistant, attachment, file-history-snapshot, mode, permission-mode, last-prompt}`. Threaded by `uuid`/`parentUuid`. Per-turn `usage`, `model`, `cwd`, `gitBranch`. No conversation-level name/summary. Sidecars: `subagents/agent-*.jsonl` + `tool-results/*.txt` overflow spill.
- Both reduce to the same message tuple after filtering: `(sender, parent-uuid, timestamp, content-blocks)`. claude-code adds event-record filtering + sidecar reassembly upstream.

## Agenda
1. Start order — claude-ai first or claude-code first?
2. Document granularity — per-conversation, per-message, or per-day?
3. Non-text content blocks — include, strip, or stub?
4. Shared `zkm.session` helper — extract now or at N=2?

## Discussion

### Agenda 1 — Start order
🏗️ Archie: claude-ai is the clean schema (conversation→thread, name+summary built in); claude-code is a superset (event-filter + sidecar reassembly upstream of the shared tuple). Define contract against the simple form, widen for event-stream — additive, not a refactor.

🗺️ Flora: claude.ai = knowledge (discussions, Q&A, reasoning); claude-code = mechanics (tool calls, mostly self-referential zkm logs). Higher knowledge-per-MB. 187 curated conversations > 627 agentic session files as a starting corpus.

✂️ Petra: claude.ai fixture ready today (48.8 MB in claude-diary, no export step needed). claude-code parsing surface bigger (event-record filtering, sidecar spill). Least scope to first value = claude-ai.

😈 Riku: three counters — (1) claude.ai export is stale/manual; claude-code is the live corpus; (2) contract-baking refactor risk; (3) empty `chat_messages` edge case. Yields on (2) since both reduce to same tuple per exploration; wants staleness/refresh story recorded: dedup on uuid, re-export = the "fetch" role, watermark is speed-only.

**Decision D1:** claude-ai first.

### Agenda 2 — Document granularity
🏗️ Archie: a Claude conversation is a naturally bounded unit — it has its own `name`, `summary`, clear start/end. Unlike email (no intrinsic thread boundary) or WhatsApp (unbounded running chat). Grain = one .md per conversation (transcript-as-document, WhatsApp W1 precedent). Conversation `uuid` = stable ID; messages = sections ordered by walking `parent_message_uuid`.

✂️ Petra: per-message = thousands of tiny fragments nobody retrieves individually; retrievable unit is the conversation. 187 files right-sized.

🗺️ Flora: segmentation axis differs from WhatsApp — WhatsApp needs day-cuts because chat is unbounded; a conversation is already the bounded unit. No day-segmentation. Store under `sessions/claude-ai/` (parallel to `mail/`, `chat/whatsapp/`). Thread_id = conversation uuid, singleton thread.

😈 Riku: big conversations → embed.py already chunks, not a blocker. Re-export: rewrite-in-full when `updated_at` newer. Accepts if empty-`chat_messages` conversations are skipped and `summary` is provenance-marked (Anthropic-generated, not zkm-derived).

**Decision D2:** per-conversation transcript.

### Agenda 3 — Non-text content blocks & privacy
🗺️ Flora: block histogram shows tool blocks are ~half the volume and a different content-type. `tool_result` from Read = a copy of a file already in the store. From MCP Gmail/Calendar/Drive = private data pulled sideways, divorced from its real provenance. Do not include payloads verbatim.

🏗️ Archie: render structure, not payload. Default — `text` verbatim; `thinking` included+marked (own reasoning, lower leak risk); `tool_use` → one-line stub `[→ <name>: <short input>]`; `tool_result` → `[← result: <N bytes>]` (no payload); `token_budget` skip.

✂️ Petra: knowledge is in prose and reasoning, not tool mechanics. Stubbing also kills the size problem (2.5 MB sessions are mostly tool output). One default, no verbosity matrix.

😈 Riku: accepts stub default if recorded as a **deliberate privacy posture** — stub never fabricates a summary of result content (name+size only, nothing else). `--no-thinking` deferred behind a min-evidence gate: if thinking proves noisy in practice, re-open.

🗺️ Flora: `attachments[].extracted_content` = content the user pasted into the conversation → genuine content, include it. `files[]` = `file_uuid` pointers, binaries not in export → emit pointer note only.

**Decision D3:** narrative + tool stubs. Deliberate privacy posture.

### Agenda 4 — Shared zkm.session helper
✂️ Petra: N=2 requires both consumers real; claude-code is roadmapped but not built. Extracting `zkm.session` now = shaping a "shared" helper around one real caller + one guess at the harder schema. Build claude-ai self-contained; duplicate the small rendering when claude-code lands (2026-05-14: inline duplication beats premature extraction at N=1.5).

😈 Riku: pay-twice risk if claude-ai bakes non-reusable rendering. Petra: cheaper than the wrong abstraction; the conversion is small.

🏗️ Archie: the *contract* is shareable now even if the *code* isn't — `message_id` = `claude-ai:<conv_uuid>:<msg_uuid>`, `thread_id` = conversation uuid, 2-participant model (human=owner, assistant=claude), block-stub rules. Document in `docs/messaging-spec.md` + README. claude-code mirrors the doc.

🗺️ Flora: participants trivial (two roles, no gazetteer, no identity-merge). Consistent with the zkm no-auto-merge rule.

**Decision D4:** claude-ai standalone; zkm.session extraction deferred to the claude-code build session as the explicit N=2 trigger.

## Decisions
- **D1 — Start order:** Build `zkm-claude-ai` first (claude.ai `conversations.json`); `zkm-claude-code` second, extending with event-record filtering + sidecar reassembly. Other providers (ChatGPT/Gemini) out of scope until N=2 proves the pattern. Staleness handled by uuid-dedup + re-export; watermark speed-only.
- **D2 — Document grain:** One `.md` per conversation under `sessions/claude-ai/`. Conversation `uuid` = stable ID and `thread_id` (singleton thread, messaging-spec). `name` → title/filename. `summary` → frontmatter (provenance-marked: Anthropic-generated). Messages = body sections in `parent_message_uuid` order. Rewrite-in-full when `updated_at` newer. Skip empty-`chat_messages` conversations. Out of scope: per-message files, day-segmentation.
- **D3 — Content blocks:** `text` verbatim; `thinking` included+marked; `tool_use` → stub `[→ <name>: <short input>]`; `tool_result` → `[← result: <N bytes>]` (NO payload, name+size only, never fabricated content); `token_budget` skipped; `attachments[].extracted_content` included; `files[]` → pointer notes. Deliberate privacy posture: no MCP or file payloads enter the store. Out of scope: full-fidelity knob (forward-flag), `--no-thinking` (min-evidence gate).
- **D4 — Shared helper:** No `zkm.session` in v1. Build claude-ai self-contained; document the conceptual contract (message_id format, thread_id, participant model, block-stub rules) in `docs/messaging-spec.md` + plugin README. Extract shared code only at the claude-code build session (real N=2). Out of scope: pre-committing module name/shape.
- **Cross-cutting:** `convert()` MUST NOT call any AI. No identity-merge of participants to NER/mail (Phase-4 manual-merge only). Assign single-letter TODO prefix once `zkm-claude-ai` accumulates ≥3 unchecked items.

## Action items
- [ ] Build `zkm-claude-ai` plugin (own repo `plugins/zkm-claude-ai/`): `plugin.yaml` (`name: claude-ai`, `creates_dirs: [sessions/claude-ai]`, config `source_dir`) + `convert(store_path, config, *, progress)`. Per-conversation transcript .md; dedup on conversation uuid via frontmatter scan; `.zkm-state/zkm-claude-ai.json` watermark on `updated_at`; block-stub rendering per D3; skip empty conversations; reuse `zkm.atomic`/`zkm.encoding`/`zkm.canonical`; emit messaging-spec frontmatter. Verifiable contract: one .md per non-empty conversation, payload-free tool stubs, uuid-stable filenames. <!-- id:1c5b -->
- [ ] Document the session-import conceptual contract in `docs/messaging-spec.md` (+ plugin README): `message_id` = `claude-ai:<conv_uuid>:<msg_uuid>`, `thread_id` = conv uuid, 2-participant model, block-stub rendering rules. <!-- id:5590 -->
- [ ] Forward-flag: `zkm-claude-code` build session is the N=2 trigger for `zkm.session` extraction. Open that session comparing the two real renderers; claude-code extends with event-record filtering (`type ∈ user/assistant/...`) + sidecar reassembly. Module name not pre-committed. <!-- id:4d93 -->
- [ ] Add test fixture + conformance for `zkm-claude-ai`: small committed `conversations.json` slice (placeholder/redacted content per published-repos-must-be-generic rule) + `conformance.config.source_dir`; roundtrip test that convert() output passes `validate_frontmatter()`. <!-- id:dd21 -->
