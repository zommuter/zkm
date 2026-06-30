# 2026-06-22 — Messenger plugins: Telegram, Signal, Threema

**Started:** 2026-06-22 15:03
**Session:** a1fc4322-6075-4bfa-8433-626648369ae8
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 📬 Pim (PIM engineering), 🔐 Crys (backup-crypto / KDF / keyring) (new)
**Topic:** Scope and sequence the three remaining messenger ingestion plugins, and decide whether their arrival triggers extraction of a shared core messaging/state module.

## Surfaced discoveries
- The per-chat-day transcript doc-type already exists (`docs/messaging-spec.md`) and explicitly names `zkm-telegram`, `zkm-signal`, `zkm-threema` (lines 296–307) as conformant consumers.
- `zkm-whatsapp` v0.3.0 is the working reference: SQLite parse, watermark `state.py`, fetch-role decryption, CAS media, deterministic byte-identical re-emission.
- Difficulty ranking (research): Telegram easiest (plain JSON export, no decryption) → Signal hard (SQLCipher+keyring or signalbackup-tools) → Threema hardest (scrypt ZIP, weakest tooling, unresolved which backup holds messages).

## Agenda
1. Scope & ordering: all three at once, or Telegram-first? Confirm difficulty-driven sequence and per-plugin v1 boundary.
2. Shared abstraction (N=3 trigger): extract `zkm.state` + a shared per-chat-day renderer into core now, or keep copy-per-plugin until proven?
3. Decryption / fetch-role gating: which plugins need a hard decryption-pilot gate; resolve the Threema source-artifact question (Data Backup vs Safe).
4. Ledger setup: prefix letters, remote-first skeleton convention, entities[] emission for participants (defer or adopt).

## Discussion

### Item 1 — Scope & ordering
Archie/Pim/Crys: difficulty is Telegram (no decryption) << Signal (SQLCipher+keyring / signalbackup-tools) < Threema (scrypt ZIP, weakest tooling, source artifact unclear). Telegram Desktop "Export Telegram Data" produces a plaintext `result.json` with native integer message IDs (`telegram:<chat_id>:<msg.id>` maps straight onto the `<network>:<chat>:<msgid>` contract) and a native reply graph — closer to the `zkm-vcard` one-shot-export skeleton than to WhatsApp's watermark model. Signal is a SQLCipher DB (keyring-wrapped key on current desktop) or an Android `.backup` via `signalbackup-tools`; same post-decrypt SQLite shape as WhatsApp. Threema is a scrypt-encrypted backup with the weakest tooling. Petra/Riku argued Telegram-first with the others gated on decryption pilots; Crys flagged Threema's source-artifact uncertainty (Data Backup vs Safe).

**DP1 decision (Tobias):** Option 3 — **create all three repos/remotes + skeletons now.** Pilot details (Signal keyring/SQLCipher path, Threema source artifact + scrypt) handled inside each respective repo, not blocked on this meeting. Quote: *"3 since I'll handle the pilot details etc in the respective repos if we can't prepare enough here already."* Out of scope for all v1: secret/E2E device-local chats, live API sync (Telethon/MTProto), voice/OCR (→ zkm-stt amender).

### Item 2 — Shared abstraction (N=3 trigger)
Personas split the abstraction into three tiers: `zkm.state` (watermark, identical WhatsApp+Signal payload), a deterministic-emission contract test (every plugin needs the byte-identical re-emit check), and the renderer code (only WhatsApp exists → N=1, premature to generalize). Crys: `zkm.state` must preserve "keyed by source identifier" so multi-account stays independent. Riku: extraction must be a behavior-preserving *lift* of WhatsApp's 39 lines, not a redesign.

**DP2 decision (Tobias):** **Extract `zkm.state` + a shared byte-identical-reemit contract-test helper into core now; defer the renderer.** Each new plugin writes its own `_render_file()` until a 3rd real implementation exists, then extract the genuinely-common core. `zkm.state` is a behavior-preserving lift (same keying-by-source-path, atomic write, watermark-is-speed-only invariant).

### Item 3 — Decryption boundary, Threema artifact, ledger
Crys: fetch-vs-parse doctrine holds for all three — `convert()` reads plaintext only; decryption is a separate fetch-role step (none for Telegram; SQLCipher+keyring/signalbackup-tools for Signal; scrypt ZIP for Threema). Threema source artifact ("Safe" per `messaging-spec.md:303` vs Data Backup) is a forward-flag to resolve on the bench — Safe historically holds identity + contacts, not message bodies, so the input contract should not hardcode it. Archie: `keysource.py` (`bitwarden:<id>` / `keyring:<svc>:<acct>`) is a 4th extraction candidate — defer like the renderer. Gotcha: never name a plugin module after a stdlib module (sys.path collision under core's loader; hence WhatsApp's `keysource.py`, not `secrets.py`). Petra/Riku: reserve prefix letters, allocate rows at ≥3 items; remote-first convention non-negotiable. Pim: each skeleton ships a conformance fixture so `zkm test <plugin>` has a dynamic tier from day one.

