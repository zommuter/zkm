# 2026-06-04 — Tracking OpenPGP keys & signature validity in zkm

**Started:** 2026-06-04 10:02
**Session:** 01158050-5a5f-435b-b1e2-0fd06794be00
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🔐 Dario (E2E-PIM/Proton lens, re-onboarded), 🧬 Nora (entity-vs-value typology, re-onboarded)
**Topic:** Given Proton's OpenPGP-centric model, how should zkm track public keys (vCard) and signature validity (eml)?

## Surfaced discoveries
- [2026-05-29 proton-moresync] Fetch-vs-ingest split: fetch layer (Go go-proton-api) emits a versioned standard-format tree (RFC vCard/iCal + .meta sidecar); Python zkm plugin ingests. Standard tree is the language-neutral contract.

## Agenda
1. What does "tracking" buy — preservation, searchability, or verification?
2. Public keys: source and storage shape (vCard KEY → entity + CAS?)
3. Signature validity: the three-tier problem — what is v1?
4. Fingerprint as cross-doc join: entity type + canonical normaliser + the no-auto-merge boundary
5. Scope & sequencing vs the W-series (WhatsApp) work

## Grounding (code exploration)
- **zkm-vcard** (`convert.py`): parses FN/EMAIL/TEL/ORG/URL/IMPP/ADR/PHOTO — does **NOT** read vCard `KEY`. PHOTO→CAS+`photo:` pointer is the reuse template.
- **zkm-eml** (`parse.py`, `frontmatter.py`): stdlib `email` module; no PGP/DKIM/ARC handling. `multipart/signed`/`multipart/encrypted` in `_MULTIPART_TYPES` are skipped as containers → `application/pgp-signature` leaf silently becomes a generic CAS attachment. DKIM-Signature / Authentication-Results / ARC-* headers never read (survive only in stored stripped .eml).
- **γ entity model** (`docs/entity-model.md`): fields scope/type/value/canonical/standard/unit/valid. No fingerprint/key/verification concept. Scopes include `signature` (planned).
- **`zkm.canonical`** (`src/zkm/canonical.py`): 5 normalisers — iban/amount/email/phone/iso8601. Pure stdlib. No fingerprint.
- **dedup key** (`amendments.py:135`): `(scope,type,value)` — dedups on raw `value`, not `canonical`.

## Discussion

### Item 1 — What tracking buys
Three distinct payoffs: **(a) preservation** (already ~free via CAS), **(b) searchability** (promote structured facts to frontmatter/entities[] — the zkm value-add), **(c) verification** (different universe of cost). Dario: Proton verifies server-side; re-verifying received mail means rebuilding a keyring you don't have. Riku: "validity" is a trap word — a provider verdict is time-stamped and NOT re-verifiable (DNS keys rotate); laundering it as a zkm fact under bare `valid:` is wrong. Nora: the entity model's existing `valid:` means checksum correctness, not third-party verdict — keep lexically distinct.

### Item 2 — Public keys
Source: vCard `KEY` (RFC 6350 §6.8.1). Precedent in codebase: PHOTO→CAS+`photo:` pointer. Nora: fingerprint is a **value-type** (like IBAN — normalisable hex with governing standard); key-with-uIDs/expiry is a richer object — emit the fingerprint entity, CAS the bytes. Dario: vCard KEY is the right v1 source; forward-flag inline `application/pgp-keys` MIME + `Autocrypt:` header. Riku: KEY form must be branched — embedded/data-URI → decode+CAS+fingerprint; bare URI → reference only (no fabricated fingerprint). Fingerprint computation needs OpenPGP packet parse (SHA-1 over pubkey packet body — not stdlib).

**D1 (user): Compute fingerprint now.** Dependencies: **pgpy** (pure-Python, no system binary, no `~/.gnupg` state side effect). Contract: fingerprint best-effort, CAS preservation mandatory. `zkm.canonical.fingerprint(s)`: strip ws/colons/`0x`, uppercase, validate hex len 40→`openpgp-v4` / 64→`openpgp-v6`; invalid → `valid: false` + raw (IBAN pattern). One `fingerprint` entity per key — no uID/expiry/revocation/algorithm sub-entities (Petra: N=1). pgpy is a **zkm-vcard dep**, not core.

