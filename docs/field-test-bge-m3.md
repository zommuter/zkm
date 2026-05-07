# Field test: bge-m3 hybrid retrieval

Run once `zkm index` (embedding phase) has completed.
Privacy: safe — bge-m3 runs via llama-swap at localhost:8080 (default), no data leaves the machine.

## Verify index completeness

```bash
cat $ZKM_STORE/.zkm-index/embeddings-meta.json
# n_docs should match your total .md count

zkm doctor   # probes endpoint reachability + compares md/bm25/embed counts
```

## Test sequence

```bash
# 1. BM25-only baseline
zkm search "O2 Rechnung" --no-dense -k 5
zkm search "Cloudflare invoice" --no-dense -k 5

# 2. Hybrid — does dense add anything?
zkm search "O2 Rechnung" -k 5
zkm search "Cloudflare invoice" -k 5

# 3. Cross-lingual recall (needs --expand on literal-heavy corpora)
#    Anchor pairs chosen so the query language and the result language are disjoint:
#    - "monatliche Cloud Abrechnung" (DE) → pure-EN docs: Google Cloud/Cloudflare/AWS
#    - "mobile phone monthly bill" (EN) → pure-DE docs: "Ihre Online-Rechnung von O2"
#    Neither pair shares meaningful vocabulary across languages, so BM25-only returns 0.

# DE→EN: expect 0 without expand, ≥2 with expand
zkm search "monatliche Cloud Abrechnung" --no-dense -k 10 | grep -ic "invoice"  # expect 0
ZKM_LLM_EXPAND_MODEL=aya-expanse-8b \
  zkm search "monatliche Cloud Abrechnung" --expand -k 20 | grep -ic "invoice"  # expect ≥4

# EN→DE: expect 0 without expand, ≥2 with expand
zkm search "mobile phone monthly bill" --no-dense -k 10 | grep -i "o2"           # expect empty
ZKM_LLM_EXPAND_MODEL=aya-expanse-8b \
  zkm search "mobile phone monthly bill" --expand -k 10 | grep -i "o2"           # expect ≥2 hits

# 4. Semantic / no keyword match (pure dense test — no literal match possible)
zkm search "monatliche Kosten Telefon" -k 5    # finds O2 Rechnung docs via dense?
zkm search "cloud hosting monthly charges" -k 5 # finds Cloudflare/GCP/AWS docs via dense?

# 5. End-to-end query (expansion + dense on by default)
#    Use queries with real answers in the corpus; avoid categories with no coverage.
#    NOTE: no electricity utility bills exist in this corpus (only electricity-meter emails).
ZKM_LLM_EXPAND_MODEL=aya-expanse-8b zkm query "Was hat mein Handyvertrag bei O2 im Herbst 2014 gekostet?"
ZKM_LLM_EXPAND_MODEL=aya-expanse-8b zkm query "How much did the Hotel Katharinenhof stay cost?"

# 5b. Corpus-gap probe — verify hallucination guard (answer prompt + low-score warning)
#     Probe a category absent from the corpus.  The LLM should say so explicitly;
#     a "top-hit relevance is low" warning may appear on stderr if top hit is weak.
#     Expected: answer names retrieved docs as phone/meter emails, NOT an invented electricity figure.
ZKM_LLM_EXPAND_MODEL=aya-expanse-8b zkm query "Wie hoch war meine letzte Stromrechnung?"

# Counter-test: a query WITH real corpus support must NOT warn and must give a concrete answer.
ZKM_LLM_EXPAND_MODEL=aya-expanse-8b zkm query "Was hat mein Handyvertrag bei O2 im Herbst 2014 gekostet?"
```

## Step 5b live results — 2026-05-07

**Corpus-gap probe** (`"Wie hoch war meine letzte Stromrechnung?"`):

```
Die Daten zur Stromrechnung sind ausschließlich aus E-Mails von Tobias Kienzler zu den O2
Online-Rechnungen. Keine der oben genannten E-Mails enthält direkt eine Stromrechnung, sondern
enthält nur Informationen zu anderen Themen wie Arbeitsbemühungen, Steuererklärung, Stellensuche
oder Vertragsverhandlungen. … Die E-Mails enthalten Informationen über andere Themen, nicht
direkt über Stromrechnung.
```

Result: LLM correctly refused to invent an electricity figure and named the actual content
(O2 phone bills, meter-reading email `zählerstand.md`, unrelated mails). No low-score warning
fired — `[1]` is a literal "Stromkosten" document that scored above the dense floor — but the
answer is correctly grounded. Hallucination guard confirmed working.

**Counter-test DE** (`"Was hat mein Handyvertrag bei O2 im Herbst 2014 gekostet?"`):

LLM answered "14,98 EUR monatlich" with citations [2]–[10] from the 2014 O2 invoice emails.
No low-confidence warning. Concrete grounded answer confirmed — guard doesn't over-refuse.

**Counter-test EN** (`"How much did my O2 mobile contract cost in autumn 2014?"`):

LLM answered in English (bilingual clause working), same invoice documents retrieved. It
correctly noted the distinction between "contract terms" and "monthly subscription fees",
then answered from the actual invoices (15.37 EUR Sept 2014, 14.98 EUR Oct 2014, 15.58 EUR
Nov 2014). Relevance-judgement instruction visible even on a legitimate but slightly imprecise
question — appropriate nuance without refusing.

## What to record

