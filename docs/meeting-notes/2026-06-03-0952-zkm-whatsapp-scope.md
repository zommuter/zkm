# 2026-06-03 — zkm-whatsapp scoping (Session 15)

**Started:** 2026-06-03 09:52
**Session:** 7b1f962a-6de0-4e86-b6b3-0df8f5c73136
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 📬 Pim (PIM-engineering, new)
**Topic:** Scope the future `zkm-whatsapp` plugin — source-ingestion path, non-git source state, stable-ID synthesis, per-store config shape.

## Surfaced discoveries
- [2026-06-01 zkm] zkm ingest-only-plugin + core-fetch-orchestrator: fetch/decrypt tools play the mbsync role; plugin is a source-agnostic consumer.
- [2026-06-01 zkm] iCal/vCard UID dedup-on-UID → analogous stable-ID lever for chat (protocol-level ID).
- [2026-05-10 zkm] Name alone is NOT a UID — phone numbers can be reused; plan for manual-merge, not heuristic clustering.
- [2026-05-14 zkm] M2 per-store YAML config already retired env-var lists; `for_plugin()` returns whole section dict, so nested `whatsapp.accounts:[…]` works with no core change.

## Agenda
1. Source-ingestion path — which data source does v1 target?
2. Non-git source state — watermark strategy for a snapshot source; `zkm.state` N=2 check.
3. Stable-ID synthesis + granularity — `whatsapp:<chat_jid>:<key_id>` form, threading, filename, doc-type.
4. Per-store config shape + explicit out-of-scope list.

## Discussion

### 1. Source-ingestion path

Three candidate sources: **(A)** encrypted SQLite backup (`msgstore.db.crypt15`) — highest fidelity, needs decryption key; **(B)** official per-chat Export-chat `.txt` — lossy, no native message IDs or reply-to; **(C)** desktop/web LevelDB stores — volatile, undocumented.

🏗️ **Archie:** The fetch/ingest split (see contacts/calendar decision 2026-06-01) applies cleanly. Decryption is the mbsync-role fetch step (e.g. `wa-crypt-tools`); the plugin parses the *decrypted* `msgstore.db` via stdlib `sqlite3` (zero deps). The real decision is what standard tree the plugin consumes.

