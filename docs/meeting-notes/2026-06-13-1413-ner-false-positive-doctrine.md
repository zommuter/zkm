# 2026-06-13 — NER false-positive doctrine ("wrong entity worse than no entity")

**Started:** 2026-06-13 14:13
**Session:** 5ea072b1-41e2-4c50-b338-c1aaa2ccfc77
**Attendees:** 🧬 Nora (IE/NER typology), 🏗️ Archie (architect), 😈 Riku (devil's advocate), ✂️ Petra (productivity)
**Topic:** Ratify one store-wide precision/recall doctrine the executor can apply consistently, replacing per-box judgment on 204c (LinkedIn employer fallback), 4352 (currency allowlist), b081 (lowercase IBAN).

## Surfaced discoveries
- `entity-model.md:49` — every entity already carries `valid` (False if normalisation failed checksum); dedup key `(scope, type, value)`.
- `ner.md:18-21` — high-precision pattern overlay applied first, then POS-filter + stoplists; `ner.md:33` IBAN row already specs mod-97 → `valid:false` on fail.
- The architecture already separates checksum-verifiable from unverifiable types; the doctrine was implicit but unstated.

## Agenda
1. The doctrine — one precision/recall rule, or three separate calls?
2. Currency allowlist (4352) — do BTC/ETH belong, and what's the extension rule?
3. Lowercase IBAN (b081) — is the mod-97 gate sufficient alone?

## Discussion
Nora reframed the three boxes as one decision the codebase had already half-drawn: entities split into **verifiable** (intrinsic validity test — IBAN mod-97, currency set-membership) and **unverifiable** (person/org/loc — no test, a wrong guess is permanent search pollution). Doctrine is asymmetric by class: unverifiable → precision-first (drop on ambiguity); verifiable-by-checksum → recall-permissive (emit `valid:false` on failure, let the gate sort it). Archie mapped all three boxes onto it. Riku caught the trap in 4352: currency has no checksum, so the allowlist *is* the precision gate — broadening it manufactures FPs (`MAX`/`ANY`/`ART` shape-matches) that `valid:` cannot catch because they *are* in the list. Nora refined to **three arms**, adding closed-set-verifiable (keep minimal + evidence-gated). Petra justified the BTC/ETH exception by corpus signal (crypto-adjacent) and demanded the extension bar be a logged census case, not intuition. Riku named the `valid:false` census (1a6f) as the instrument: tune by measured FP rate, not vibes; until it has real counts, stay tight. Archie placed the doctrine in `ner.md` with each type-table row declaring its class.

## Decisions
- **D1 — Three-arm precision doctrine (ratified).** (a) **Unverifiable** types (person, org, location, misc) → **precision-first**: when extraction is ambiguous, emit nothing. (b) **Checksum-verifiable** types (IBAN) → **recall-permissive**: emit the candidate, set `valid:false` on checksum failure, let the validity gate + census handle it; no extra type-specific penalty. (c) **Closed-set-verifiable** types (currency) → keep the set **minimal and evidence-gated**; the set membership is the only precision boundary, so it must stay closed. New entity types MUST declare their class in the `ner.md` type table and inherit the arm. The `valid:false` census (1a6f) is the sole instrument for retuning any knob. Out of scope: an LLM verifier pass (already backlogged N9d, gated on post-N9c residual rate).
- **D2 — 204c resolved.** LinkedIn employer/org is unverifiable → precision arm → **drop the broad first-span fallback**; unrecognized experience markup yields NO employer. Confirmed.
- **D3 — b081 resolved.** IBAN is checksum-verifiable → recall arm → **accept lowercase IBANs**, emit with `valid:false` when mod-97 fails. The checksum is the gate; **no extra lowercase-only confidence penalty**. Confirmed.
- **D4 — 4352 resolved.** Currency allowlist = **ISO-4217 active codes ∪ {BTC, ETH}** only. BTC/ETH earn the exception by high corpus signal (crypto-adjacent). The bar for any third crypto code is a **logged FP/recall case from the `valid:false` census**, documented in `ner.md` — not intuition. Out of scope: a broad crypto-ticker list (rejected — manufactures uncatchable FPs).

## Action items
- [ ] Add a **§Precision doctrine** to `docs/ner.md` (three arms: unverifiable / checksum-verifiable / closed-set-verifiable); annotate each row of the type table (`ner.md:33`) with its class; new types declare class on add. (2026-06-13 ner-fp-doctrine mtg) <!-- id:b99e -->
- [ ] zkm-ner currency (4352): freeze the allowlist at ISO-4217 ∪ {BTC, ETH}; document the census-logged extension bar in `ner.md`. (2026-06-13 ner-fp-doctrine mtg) <!-- id:f40c -->
- [ ] Apply the doctrine to the open boxes as confirmations: 204c (drop org fallback, zkm-social), b081 (accept lowercase IBAN + valid:false, no penalty, zkm-ner) — verify the red tests encode the doctrine arm, then tick. (2026-06-13 ner-fp-doctrine mtg) <!-- id:346c -->