For each query, note:
- Results in hybrid but not BM25-only → dense win
- Results in BM25-only but not hybrid → RRF regression (score diluted)
- Queries that return garbage either way → content/chunking issue
- "dense leg skipped" warning on stderr → endpoint or index issue (run `zkm doctor`)
- Step 3 baseline must be 0 — if non-zero, the anchor pair is contaminated (pick a different one)
- "query expansion failed (timed out)" on step 5 → aya-expanse-8b wasn't warm; answer still
  comes from raw BM25 so it is usually still correct, but re-run once the model is loaded

## Why step 3 requires --expand and a bilingual model

bge-m3 cross-lingual quality is good (cos("invoice", "Rechnung") ≈ 0.72), but on a
corpus with thousands of literal keyword matches the dense ranking is saturated:
all top-200 results by cosine are literal-match docs at ~0.95. English "invoice" docs
at cosine ~0.72 sit at rank 1000+ — far behind all the German "Rechnung" docs.

`--expand` works by generating multilingual keyword variants and running a separate BM25
leg for each. The English keyword "invoice" finds English-only billing docs that the
German-query BM25 and the saturated dense leg both miss.

### Choosing anchor pairs for step 3

The step 3 pairs were chosen so the query vocabulary and the result vocabulary are
disjoint: O2 bills contain only "Rechnung" (no "bill"/"invoice"); Google Cloud / Cloudflare
/ AWS billing emails contain only "invoice" (no "Rechnung"/"Abrechnung"). The BM25
baseline *must* return 0 for the other-language docs — if it doesn't, the pair is
contaminated by shared vocabulary and the test is not informative.

**Do not use** pairs where a proper noun (hotel name, brand name) appears in both languages
of the same document, e.g. "Hotel Katharinenhof" sent both a German "Rechnung" and an
English "invoice" email for the same stay — BM25 finds both via the shared proper noun
regardless of expansion.

**Bilingual capability is about instruction-following, not parameter count.**
Tested against every configured model on this machine; only `aya-expanse-8b` and
`qwen3.5-35b` produce keywords in both languages regardless of the query language.

| Model | DE→EN | EN→DE | Notes |
|---|---|---|---|
| `qwen3.5-0.8b` (default RAG) | ❌ | ❌ | Produces only the input language |
| `llama-3.2-3b` | ✓ semantic | ✓ semantic | Format incompatible — parser yields 0 keywords |
| `deepseek-r1-7b` | ❌ | — | Reasoning mode burns the 150-token budget; empty output |
| `qwen3-coder-30b` | ❌ | ✓ | Fails German→English; leaks "Section 1" as keyword |
| `qwen3.5-35b` | ✓ | ✓ | Works reliably with the current prompt |
| **`aya-expanse-8b`** | ✓✓ | ✓✓ | Best bilingual; parser handles its markdown format |

Configure a model explicitly for expansion (it defaults to `ZKM_LLM_MODEL`):

```bash
# In $ZKM_STORE/.env or shell profile:
ZKM_LLM_EXPAND_ENDPOINT=http://localhost:8080
ZKM_LLM_EXPAND_MODEL=aya-expanse-8b   # best bilingual; ~11 t/s, 5 GiB
# ZKM_LLM_EXPAND_MODEL=qwen3.5-35b   # alternative; clean format, ~6 t/s, 21 GiB
# ZKM_LLM_MODEL stays as qwen3.5-0.8b for fast RAG answers

zkm doctor   # shows both "llm endpoint" and "expand endpoint" when they differ
```

Steps 4 and 5 work without expansion because they test queries where no exact keyword
match exists, so pool saturation is not the problem.

## Diagnostic checklist

If step 3 returns no cross-lingual hits even with `--expand`:

```bash
# 1. Confirm dense is actually running (no "dense leg skipped" on stderr)
zkm search "Rechnung" -k 5 2>&1 | grep "dense leg"

# 2. Check index and endpoint health
zkm doctor

# 3. Verify bge-m3 cross-lingual similarity directly
curl -s http://localhost:8080/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"bge-m3","input":["invoice","Rechnung"]}' | \
  python3 -c "
import json,sys,numpy as np
d=json.load(sys.stdin)['data']
v=[np.array(x['embedding']) for x in d]
print(f'cos(invoice, Rechnung) = {v[0]@v[1]/(np.linalg.norm(v[0])*np.linalg.norm(v[1])):.3f}')
"
# Expected: ~0.72. If < 0.5, the wrong model is loaded.

# 4. Probe the expand model directly — confirm both languages appear in Section 1
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"aya-expanse-8b","messages":[{"role":"user","content":"The user question may be in English or German. The document corpus contains BOTH languages.\nOutput Section 1, then a blank line, then Section 2.\n\nSection 1 — Search terms: produce keyword phrases in BOTH languages, one per line, no blank lines, no bullets, no markdown. Each phrase must be ≤4 words. Output 3 English phrases, then 3 German phrases. Translate the question main concepts into the OTHER language. Do not repeat phrases.\n\nSection 2 — Hypothetical answer: one sentence that would be a plausible answer, in either language.\n\nQuestion: Rechnung"}],"max_tokens":250}' \
  | python3 -c "
import json,sys,re
c=json.load(sys.stdin)['choices'][0]['message']['content']
en=bool(re.search(r'\b(invoice|bill|receipt|payment)\b',c,re.I))
de=bool(re.search(r'\b(rechnung|abrechnung|faktura|zahlung)\b',c,re.I))
print('EN terms:', en, '  DE terms:', de, '  → bilingual:', en and de)
print(c[:300])
"
# Expect: bilingual: True
```

These are the concrete failures that drive decisions on doc chunking,
expansion-model split, and RRF weight tuning (see TODO.md).