### Item 3 — eml signature validity: three tiers
- **Tier A** (structural presence, stdlib-free): detect `multipart/signed` + `application/pgp-signature`/`pkcs7-signature` → emit `signed: pgp-mime` or `signed: smime`.
- **Tier B** (provider verdict, stdlib-free): parse `Authentication-Results:`, `DKIM-Signature:`, `ARC-*`, `X-Pm-*` headers into provenance-named `auth_results:` block. These headers survive verbatim in our stored stripped .eml → re-runnable.
- **Tier C** (true crypto re-verification): needs keyring + every signer's public key. Proton already did it server-side → mirage for received mail; N=0 → "observe before preventing" says defer.

**D2 (user): Tier A + B only.** `signed:` enum + message-level `auth_results:` block (dkim/spf/dmarc + `verified_by: provider` + raw `source:` header). NOT entities[] (document-level, not mentions). Provenance naming mandatory — never bare `verified: true`. Signature leaf CAS-preserved, excluded from `attachment_inbox` fan-out (Dario). Tier C deferred.

Impl sites: `parse.py:185` (`_extract_parts`), `parse.py:77` (header reads), `frontmatter.py:31`.

### Item 4 — Fingerprint as cross-doc join
Nora: a v4 fingerprint is a true crypto UID — collision-resistant, globally unique, machine-verifiable. The no-auto-merge rule was built for *names*, not this. Riku: exact-match JOIN of key-occurrences is safe; person-MERGE is still inference (shared role keys, forwarded keys, keys-about-others). **The rule stands for person-merge; fingerprint earns the exception only for key-occurrence linking.** Dario: Proton binds key↔email, never fuses person identity.

**D3:** Fingerprint = exact-match join key, the first **join-grade value-type**. NOT a person-merge license. No v1 join code — emergent from shared `(scope,type,value)` dedup space. Deliverable: one doc note in `entity-model.md`. Phase-4 manual-merge ranks fingerprint matches above name matches (human-confirmed).

### Item 5 — Sequencing
**D4 (user): Build PGP chain now**, order core → eml → vcard. Each = separate repo + version bump. Fixtures-first (Riku): vCard with embedded KEY; PGP/MIME-signed .eml with Authentication-Results — new fixtures in existing synthetic-corpus frame, not new infra. W-series resumes after.

## Decisions
- **D1.** zkm-vcard reads vCard `KEY` (RFC 6350 §6.8.1); computes real OpenPGP fingerprint via **pgpy**. Per key: `write_object` bytes + `key:` frontmatter pointer + emit `{scope: contact, type: fingerprint, value, canonical, standard: openpgp-v4|v6}`. Best-effort parse (failure → keep bytes, skip entity). KEY-form branch: embedded/data-URI → decode+fingerprint; bare URI → reference only. **Out of scope:** uID/expiry/revocation/algorithm sub-entities; gnupg binary; key fetch (WKD/keyserver = fetch-role).
- **D2.** zkm-eml Tier A+B. `signed:` enum + `auth_results:` provenance block. Document-level frontmatter, not entities[]. Signature leaf CAS-preserved, excluded from inbox fan-out. **Out of scope:** Tier C; bare `verified: true`.
- **D3.** Fingerprint = join-grade value-type. NOT person-merge license — person identity stays Phase-4 manual-merge. **Out of scope:** v1 join/graph code; auto person-merge.
- **D4.** Build PGP chain now: core → eml → vcard. Fixtures-first. W-series after.

## Action items
- [ ] **PGP1.** Add `zkm.canonical.fingerprint(s)` to `src/zkm/canonical.py`; add `fingerprint` to entity-type registry + join-grade note in `docs/entity-model.md`; test in `tests/test_canonical.py`. Contract: canonical = uppercase hex no-sep; bad hex → `valid: false`. See this meeting note. <!-- id:734f -->
- [ ] **PGP2.** zkm-eml Tier A+B: `parse.py:185` detect signed leaf + CAS-preserve (exclude inbox); `parse.py:77` read auth headers; `frontmatter.py:31` emit `signed:` + `auth_results:`. Fixture: PGP/MIME-signed .eml w/ Authentication-Results. Version bump. See this meeting note. <!-- id:4649 -->
- [ ] **PGP3.** zkm-vcard KEY+pgpy: read KEY in `_extract_entities`/`_process_vcard`, branch on form, `write_object` bytes + `key:` pointer, pgpy fingerprint → `fingerprint` entity. Add pgpy dep to `plugin.yaml`. Fixture: .vcf w/ embedded KEY. Version bump. See this meeting note. <!-- id:961b -->
- [ ] **PGP4 (forward-flag/design-note).** eml inline `application/pgp-keys` + `Autocrypt:` = future 2nd `fingerprint` producer (Phase-4 join). Design note in `docs/entity-model.md`. No v1 code. See this meeting note. <!-- id:d54f -->