😈 **Riku:** `.txt` export bakes a lossy synthesized-ID contract (must hash `timestamp+sender+body` because there's no native ID) — hard to migrate if you later switch to SQLite. And crypt15-targeting risks scoping a plugin that can't run. Mitigation: "plugin parses SQLite, not crypt" keeps the plugin runnable once the fetch step works.

✂️ **Petra / 📬 Pim:** `.txt` is a different plugin (or deferred v2 mode) — don't blend two parsers.

**User:** v1 = SQLite msgstore.db. Two riders: (1) **pilot the decryption path first** — verify wa-crypt-tools actually decrypts this user's crypt15 before building; spin a separate project if no clean tool. (2) **WA Web "live" updates must remain mergeable** later — `message_id` must be the protocol-level `key_id`, not a per-store rowid or content hash.

### 2. Non-git source state

🏗️ **Archie:** zkm-eml's watermark (`state.py:1-51`) is a git-SHA of the source mail repo — does not transfer (WhatsApp has no git; source is a periodically-replaced SQLite snapshot).

📬 **Pim:** SQLite gives a cleaner lever: `max(timestamp)` already imported → next run `WHERE timestamp > :watermark`.

😈 **Riku:** `_id` (rowid) is NOT stable across backup-restore — WhatsApp rebuilds `msgstore.db` on restore. Watermark on **timestamp** only; correctness from idempotent **dedup-on-`key_id`** (mirrors `eml/convert.py:99`). Watermark is a speed optimisation, not a truth source.

✂️ **Petra:** N=2 check for a generic `zkm.state` core module: eml (git-SHA payload) + whatsapp (timestamp payload) share only "atomic JSON blob at `.zkm-state/zkm-<plugin>.json`" — payloads differ. Below D5 abstraction bar (16 shared lines vs cost of new module + allowlist + P2 symlink).

**Decision:** **Convention, not module.** Document in `plugin-spec.md`: "incremental state at `.zkm-state/zkm-<name>.json` via `zkm.atomic.write_atomic`, gitignored." whatsapp ships its own `state.py` mirroring eml, keyed by `source_db` path (multi-account independent). Promote to a shared `zkm.state` module only when a third plugin wants the *same* payload shape.

### 3. Stable-ID synthesis + granularity

**ID mapping** (settled): `message_id = whatsapp:<chat_jid>:<key_id>` (spec line 31 documented form; protocol-level `key_id` is identical in msgstore.db and WA Web → rider 2 satisfied). `thread_id = sha256(chat_jid)[:16]` (one chat = one thread, threading.py convention). `in_reply_to = whatsapp:<chat_jid>:<quoted_key_id>` from `message_quoted` table (omit if none). participants = JIDs role-tagged; `direction` NOT written (derived from `from_me + owner_jid` at query time, per spec lines 57–64). SQLite tables: `message(key_id, chat_row_id, timestamp, from_me, sender_jid_row_id, text_data)`, `chat→jid`, `message_quoted`, `message_media`, `group_participant_user`.

**Granularity:**

| Option | Files | Decision |
|---|---|---|
| Per-message (spec-literal) | ~100k+ tiny files | Heavy git tree, low-signal embed/BM25, large key_id-set scan → **rejected** |
| Per-chat (whole) | 1 / chat | Unbounded-growth churn file → **rejected** |
| **Per-chat-day transcript** | ~100× fewer | **CHOSEN** — coherent embed/retrieval unit; N=2+ (Signal/Threema on roadmap) justifies new doc-type |

📬 **Pim:** Day-boundary is the only *deterministic, zero-heuristic* segmentation — needs only a timezone (store locale, de_CH).

😈 **Riku:** **Deterministic emission is a hard contract requirement** — sort by `(timestamp, key_id)`, stable formatting, fixed sentinel strings → re-emitting an open (today's) day file is a git no-op.

**Forward-flag (deferred, design-note only):** smarter segmentation — burst/temporal-density (gap-based; threshold `N` needs measure-first) OR per-thread (needs implicit reply-detection = heuristic, can mis-thread). Must be an **additive re-segmentation layer** that never rewrites the chat-level `thread_id`. No v1 code. Trigger: v1 live + a concrete retrieval pain that day-boundaries cause.

### 4. Config + scope boundary

Config is M2-solved: `whatsapp:` section in `zkm-config.yaml`, keys `source_db` + `owner_jid`, `creates_dirs: [chat/whatsapp/]`. No secrets in plugin (decryption key lives in the fetch tool). Multi-account deferred — `whatsapp.accounts: [...]` nests later via `for_plugin` with zero core change.

Contact names: write JID/number as canonical `address`; human name best-effort from group `subject` or absent for 1:1. **No contact-resolution** (zkm-vcard + Phase-4 manual-merge territory).

**User: deleted-tombstones IN v1.** In `msgstore.db` a delete-for-everyone is a *revoke* — the row remains with a revoked status (not deleted). Emit `[HH:MM] sender: «deleted»` (fixed sentinel, not WhatsApp's locale string), original `key_id` kept in the `messages:` manifest (deletion recorded, dedup stable, future restore mergeable, re-emission a git no-op).

**Explicit out-of-scope for v1:**
- crypt15 decryption (fetch-role; pilot gate)
- `.txt` export parsing (deferred separate mode/plugin)
- WA Web live sync (forward-flag; mergeability designed-in via `key_id`, no code)
- burst/thread re-segmentation (forward-flag)
- multi-account (nestable later)
- reactions / read-receipts as frontmatter (inline-only if trivial; read-receipts out entirely)
- voice transcription / image OCR (media → CAS only; enrichment is amender territory)
- contact-name resolution / gazetteer (JID is the address)

## Decisions
- **v1 source = decrypted `msgstore.db` (SQLite), parsed via stdlib `sqlite3` (zero deps).** Decryption is an out-of-scope fetch-role step (future `zkm fetch`, id:473c). `.txt` export and WA Web/desktop stores are deferred.
- **Decryption pilot is a hard gate** before plugin build — verify wa-crypt-tools (or equiv) decrypts this user's crypt15; spin a separate project if no clean tool exists.
- **`message_id = whatsapp:<chat_jid>:<key_id>`** — protocol-level `key_id`, mergeable with WA Web (iCal-UID-style). NOT a rowid or content hash.
- **`thread_id = sha256(chat_jid)[:16]`** — one chat = one thread. `in_reply_to` from `message_quoted`. Participants = JIDs, role-tagged. No `direction` in frontmatter.
- **Granularity = per-chat-day transcript doc-type (NEW)** — reused by future Signal/Threema plugins. File-level frontmatter: `source`, `date`=day, `thread_id`, chat metadata, `messages:` key_id manifest. Body = chronological `[HH:MM] sender:` lines + inline key_id anchor. Reply-to + reactions inline (never frontmatter). Day boundary uses store locale TZ (de_CH). Deterministic emission (sort by timestamp,key_id; fixed sentinels) → re-emit of unchanged day is a git no-op.
- **Source state = convention, not module.** Own `state.py` → `.zkm-state/zkm-whatsapp.json` (timestamp watermark keyed by `source_db`). Correctness from dedup-on-`key_id`; watermark is speed-only. Convention documented in `plugin-spec.md`. Promote to `zkm.state` module only at 3rd same-payload consumer.
- **Deleted messages = tombstones IN v1.** Revoke rows → `[HH:MM] sender: «deleted»`, key_id in manifest. Fixed sentinel (not locale string).
- **Config (M2-solved):** `whatsapp:` section, `source_db` + `owner_jid`, `creates_dirs:[chat/whatsapp/]`, no secrets.
- **Media → inbox+CAS** via `zkm.cas.write_object` + `.origin.json` sidecar.

## Action items
- [ ] **W-pilot.** Pilot crypt15 decryption: verify wa-crypt-tools (or equiv) decrypts this user's `msgstore.db.crypt15` → plaintext SQLite; spin a separate project if no clean tool. HARD GATE before plugin build. <!-- id:9f05 -->
- [x] **W1.** Define per-chat-day transcript doc-type in `docs/messaging-spec.md`: file-level frontmatter schema + `messages:` key_id manifest; inline-line body shape; deterministic-emission contract. Contract test: re-emit of unchanged day = byte-identical file. <!-- id:3970 -->
- [ ] **W2.** `plugins/zkm-whatsapp/` repo: `plugin.yaml` (name: whatsapp, creates_dirs:[chat/whatsapp/], config source_db+owner_jid) + `convert()` (decrypted msgstore.db → transcript .md via stdlib sqlite3). Contract: idempotent (dedup-on-key_id), atomic writes, source/processor/processor_version set. <!-- id:b51a -->
- [ ] **W3.** Stable-ID synthesis: `message_id=whatsapp:<chat_jid>:<key_id>`, `thread_id=sha256(chat_jid)[:16]`, `in_reply_to` from `message_quoted`, participants from JIDs, no direction. Contract test: same key_id → same message_id across two ingests. <!-- id:227d -->
- [ ] **W4.** Source state: `state.py` → `.zkm-state/zkm-whatsapp.json` timestamp watermark keyed by source_db; document `.zkm-state/zkm-<name>.json` convention in `docs/plugin-spec.md`. Contract: rowid renumber across restore does not skip/dup messages. <!-- id:035a -->
- [ ] **W5.** Deleted-tombstone handling: revoke rows → `[HH:MM] sender: «deleted»` (fixed sentinel), key_id preserved in `messages:` manifest. <!-- id:4c8a -->
- [ ] **W6.** Media → inbox+CAS (`write_object` + `.origin.json`) for image/video/audio/document attachments. <!-- id:d60c -->
- [ ] **W7 (deferred design note).** Smarter segmentation (burst/temporal-density or per-thread) as additive re-segmentation that never rewrites chat-level `thread_id`. Trigger: v1 live + concrete retrieval pain from day-boundaries. <!-- id:367f -->
- [x] Add `W` prefix row (zkm-whatsapp) to TODO prefix-convention table in `CLAUDE.md`. <!-- id:890f --> **Done — CLAUDE.md line 140.**
