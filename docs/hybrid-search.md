# Hybrid search: BM25 + dense embeddings

zkm's retrieval pipeline combines **sparse BM25** and **dense vector search**, fused with Reciprocal Rank Fusion (RRF). The dense leg is optional and degrades gracefully when not configured.

## Architecture

```
                       ┌─────────────────────────────┐
  zkm search / query → │  search_with_expansion()    │
                       │   or search_hybrid()        │
                       └────────────┬────────────────┘
                                    │
               ┌────────────────────┴─────────────────────┐
               │                                          │
         BM25 leg                                   Dense leg
    (expand_query_with_hyp                     (embed question +
     → multi-BM25 → RRF)                      hypothetical text
                                               → EmbedStore.topk)
               │                                          │
               └────────────────────┬─────────────────────┘
                                    │
                              rrf_merge()
                                    │
                              top_k hits
```

### Why hybrid?

BM25 is lexical: it misses paraphrases, cross-lingual matches, and conceptual synonyms ("invoices" vs "Rechnung"). Dense embeddings capture semantics. RRF fusion keeps the strengths of both without needing tuned weights.

### Fusion formula

Reciprocal Rank Fusion (`rrf_merge`, `query.py`):

```
score(d) = Σ  1 / (k + rank_i(d))   for all lists containing d
```

Default `k = 60`. Dense hits and BM25-RRF hits are treated as two input lists.

## Configuration

| Env var | Default | Description |
|---|---|---|
| `ZKM_EMBED_ENDPOINT` | *(empty — dense disabled)* | Base URL of an OpenAI-compatible `/v1/embeddings` server |
| `ZKM_EMBED_MODEL` | `bge-m3` | Embedding model name |
| `ZKM_EMBED_KEY` | *(empty)* | Bearer token (leave empty for local servers) |

Same lookup order as LLM config: CLI override → env var → `$ZKM_STORE/.env` → default.

### Serving bge-m3 locally

**llama-swap** (llama.cpp serving, zero-downtime model swapping):

```bash
# In your llama-swap config, add bge-m3 as an embed model
# Then set:
export ZKM_EMBED_ENDPOINT=http://localhost:8080
export ZKM_EMBED_MODEL=bge-m3
```

**Ollama**:

```bash
ollama pull bge-m3
export ZKM_EMBED_ENDPOINT=http://localhost:11434
export ZKM_EMBED_MODEL=bge-m3
```

**llama.cpp server** (standalone):

```bash
llama-server --model bge-m3.gguf --embedding --port 8081
export ZKM_EMBED_ENDPOINT=http://localhost:8081
export ZKM_EMBED_MODEL=bge-m3
```

## Indexing

```bash
zkm index                   # BM25 + embeddings (if ZKM_EMBED_ENDPOINT set)
zkm index --no-embed        # BM25 only, skip embedding pass
```

The embedding index is stored at `$ZKM_STORE/.zkm-index/embeddings.npz` (compressed NumPy) and `embeddings-meta.json`. It is incremental: unchanged docs (same mtime) reuse their cached vectors.

When the `ZKM_EMBED_MODEL` changes, the cache is discarded and all docs are re-embedded.

## Querying

```bash
zkm search "invoices last month"           # BM25 + dense (default)
zkm search --no-dense "invoices"           # BM25 only
zkm query "what did I pay in March?"       # expansion + BM25 + dense + LLM answer
zkm query --no-dense "..."                 # expansion + BM25 only + LLM answer
zkm query --no-expand --no-dense "..."     # bare BM25 + LLM answer
```

### Graceful degradation

- `ZKM_EMBED_ENDPOINT` not set → dense leg silently skipped.
- `embeddings.npz` missing (e.g. `zkm index --no-embed` was used) → dense leg silently skipped.
- Embed endpoint unreachable at query time → dense leg silently skipped, BM25 result returned.

No flag is needed to enable degradation; it is automatic.

## Storage

```
$ZKM_STORE/.zkm-index/
├── bm25.pkl               # BM25 index (existing)
├── embeddings.npz         # Dense vectors (float32, L2-normalized, compressed)
└── embeddings-meta.json   # Model name, dim, n_docs, built_at
```

Both files are gitignored (`.zkm-index/` is already in `.gitignore`).

## Implementation

- **`src/zkm/embed.py`** — `EmbedStore`, `embed_texts`, `build_embed_store`, `save/load_embed_store`, `resolve_embed_config`
- **`src/zkm/query.py`** — `_dense_search`, `search_hybrid`, updated `search_with_expansion`
- **`src/zkm/index.py`** — `build_index` unchanged; `cmd_index` in `cli.py` calls `build_embed_store` after BM25
- No torch, no sentence-transformers, no local GPU required — embedding is a remote HTTP call

## Phase 2 next steps

- Doc chunking for long emails/threads (current: first 2000 chars per doc)
- Multi-vector search (bge-m3 supports sparse + dense + multi-vector colbert mode)
- Embedding the hypothetical paragraph generated during query expansion (already wired in `search_with_expansion`)