**DP3 decision (Tobias):** **Match WhatsApp, defer entities.** Fetch-vs-parse boundary stamped on all three; plaintext-only `convert()`. Threema source = forward-flag. Reserve prefixes **T=Telegram, G=Signal, H=Threema** (allocate rows at ≥3 items). Plugins emit `participants:` only — **no `entities[]`** (a cross-plugin participant→entity amender comes later, keeping all four message plugins consistent). Defer `keysource.py` extraction until Signal/Threema actually consume it.

## Decisions
- **Three plugins, all repos created now:** `zkm-telegram`, `zkm-signal`, `zkm-threema` — remotes + skeletons pushed up front (remote-first convention). Pilot/parser detail handled inside each repo, not blocked on this meeting.
- **All three conform to `docs/messaging-spec.md`** per-chat-day doc-type: `chat/<network>/<thread_id>/YYYY-MM-DD.md`, `thread_id = sha256(chat_id)[:16]`, body `[HH:MM] sender: text <!-- key_id: … -->`, `message_id = <network>:<chat>:<msgid>`, deterministic byte-identical re-emission, `«deleted»` U+00AB/BB sentinel. Out of scope: shared renderer *code* (deferred — see below).
- **Difficulty-ordered build:** Telegram (plain JSON export, no decryption) → Signal (SQLCipher+keyring or signalbackup-tools) → Threema (scrypt Data Backup ZIP). Out of scope v1: secret/E2E device-local chats, live API sync (MTProto/Telethon), voice/OCR (→ zkm-stt amender).
- **Extract to core now:** `zkm.state` (behavior-preserving lift of WhatsApp `state.py`, keyed by source identifier for multi-account independence) + a shared byte-identical-reemit contract-test helper. **Defer:** the renderer (extract common core only after a 3rd `_render_file()` exists) and `keysource.py` (extract at 2nd real consumer). Out of scope: redesigning the watermark — lift, don't rewrite.
- **Decryption = fetch-role step, never in `convert()`** for all three. Telegram has none. Threema source artifact (Safe vs Data Backup) is a forward-flag to resolve during its pilot — do not hardcode "Safe."
- **Plugins emit `participants:` only, not `entities[]`** — matches WhatsApp; cross-source participant→entity joins are a later cross-plugin amender. Out of scope: per-plugin entity emission.
- **Prefixes reserved (not yet allocated):** `T`=Telegram, `G`=Signal, `H`=Threema; add the CLAUDE.md table row when a plugin first accumulates ≥3 unchecked items.
- Each skeleton ships a `conformance.config` fixture (Telegram: a small `result.json`; Signal/Threema fixtures arrive with their pilots). Never name a plugin module after a stdlib module.

## Action items
- [ ] Core: lift WhatsApp `state.py` → `src/zkm/state.py` (`zkm.state`), behavior-preserving (keyed by source id, atomic write, watermark-speed-only); WhatsApp imports it. Contract: existing whatsapp watermark tests pass unchanged; multi-account keying preserved. (session 2026-06-22-1503) <!-- id:f399 -->
- [ ] Core: add a shared byte-identical-reemit contract-test helper (e.g. `zkm.testing.assert_reemit_identical` or a pytest fixture); document in `messaging-spec.md`. Contract: emit→re-emit from same snapshot asserts byte-identical. (session 2026-06-22-1503) <!-- id:ab8b -->
- [ ] Create + push skeleton repos `zkm-telegram`, `zkm-signal`, `zkm-threema` (remote-first: remote created, `git push -u origin main` landed before any item marked done). Each: `plugin.yaml` (creates_dirs `chat/<net>`, `inbox/<net>`; gitignore source artifacts; `conformance.config`), `convert.py` skeleton, README, ROADMAP.md, CLAUDE.md. (session 2026-06-22-1503) <!-- id:66e0 -->
- [x] zkm-telegram: implement `convert()` parsing Telegram Desktop `result.json` → per-chat-day transcripts; `message_id = telegram:<chat_id>:<msg.id>`, reply graph from `reply_to_message_id`, media → CAS. No decryption. Ship conformance fixture. (session 2026-06-22-1503) — SHIPPED (zkm-telegram ROADMAP done); closed 2026-06-30 via Option-B reconcile. <!-- id:849f -->
- [ ] zkm-signal: decryption pilot (SQLCipher+keyring unwrap vs Android `.backup`/signalbackup-tools) is a hard gate; then `convert()` over decrypted SQLite (whatsapp skeleton). (session 2026-06-22-1503) <!-- id:b043 -->
- [ ] zkm-threema: resolve source artifact (Data Backup ZIP vs Safe) on the bench, then scrypt-decrypt fetch step + `convert()` over decrypted contents. Forward-flag: `messaging-spec.md:303` likely wrong ("Safe"). (session 2026-06-22-1503) <!-- id:c89a -->
- [x] Reserve prefix letters T/G/H in CLAUDE.md TODO-prefix table commentary; allocate a full row per plugin once it hits ≥3 unchecked items. (session 2026-06-22-1503) — OBSOLETE: prefix table retired 2026-06-30 (Option B, repo = namespace; `2026-06-30-1004-per-plugin-todo-topology-revisited.md`). <!-- id:8cf8 -->
- [ ] Forward-flag (deferred): extract `keysource.py` to core once Signal+Threema both consume it; extract shared renderer after 3rd `_render_file()` exists. (folded into id:f399/id:66e0 forward-flags; no separate id)
