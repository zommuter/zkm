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

## Why step 3 requires --expand

bge-m3 cross-lingual quality is good (cos("invoice", "Rechnung") ≈ 0.72), but on a
corpus with thousands of literal keyword matches the dense ranking is saturated:
all top-200 results by cosine are literal-match docs at ~0.95. Cross-lingual hits
at ~0.72 appear only at rank 1000+.

`--expand` uses the local LLM (qwen3.5-0.8b) to generate a bilingual hypothetical
answer that shifts the dense query vector into both language spaces, breaking through
the saturation. Steps 4 and 5 work without expansion because they test queries where
no exact keyword match exists.

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
```

These are the concrete failures that drive decisions on doc chunking,
expansion-model split, and RRF weight tuning (see TODO.md).
