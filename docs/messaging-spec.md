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
participants:                            # all addresses in From/To/Cc (or chat members)
  - "Alice Example <alice@example.com>"
  - "Bob <bob@example.com>"
direction: incoming                      # incoming | outgoing | unknown
```

### Field notes

- `message_id` — for email, use the `Message-ID` header verbatim (with angle brackets). For chat platforms, derive a stable ID from the platform's own message ID (e.g. `whatsapp:<chat_id>:<msg_id>`).
- `thread_id` — the first 16 hex chars of `sha256(root_message_id.encode())`. Stable across re-ingestion. For email, the root is the oldest `Message-ID` in the `References` chain, falling back to the message's own `Message-ID` if `References` is absent.
- `in_reply_to` — omit (don't write `null`) for root/thread-starter messages.
- `references` — use the `References` header for email; build it from the platform's reply graph for chat.
- `thread` — path relative to the store root. Always `<source_dir>/threads/<thread_id>.md`.
- `participants` — human-readable, deduplicated. Phase 2 will turn these into entity links via NER.
- `direction` — `incoming` (received), `outgoing` (sent by the store owner), `unknown` (indeterminate or group).

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
participants:
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

## Future plugins that should conform

| Plugin | Source | Notes |
|--------|--------|-------|
| `zkm-eml` | Maildir / `.eml` files | Reference implementation |
| `zkm-whatsapp` | WA local backup | Needs crypt14/15 decryption |
| `zkm-threema` | Threema Safe export | JSON export |
| `zkm-signal` | Signal SQLite DB | Requires phone access |
| `zkm-telegram` | Telegram JSON export | Built-in export feature |
| `zkm-chatlog` | AI chat exports | Various formats |
