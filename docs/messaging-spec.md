# zkm messaging plugin specification

Conventions for any plugin that converts a *conversation source* — email, chat, SMS, or similar — into the store. Defines frontmatter fields and store layout so all messaging plugins share a consistent shape that search, the future WebUI, and other plugins can rely on.

Reference implementation: [`zkm-eml`](https://github.com/Zommuter/zkm-eml) (EML/Maildir import).

## Frontmatter fields

In addition to the [base fields](plugin-spec.md#frontmatter) (`source`, `date`, `tags`, `sha256`, `processor`, `processor_version`), messaging plugins MUST write:

```yaml
message_id: "<abc123@example.com>"       # RFC 5322 Message-ID or equivalent stable ID
thread_id: "a1b2c3d4"                    # SHA-256 prefix of the root message_id in the thread
in_reply_to: "<parent@example.com>"      # parent message_id, or omit if root
references:                              # full ancestor chain, oldest first
  - "<grandparent@example.com>"
  - "<parent@example.com>"
thread: "mail/threads/a1b2c3d4.md"       # relative path to the thread index file
participants:
  - address: alice@example.com
    name: Alice Example
    role: from
  - address: bob@example.com
    role: to
  - address: carol@example.com
    role: cc
```

### Field notes

- `message_id` — for email, use the `Message-ID` header verbatim (with angle brackets). For chat platforms, derive a stable ID from the platform's own message ID (e.g. `whatsapp:<chat_id>:<msg_id>`).
- `thread_id` — the first 16 hex chars of `sha256(root_message_id.encode())`. Stable across re-ingestion. For email, the root is the oldest `Message-ID` in the `References` chain, falling back to the message's own `Message-ID` if `References` is absent.
- `in_reply_to` — omit (don't write `null`) for root/thread-starter messages.
- `references` — use the `References` header for email; build it from the platform's reply graph for chat.
- `thread` — path relative to the store root. Always `<source_dir>/threads/<thread_id>.md`.
- `participants` — role-tagged list. `address` is required (lowercase); `name` is optional. `role` is required.
- `direction` — **not emitted**. Direction is derivable: outgoing iff there exists a `participants` entry with `role: from` whose address is in the store owner's identity list (kept in `.env` / future global config, not baked into individual files).

### Participant role vocabulary

| Role | Description | Email | Group chat | Calendar |
|------|-------------|-------|-----------|----------|
| `from` | Originator | `From:` header | sender | (n/a) |
| `reply-to` | Explicit reply target | `Reply-To:` header | (n/a) | (n/a) |
| `to` | Direct recipient | `To:` header | DM target | (n/a) |
| `cc` | Informational copy | `Cc:` header | (n/a) | (n/a) |
| `bcc` | Blind copy (outgoing only) | `Bcc:` header | (n/a) | (n/a) |
| `member` | Group member who could see message | mailing list | group roster | (n/a) |
| `mentioned` | @-tagged in message body | (n/a) | @-mention | (n/a) |
| `organizer` | Event/meeting organizer | (n/a) | (n/a) | `ORGANIZER` |
| `attendee` | Confirmed attendee | (n/a) | (n/a) | `PARTSTAT=ACCEPTED` |
| `optional` | Optional attendee | (n/a) | (n/a) | `ROLE=OPT-PARTICIPANT` |
| `invitee` | Invited, not yet confirmed | (n/a) | (n/a) | `PARTSTAT=NEEDS-ACTION` |

Plugins MAY add custom roles not in this table; custom roles SHOULD use an `x-` prefix to flag non-canonical use. The same person MAY appear multiple times with different roles (e.g. `from` + `reply-to`).

### Owner identity and direction derivation

The store owner's addresses are kept outside the per-message md to avoid rebaking every file if the owner list changes. They live in `$ZKM_STORE/.env` under a key defined by each plugin (`EML_OWNER_ADDRESSES` for `zkm-eml`). Future global config will unify these. Search and UI code loads the identity list into memory and applies it at query time:

```python
owner = {a.strip().lower() for a in config.get("EML_OWNER_ADDRESSES", "").split(",") if a}
is_outgoing = any(p["address"] in owner for p in participants if p["role"] == "from")
```

## Store layout

Each messaging plugin chooses a `source_dir` (e.g. `mail/`, `chat/whatsapp/`) and MUST lay out its files as follows:

```
<source_dir>/
├── messages/         # one .md per message
│   ├── 2026-04-13_subject-slug.md
│   └── ...
└── threads/          # one .md per thread, regenerated on each convert run
    ├── a1b2c3d4.md
    └── ...
```

The `messages/` and `threads/` split is mandatory — it allows the thread index files to be regenerated without touching the per-message git history.

### Thread index file format

`<source_dir>/threads/<thread_id>.md`:

```markdown
---
source: <plugin-name>
thread_id: a1b2c3d4
participants:                 # flat-dedup "Name <addr>" strings across all messages
  - Alice Example <alice@example.com>
  - Bob <bob@example.com>
first_date: 2026-04-10T09:15:00+02:00
last_date: 2026-04-13T14:30:00+02:00
message_count: 7
---

# Thread: Subject of the first message

| Date | From | Subject |
|------|------|---------|
| 2026-04-10 | Alice Example | Re: Initial question |
| 2026-04-11 | Bob | ... |
```

Thread index files are always fully regenerated — they are never committed incrementally. A plugin run that adds messages to a thread MUST rewrite the entire thread index file for that thread.

## Originals

Raw originals (`.eml`, chat export JSON, etc.) SHOULD be stored at `originals/<source_dir>/<stable_slug>.<ext>` and referenced via the base `original` frontmatter field. This enables `--reprocess` to re-derive the markdown from the original source when the plugin algorithm improves.

## Deduplication

Use `message_id` as the primary dedup key (more stable than `sha256` for sources that allow minor re-encoding). Keep `sha256` in frontmatter to satisfy the base plugin contract; compute it over the raw original bytes or a stable canonical form.

## Per-conversation transcript doc-type

AI session plugins with naturally bounded conversations (claude.ai, ChatGPT, etc.) produce
**per-conversation transcripts**. A conversation has an intrinsic start/end and a stable UUID.

> Reference design: [zkm-claude-ai / zkm-claude-code scoping meeting 2026-06-06](meeting-notes/2026-06-06-1617-zkm-claude-ai-claude-code-scoping.md).

### File layout

```
sessions/<platform>/
├── 2026-01-02_simple_text_conversation_00000002.md
└── ...
```

Filename: `<YYYY-MM-DD>_<slug>_<uuid8>.md`. Slugify the conversation name; UUID prefix is 8 chars.

### Frontmatter schema

```yaml
source: claude-ai
date: 2026-01-02T09:00:00+00:00       # created_at with timezone
title: "Simple text conversation"
thread_id: 00000000-0000-0000-0000-000000000002   # conversation UUID
participants:
  - address: human
    role: human
  - address: assistant
    role: assistant
message_count: 2
updated_at: 2026-01-02T09:05:00+00:00
summary: "Anthropic-generated summary"  # omit if empty
tags: []
sha256: <sha256 of conversation JSON>
processor: claude-ai
processor_version: "0.1.0"
```

**Notes:**
- `thread_id` is the platform-native conversation UUID (stable, not derived).
- `message_id` is NOT in the file-level frontmatter. Conceptual per-message format:
  `claude-ai:<conv_uuid>:<msg_uuid>` — for cross-reference in body text and future tooling.
- `participants` uses fixed roles `human` / `assistant`; `address` is the lowercase role string.
- `sha256` is computed over the stable JSON representation of the conversation.
- `summary` is provenance-marked as Anthropic-generated; never a zkm-derived field.

### Content block rendering (D3 — deliberate privacy posture)

| Block type | Rendered as |
|---|---|
| `text` | Verbatim body text |
| `thinking` | `> [thinking]` blockquote |
| `tool_use` | `[→ tool_name: {short input ≤80 chars}]` |
| `tool_result` | `[← result (name): N bytes]` — **no payload** |
| `token_budget` | Skipped |
| `attachments[].extracted_content` | Verbatim (user-pasted content, owns its own provenance) |
| `files[]` | `[attachment: filename]` pointer note |

MCP tool results and file payloads MUST NOT enter the store. Stub format is `name+size only`.

### Deduplication

Use the conversation `uuid` as the primary dedup key. Re-import when `updated_at` is newer.
State file: `<store>/.zkm-state/zkm-claude-ai.json` — maps source path → `{by_uuid: {uuid: updated_at}}`.
Correctness comes from UUID-dedup via frontmatter scan; watermark is a speed optimisation.

---

## Per-chat-day transcript doc-type

Chat plugins operating on a *conversation snapshot* (e.g. a SQLite backup) produce
**per-chat-day transcripts** rather than per-message files.
This is a distinct doc-type from the per-message shape above.

> Reference design: [zkm-whatsapp scope meeting 2026-06-03](meeting-notes/2026-06-03-0952-zkm-whatsapp-scope.md).
> Future Signal/Threema plugins SHOULD adopt this doc-type.

### Rationale

Per-message files produce tens of thousands of tiny git entries from a single chat archive.
A per-chat-day transcript is the smallest granularity at which:
- BM25 and dense search return coherent, context-rich result snippets.
- Git history is meaningful (one commit per sync, not one per message).
- Re-emission of an unchanged day is a byte-identical git no-op (deterministic contract).

### File layout

```
chat/<platform>/
├── <thread_id>/          # one dir per chat; thread_id = sha256(chat_jid.encode())[:16]
│   ├── 2026-04-13.md     # one file per day; date in store locale TZ
│   └── 2026-04-14.md
└── ...
```

Thread-index files (per-message spec) are NOT used for this doc-type. Thread identity is
encoded in the directory name and `thread_id` frontmatter field.

### Frontmatter schema

```yaml
---
source: whatsapp                              # plugin name
date: 2026-04-13                             # day (YYYY-MM-DD), store locale TZ
thread_id: "a1b2c3d4e5f60718"               # sha256(chat_jid.encode())[:16]
chat_jid: "123456789@g.us"                  # platform JID (group) or phone@s.whatsapp.net
chat_name: "Family Group"                    # optional; group subject; omit for 1:1
participants: [{address: "123456789@g.us", name: "Alice", role: member}, {address: "987654321@s.whatsapp.net", role: member}]
processor: zkm-whatsapp
processor_version: "0.1.0"
---
```

**Notes:**
- `sha256` is omitted — there is no single "original" byte source for a day file.
- `message_id` and `in_reply_to` are NOT in the file-level frontmatter (they appear in the body, see below).
- `participants` uses the same `address` / `name` / `role` structure as the per-message spec; use `member` for chat participants (or `mentioned` for @-tags). The owner's JID MUST appear in `participants`. Flow-compacted (block-style only for very large groups).
- `direction` is NOT written — derivable from `owner_jid` config at query time, same principle as per-message spec.
- The per-message manifest (`key_id`, `timestamp`, `sender_jid`, `status`, and optional `text`/`quoted_key_id`/`media` fields) lives in the **footer**, not the frontmatter — see [Footer manifest](#footer-manifest) below.

### Body format

One line per message, sorted by `(timestamp, key_id)`. Lines are separated by a single newline (no blank lines between messages).

```
[HH:MM] Alice: message text here <!-- key_id: abc123DEF456 -->
[HH:MM] Alice: «deleted» <!-- key_id: ghi789JKL012 -->
[HH:MM] Bob: ↩ (re: abc123DEF456) thanks! <!-- key_id: stuvWXYZ -->
[HH:MM] Alice: [media: image/jpeg → chat/whatsapp/a1b2c3d4/originals/img_key.jpg] <!-- key_id: AB12CD34 -->
[HH:MM] Bob: great pic [reaction: 👍 from Alice] <!-- key_id: EF56GH78 -->
```

**Rules:**
- `[HH:MM]` — 24-hour clock in store locale TZ (default: Europe/Zurich for de_CH).
- `DisplayName` — sender's `name` from `participants` if known, otherwise the bare JID/phone number.
- **Deleted tombstone:** `«deleted»` (U+00AB + U+00BB, fixed sentinel — NOT the platform's locale string). The `key_id` MUST still appear in the footer manifest with `status: revoked`.
- **Reply indicator:** `↩ (re: <quoted_key_id>)` prefix when the platform provides a quoted-message reference. `quoted_key_id` may point to a message in a different day file.
- **Media:** `[media: <mime-type> → <store-relative-path>]` for attachments stored via `zkm.cas.write_object`; a `.origin.json` sidecar records provenance.
  The body `[media: …]` line plus the trailing `<!-- key_id: … -->` anchor is the
  **guaranteed audio-discovery surface**: downstream consumers (e.g. zkm-stt) locate
  transcribable voice notes by scanning body lines for an `audio/*` mime and resolve
  the message via the `key_id` anchor — producers MUST keep both on the same line.
  Producers SHOULD set a **precise `audio/*` mime for voice notes** (e.g. `audio/ogg`
  for WhatsApp/Signal opus notes, `audio/mp4` for AAC), never a generic
  `application/octet-stream`, so mime-based discovery does not miss them.
- **Reactions:** appended inline as `[reaction: <emoji> from <DisplayName>]`. Never in frontmatter.
- Inline key_id anchors (`<!-- key_id: ... -->`) MUST be the last token on the line.

### Deterministic emission contract

Re-ingesting a source with no new messages for a given day MUST produce a byte-identical file.

1. Sort all messages by `(timestamp, key_id)` — `key_id` is the tiebreaker for same-second messages.
2. Use fixed sentinel strings (never platform locale strings).
3. Format times with `strftime("%H:%M")` in the store locale TZ.
4. Write the footer manifest entries in the same `(timestamp, key_id)` order as the body lines.
5. Omit fields whose value would change across runs for unchanged source data.

**Contract test:** emit a day file from a fixed source snapshot; re-emit from the same snapshot; assert the two files are byte-identical.

Use `zkm.testing.assert_reemit_identical(emit)` as the canonical test helper for this
contract (ROADMAP id:ab8b). `emit` is a zero-arg callable that writes files and returns
an iterable of the written `Path`s. The helper calls `emit()` twice and asserts every
returned path is byte-identical across both runs, raising `AssertionError` naming the
offending path on any difference. Every messaging plugin (whatsapp, telegram, signal,
threema) MUST include a test that exercises this helper against its real emit path.

### Footer manifest

The per-message manifest is written as an end-of-file HTML comment block after the
transcript body, replacing the old frontmatter `messages:` block. The block is
machine-parseable and invisible when the `.md` is rendered:

```
<!-- zkm:manifest
messages:
  - key_id: "abc123DEF456"
    timestamp: "2026-04-13T14:30:00+02:00"
    sender_jid: "123456789@s.whatsapp.net"
    status: sent
    text: "message text here"
  - key_id: "ghi789JKL012"
    timestamp: "2026-04-13T14:31:00+02:00"
    sender_jid: "987654321@s.whatsapp.net"
    status: revoked
  - key_id: "stuvWXYZ"
    timestamp: "2026-04-13T14:32:00+02:00"
    sender_jid: "987654321@s.whatsapp.net"
    status: sent
    quoted_key_id: "abc123DEF456"
    text: "thanks!"
  - key_id: "AB12CD34"
    timestamp: "2026-04-13T14:33:00+02:00"
    sender_jid: "123456789@s.whatsapp.net"
    status: sent
    media: {mime: image/jpeg, sha256: "cafebabe..."}
-->
```

**Fields per manifest entry:**

| Field | Required | Description |
|---|---|---|
| `key_id` | yes | Platform-stable message ID; dedup key |
| `timestamp` | yes | ISO 8601 with timezone |
| `sender_jid` | yes | Sender's platform JID |
| `status` | yes | `sent` \| `delivered` \| `read` \| `revoked` |
| `text` | optional | Message text — written when the source is ephemeral and the manifest is the rewrite truth-source (w6f rationale); omit for sources with a durable original |
| `quoted_key_id` | optional | `key_id` of the quoted/replied-to message; mirrors the `↩ (re: …)` body indicator |
| `media` | optional | `{mime: <media-type>, sha256: <cas-sha256>}`; mirrors the `[media: …]` body indicator for CAS-stored attachments |

**Format rules:** entries in the same `(timestamp, key_id)` order as the body lines
(deterministic). The `<!-- zkm:manifest` block MUST be the final content in the file,
placed after the last transcript line.

**Reading:** `_load_existing_manifest` reads the footer block; pre-change day-files
that still carry `messages:` in frontmatter are healed on next rewrite (frontmatter
fallback → footer on save). Reconstitution (`_reconstitute`) reads the footer only.

### Deduplication

Use the footer manifest as the truth source:

1. Load existing `key_id` values from the footer manifest for this day (if the file exists).
2. Fetch rows from the source with `timestamp` in this day's window.
3. Skip rows whose `key_id` is already in the manifest.
4. Append new rows in `(timestamp, key_id)` order and rewrite the full manifest.

Rowid renumbering across backup-restore does NOT affect correctness — only `key_id` (the
platform-level stable ID) is used for dedup.

### Plugin conformance — footer manifest

> **Conformance contract (id:03ae):** The per-chat-day footer-manifest layout described
> above (`<!-- zkm:manifest … -->`) IS the contract that `zkm-signal`, `zkm-threema`,
> and every future chat-day plugin MUST inherit. A new plugin stub MUST NOT ship the old
> frontmatter `messages:` shape. Signal and Threema stubs should adopt this footer shape
> from day one rather than migrating later.

See also: `docs/object-storage.md` §Sidecar vs. in-document storage for the
heuristic that explains why the manifest lives in the document footer rather than a
sidecar.

## Future plugins that should conform

| Plugin | Source | Doc-type | Notes |
|--------|--------|----------|-------|
| `zkm-eml` | Maildir / `.eml` files | per-message | Reference implementation |
| `zkm-whatsapp` | WA local backup (SQLite) | per-chat-day | Decryption is a fetch-role step |
| `zkm-threema` | Threema Safe export | per-chat-day | JSON export |
| `zkm-signal` | Signal SQLite DB | per-chat-day | Requires phone access |
| `zkm-telegram` | Telegram JSON export | per-chat-day | Built-in export feature |
| `zkm-claude-ai` | claude.ai `conversations.json` | per-conversation | Singleton thread; no `message_id` at file level |
| `zkm-claude-code` | Claude Code `~/.claude/projects/*.jsonl` | per-conversation | Extends claude-ai with event-record filtering + sidecar reassembly |
