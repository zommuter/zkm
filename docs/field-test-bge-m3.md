# Field test: bge-m3 hybrid retrieval

Run once `zkm index` (embedding phase) has completed.
Privacy: safe — bge-m3 runs via llama-swap at localhost:8080 (default), no data leaves the machine.

## Verify index completeness

```bash
cat $ZKM_STORE/.zkm-index/embeddings-meta.json
# n_docs should match your total .md count
```

## Test sequence

```bash
# 1. BM25-only baseline
zkm search "Stromrechnung" --no-dense -k 5
zkm search "invoice electricity" --no-dense -k 5

# 2. Hybrid — does dense add anything?
zkm search "Stromrechnung" -k 5
zkm search "invoice electricity" -k 5

# 3. Cross-lingual (dense should help: German query → English doc and vice versa)
zkm search "Rechnung" -k 10        # finds "invoice" docs?
zkm search "invoice" -k 10         # finds "Rechnung" docs?

# 4. Semantic / no keyword match (pure dense test)
zkm search "monatliche Kosten Strom" -k 5

# 5. End-to-end query
zkm query "Wie hoch war meine letzte Stromrechnung?"
```

## What to record

For each query, note:
- Results in hybrid but not BM25-only → dense win
- Results in BM25-only but not hybrid → RRF regression (score diluted)
- Queries that return garbage either way → content/chunking issue

These are the concrete failures that drive decisions on doc chunking,
expansion-model split, and RRF weight tuning (see TODO.md).
