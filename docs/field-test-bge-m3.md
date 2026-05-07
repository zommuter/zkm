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
zkm search "Stromrechnung" --no-dense -k 5
zkm search "invoice electricity" --no-dense -k 5

# 2. Hybrid — does dense add anything?
zkm search "Stromrechnung" -k 5
zkm search "invoice electricity" -k 5

# 3. Cross-lingual recall (needs --expand on literal-heavy corpora)
#    With thousands of literal "Rechnung" docs, the top-k dense ranks are saturated
#    by exact matches (cosine ~0.95). Cross-lingual hits at cosine ~0.72 surface
#    only when the pool is wide enough AND LLM expansion provides multilingual context.
zkm search "Rechnung" --expand -k 50 | grep -i invoice | wc -l   # expect ≥ 2
zkm search "invoice"  --expand -k 50 | grep -i rechnung | wc -l  # expect ≥ 2

# 4. Semantic / no keyword match (pure dense test — no literal match possible)
zkm search "monatliche Kosten Strom" -k 5   # finds "Stromrechnung" docs?
zkm search "monthly electricity costs" -k 5  # finds German docs?

# 5. End-to-end query (expansion + dense on by default)
zkm query "Wie hoch war meine letzte Stromrechnung?"
```

## What to record

For each query, note:
- Results in hybrid but not BM25-only → dense win
- Results in BM25-only but not hybrid → RRF regression (score diluted)
- Queries that return garbage either way → content/chunking issue
- "dense leg skipped" warning on stderr → endpoint or index issue (run `zkm doctor`)

## Why step 3 requires --expand and a bilingual model

bge-m3 cross-lingual quality is good (cos("invoice", "Rechnung") ≈ 0.72), but on a
corpus with thousands of literal keyword matches the dense ranking is saturated:
all top-200 results by cosine are literal-match docs at ~0.95. English "invoice" docs
at cosine ~0.72 sit at rank 1000+ — far behind all the German "Rechnung" docs.

`--expand` works by generating multilingual keyword variants (e.g., expanding "Rechnung"
to include "invoice", "bill", "Faktura") and running a separate BM25 leg for each. The
English keyword "invoice" finds English-only invoice docs that the German-query BM25 and
the saturated dense leg both miss.

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
