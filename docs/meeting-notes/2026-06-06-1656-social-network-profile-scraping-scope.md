# 2026-06-06 — Social-network profile scraping scope

**Started:** 2026-06-06 16:56
**Session:** 7088bd36-13d6-44d6-ae10-4cc8365f3351
**Attendees:** 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity), 🧬 Nora (IE/NER typology — re-onboarded), ⚖️ Cleo (new — data-acquisition legality / platform-ToS / third-party-privacy lens)
**Topic:** Scope how social-network profile data (LinkedIn/X/Instagram/Mastodon/GitHub) enters zkm — acquisition method, identity-card vs activity-feed, and whether profile data goes into `entities[]` (γ schema) or its own document type.

## Surfaced discoveries
- [2026-05-10 zkm] Person name is NOT a unique identifier — identity-strong fields (email, LinkedIn URL, GitHub URL) exact-match clusterable; name needs human confirmation — see `docs/meeting-notes/2026-05-10-1148-entity-extraction.md`
- [2026-05-12 zkm] (now FALSE — corrected this session) BM25/embed ignored entities[]/participants[]: E8 (commit e56dd55, 2026-05-12) indexes entities[] value+canonical and participants[] address+name in both BM25 and embed
- [2026-05-08 zkm] Face detection ≠ face recognition; profile photo without enrollment gives clusters, not names

## Pre-meeting findings
- **vCard front-runs this** (`TODO.md:81`, id:2638): zkm-vcard v0.3.0 (shipped) already handles structured-export identity cards — FN→person, EMAIL/TEL/ORG/URL typed, social URLs → `linkedin_profile`/`github_profile`/`social_handle.<platform>`, PHOTO→CAS, KEY→fingerprint. All at `scope:contact`. Dedup-on-UID.
- **entities[] IS indexed** (E8): the entities-not-indexed premise in the TODO was stale.
- **Entity pages are NOT a data-model concept** (`docs/entity-model.md:5-23`): live WebUI aggregation (search→collect→LLM-summarize), Phase 3, not pre-computed. No per-person markdown file.
- **Media path exists**: `zkm.cas.write_object`; used by zkm-photo v0.4.0 and vCard PHOTO already.
- **Sibling TODO** (`TODO.md:116`): "takeout / export archive import" — offline structured archives; the LinkedIn browser-save lane converges with that work.

## Agenda
1. Acquisition boundary: takeout-export vs API vs live-scraping — relation to the takeout-import TODO
2. Identity-card vs activity-feed: which slice is in scope for v1?
3. Schema: `entities[]` (vCard pattern) vs a new doc-type
4. Network prioritization and plugin structure

## Discussion

Initial framing (Agenda 1): Cleo named the three acquisition lanes and their risk gradient. Archie noted that live scraping would be the first plugin doing authenticated live network I/O — a new architectural class. Riku flagged that pulling third-party profiles builds dossiers on others, not self-management. Nora observed vCard already covers the structured-export identity-card case.

**Human intervention (Tobias):** "Keep all three on the table — dossier building might become relevant for leads etc, but even to just get a photo of the person I'm planning to talk to or to jog my memory."

This reframed the meeting: single-subject, user-initiated third-party capture is explicitly in scope. The meeting-prep/lead use-case — "a photo before I meet someone" — is the concrete use-case Cleo had asked for.

Cleo drew the gradient: "Pull one person's public photo + headline before I meet them" (single-subject, user-initiated, on-demand) vs "build a lead database" (bulk, automated, multi-subject) — same data type, opposite risk profile. The first is what every CRM does; the second is gated.

Archie named the mechanical split: LinkedIn profiles are not fetchable unauthenticated (returns auth-wall stub). Capture for auth-walled networks must happen in the user's own authenticated browser session. GitHub is the opposite — clean public API, no auth required.

For Agenda 2, Nora noted that a captured profile is structurally a **contact** (same fields as vCard output). No new doc-type needed.

For Agenda 3, the panel converged on reusing the contact doc shape with a new `scope:profile.<network>`, URL-keyed dedup, no auto-merge (Phase-4 manual identity merge). Riku held the line on not building a live LinkedIn fetcher that silently fails; the honest mechanism for auth-walled networks is local-file ingest.

For Agenda 4, Nora proposed GitHub (API lane) + LinkedIn (browser-save lane) as a genuine N=2 that exercises both acquisition lanes. Riku insisted the extension is a sequenced follow-on — ship the file-ingest + GitHub-API plugin first, prove the doc shape, then build the extension. Petra applied N=2 to the shared-contact-writer question — don't extract now, inline at two consumers per the 2026-05-14 finding.

## Decisions

- **D1 — Acquisition boundary.** Single-subject, user-initiated profile capture is IN scope. Automated, multi-subject *bulk* crawling (lead-list building) is OUT — gated behind a future escalation requiring a concrete use-case + ToS clearance. *Out of scope: any background/automated crawler in v1.*
- **D2 — Capture mechanisms.** Two lanes: **(A)** browser-save → local-file ingest (you save the profile in your own authed browser as HTML/PDF/MHTML; zkm parses the local file — for auth-walled LinkedIn/X/IG); **(B)** GitHub public API fetch (genuinely-public dev data). Paste-URL → server-side fetch **rejected** (silently fails on auth-walled networks, highest ToS risk). Browser extension/bookmarklet is an ergonomic capture front-end over lane (A) — a *sequenced follow-on*, not v1. *Out of scope: server-side fetch of auth-walled profiles.*
- **D3 — Slice.** Identity-card only (name, headline, employer, location, photo, profile URLs). Activity-feed (posts, reactions, comments, being-tagged) is OUT → separate future meeting (overlaps `messaging-spec.md`). *Out of scope: posts/feed ingestion in v1.*
- **D4 — Schema.** Reuse the existing contact doc shape `contacts/<slug>.md`; profile fields → typed `entities[]` at a new `scope:profile.<network>`; photo → CAS (`zkm.cas.write_object`); **dedup-keyed on normalized profile URL** (byte-identical re-emit on re-capture). **No auto-merge** with vCard contacts for the same person — identity merge stays Phase-4 manual/human-confirmed. *Out of scope: identity merge, a new doc-type, a sibling `people/` dir.*
- **D5 — Unified "one page per person" view.** Delivered by the Phase-3 live WebUI entity page (search → aggregate docs carrying `person:` + `linkedin_profile:` → render), fed by these source notes. NOT a v1 artifact — v1 produces N notes per person (vCard + each captured profile). *Out of scope for v1: any unified person page.*
- **D6 — Plugin structure.** New `zkm-social` plugin with per-network parser modules (`github`, `linkedin`). Not an extension of `zkm-vcard` (different input format, same output shape). **No shared contact-writer extraction yet** — N=2 inline-duplication per the 2026-05-14 finding; extract a shared `zkm.contact` writer only at a 3rd consumer or first shape divergence. *Out of scope: refactoring zkm-vcard.*
- **D7 — v1 networks.** GitHub (API lane) + LinkedIn (browser-save lane) — the two highest-value networks that exercise both acquisition lanes (real N=2). X/Instagram/Mastodon/Facebook deferred; Mastodon (also API-public) is a cheap third if wanted later. *Out of scope: more than two networks in v1.*
- **D8 — Contract guardrail.** Plugin contract is single-subject, user-initiated capture only. No batch-crawl entry point. GitHub API lane makes bulk trivial technically, so the guardrail is documented norm + absence of a list-of-names entry point. *Out of scope: convenience bulk ingestion.*

## Action items

- [ ] **SOC1.** Build `zkm-social` plugin skeleton: `plugin.yaml` (`creates_dirs: [contacts, originals/contacts]`), `convert(store_path, config) -> list[Path]` with per-network parser dispatch. Contract: configured source dir + network config routes to the right parser; emits vCard-compatible contact doc shape. See this note. <!-- id:56ac -->
- [ ] **SOC2.** GitHub parser module (lane B): fetch `api.github.com/users/<login>`, map login/name/bio/company/location/blog/avatar → `contacts/<slug>.md`, typed `entities[]` at `scope:profile.github`, avatar → CAS, dedup-keyed on profile URL. Contract: GitHub username → one contact note; re-run is a git no-op. <!-- id:017f -->
- [ ] **SOC3.** LinkedIn parser module (lane A): parse a browser-saved LinkedIn profile (HTML/PDF/MHTML) for name/headline/current-employer/location/photo/profile-URL; emit `contacts/<slug>.md` at `scope:profile.linkedin`, photo → CAS, dedup-keyed on normalized profile URL. Contract: saved profile file → one contact note; no live network I/O, no credentials. <!-- id:7f55 -->
- [ ] **SOC4** (sequenced follow-on, after SOC1–3 prove the doc shape). Browser extension / bookmarklet capture: one-click capture of the rendered profile into the `zkm-social` source dir. Contract: capture button → file in source dir → existing ingest path produces the note. <!-- id:dfa4 -->
- [ ] **SOC5** (deferred — separate meeting). Activity-feed doc-type scoping (posts/reactions/being-tagged); overlaps `messaging-spec.md`. Reopen when a concrete feed use-case appears. <!-- id:a580 -->
- [ ] **SOC6** (deferred — gated escalation). Bulk / lead-gen multi-subject capture. Gate: a concrete use-case + ToS clearance + deliberate decision to cross the single-subject boundary. <!-- id:3de4 -->
- [ ] **SOC7.** Close/supersede the social-network scoping TODO (`TODO.md:115`) by marking it done and cross-linking this note; cross-link the takeout-import TODO (`TODO.md:116`) — the LinkedIn browser-save lane converges with LinkedIn-takeout ingest; keep separate but note the shared-parser opportunity. See this note. <!-- id:838c -->
