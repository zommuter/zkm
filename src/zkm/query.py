"""Search + LLM context assembly."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import frontmatter
import httpx

from zkm.convert import load_env
from zkm.embed import (
    EmbedStore,
    EmbedUnavailable,
    embed_texts,
    load_embed_store,
    resolve_embed_config,
)
from zkm.index import Doc, Index, load_index, tokenize

_DEFAULT_MAX_DOC_CHARS = 500  # ~125 tokens; fits 20 docs inside an 8k-token context
_SNIPPET_WINDOW = 240
_DENSE_POOL_MULT = 20      # WHY: 3× saturates on corpora with large literal-match clusters
_DENSE_POOL_FLOOR = 200    # minimum to clear typical literal-match cluster


@dataclass
class Hit:
    path: str
    score: float
    date: str
    snippet: str


@dataclass
class SearchTrace:
    bm25_hits: int
    dense_hits: int
    dense_skipped_reason: str | None  # "no_embed_store" | "no_endpoint" | "embed_failed" | None
    expanded: bool
    keywords: list[str] = field(default_factory=list)
    hyp_text: str = ""


def search(store: Path, query: str, top_k: int = 10) -> list[Hit]:
    idx = load_index(store)
    if idx is None:
        raise FileNotFoundError(
            f"No index found at {store / '.zkm-index'}. Run: zkm index"
        )
    return _search(store, idx, tokenize(query), _temporal_filter(query), top_k)


# ---------------------------------------------------------------------------
# Temporal filtering
# ---------------------------------------------------------------------------


def _temporal_filter(query: str) -> tuple[date, date] | None:
    """Return (start, end) date range if the query has a relative temporal phrase."""
    today = date.today()
    q = query.lower()

    if re.search(
        r"\blast month\b|\bprevious month\b"
        r"|\b(vorigen|letzten|letztem|vergangenen)\s+monat\b",
        q,
    ):
        first_this = today.replace(day=1)
        end = first_this - timedelta(days=1)
        return end.replace(day=1), end

    if re.search(
        r"\bthis month\b|\b(diesen|diesem|dieses|laufenden|aktuellen)\s+monat\b",
        q,
    ):
        return today.replace(day=1), today

    if re.search(
        r"\blast week\b|\bprevious week\b"
        r"|\b(vorige|letzte|letzten|letzter)\s+woche\b",
        q,
    ):
        # Mon–Sun of the calendar week before this one
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6)

    if re.search(r"\bthis week\b|\b(dieser|diese|diesem)\s+woche\b", q):
        return today - timedelta(days=today.weekday()), today

    if re.search(
        r"\blast year\b|\bprevious year\b"
        r"|\b(letztes|letzten|letztem|vergangenen|vergangenes)\s+jahr\b",
        q,
    ):
        y = today.year - 1
        return date(y, 1, 1), date(y, 12, 31)

    if re.search(r"\bthis year\b|\b(dieses|diesen|diesem)\s+jahr\b|\bin diesem jahr\b", q):
        return date(today.year, 1, 1), today

    if re.search(r"\byesterday\b|\bgestern\b", q):
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday

    if re.search(r"\btoday\b|\bheute\b", q):
        return today, today

    if re.search(
        r"\brecent(ly)?\b|\blately\b|\bzuletzt\b|\bjüngst\b|\bkürzlich\b|\bneulich\b"
        r"|\bin letzter zeit\b",
        q,
    ):
        return today - timedelta(days=30), today

    return None


def _parse_doc_date(doc: Doc) -> date | None:
    val = doc.metadata.get("date")
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        try:
            return date.fromisoformat(val[:10])
        except ValueError:
            pass
    return None


def _doc_in_range(doc: Doc, start: date, end: date) -> bool:
    d = _parse_doc_date(doc)
    return d is not None and start <= d <= end


# ---------------------------------------------------------------------------
# Core search — takes pre-tokenized query tokens and pre-computed date_range
# ---------------------------------------------------------------------------


def _search(
    store: Path,
    idx: Index,
    q_tokens: list[str],
    date_range: tuple[date, date] | None,
    top_k: int,
) -> list[Hit]:
    import numpy as np

    q_set = set(q_tokens)
    scores = idx.bm25.get_scores(q_tokens) if (q_tokens and idx.bm25 is not None) else None

    if date_range:
        start, end = date_range
        candidates = [i for i, doc in enumerate(idx.docs) if _doc_in_range(doc, start, end)]

        if not candidates:
            # Nothing in the date window — fall back to full corpus
            candidates = list(range(len(idx.docs)))

        def _sort_key(i: int) -> tuple:
            has_match = bool(q_set and q_set.intersection(idx.docs[i].tokens))
            sc = float(scores[i]) if scores is not None else 0.0
            d = _parse_doc_date(idx.docs[i]) or date.min
            # BM25-matching docs first; within each group, most recent first
            return (not has_match, -d.toordinal(), -sc)

        candidates.sort(key=_sort_key)
        selected = candidates[:top_k]
    else:
        if not q_tokens or idx.bm25 is None:
            return []
        assert scores is not None
        order = np.argsort(scores)[::-1]
        # Keep docs that share at least one token (or stem) with the query.
        # BM25Okapi IDF can be 0 for terms in half the corpus, so score > 0 is
        # not a reliable non-match signal in small corpora. Token intersection is.
        # With bilingual stemming, inflection mismatches are resolved here;
        # cross-language gaps are handled by search_with_expansion() instead.
        selected = [
            int(i) for i in order
            if q_set.intersection(idx.docs[int(i)].tokens)
        ][:top_k]

    hits: list[Hit] = []
    for i in selected:
        doc = idx.docs[i]
        sc = float(scores[i]) if scores is not None else 0.0
        snippet = _make_snippet(store / doc.rel_path, list(q_set))
        hits.append(Hit(
            path=doc.rel_path,
            score=sc,
            date=str(doc.metadata.get("date", "")),
            snippet=snippet,
        ))
    return hits


def _make_snippet(path: Path, q_tokens: list[str]) -> str:
    try:
        post = frontmatter.load(path)
        body = post.content
    except Exception:
        return ""

    lower = body.lower()
    best_pos = -1
    for tok in q_tokens:
        pos = lower.find(tok)
        if pos != -1:
            best_pos = pos
            break

    if best_pos == -1:
        return body[:_SNIPPET_WINDOW].replace("\n", " ").strip()

    start = max(0, best_pos - 60)
    end = min(len(body), start + _SNIPPET_WINDOW)
    snippet = body[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(body):
        snippet = snippet + "…"
    return snippet


# ---------------------------------------------------------------------------
# Multi-query search: RRF merge + LLM expansion wiring
# ---------------------------------------------------------------------------


def rrf_merge(hit_lists: list[list[Hit]], k: int = 60) -> list[Hit]:
    """Reciprocal rank fusion of multiple BM25 result lists.

    score(d) = Σ 1 / (k + rank_i(d)) across all lists that contain d.
    """
    rrf_scores: dict[str, float] = {}
    best: dict[str, Hit] = {}
    for hits in hit_lists:
        for rank, hit in enumerate(hits):
            rrf_scores[hit.path] = rrf_scores.get(hit.path, 0.0) + 1.0 / (k + rank + 1)
            if hit.path not in best or hit.score > best[hit.path].score:
                best[hit.path] = hit
    ranked = sorted(rrf_scores, key=lambda p: rrf_scores[p], reverse=True)
    return [best[p] for p in ranked]


def _dense_search(
    store: Path,
    es: EmbedStore,
    texts: list[str],
    date_range: tuple[date, date] | None,
    top_k: int,
    pool: int,
    endpoint: str,
    model: str,
    api_key: str,
) -> list[Hit]:
    """Embed texts, query the EmbedStore, apply temporal filter, return top_k Hits.

    Raises EmbedUnavailable when the embedding request fails — caller decides how to handle.
    """
    vecs = embed_texts(texts, endpoint, model, api_key)
    # Average the query vectors (handles both single query and question+hypothetical)
    q_vec = vecs.mean(axis=0).astype("float32")
    norm = float(q_vec @ q_vec) ** 0.5
    if norm > 0:
        q_vec = q_vec / norm

    results = es.topk(q_vec, min(pool, len(es.paths)))

    hits: list[Hit] = []
    for row_idx, score in results:
        rel_path = es.paths[row_idx]
        doc_meta: dict = {}
        try:
            post = frontmatter.load(store / rel_path)
            doc_meta = dict(post.metadata)
        except Exception:
            pass

        if date_range is not None:
            doc_date = _parse_doc_date_from_meta(doc_meta)
            start, end = date_range
            if doc_date is None or not (start <= doc_date <= end):
                continue

        doc_date_str = str(doc_meta.get("date", ""))
        snippet = _make_snippet(store / rel_path, [])
        hits.append(Hit(path=rel_path, score=score, date=doc_date_str, snippet=snippet))
        if len(hits) >= top_k:
            break

    return hits


def _parse_doc_date_from_meta(meta: dict) -> date | None:
    """Like _parse_doc_date but from a dict instead of a Doc."""
    val = meta.get("date")
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        try:
            return date.fromisoformat(val[:10])
        except ValueError:
            pass
    return None


def search_hybrid_traced(
    store: Path,
    query: str,
    top_k: int = 10,
    *,
    dense: bool = True,
) -> tuple[list[Hit], SearchTrace]:
    """BM25 + dense hybrid search; returns results and a diagnostic trace.

    Falls back to pure BM25 when dense=False, EmbedStore missing, endpoint
    unconfigured, or embed request fails. Trace records which path was taken.
    """
    idx = load_index(store)
    if idx is None:
        raise FileNotFoundError(
            f"No index found at {store / '.zkm-index'}. Run: zkm index"
        )
    date_range = _temporal_filter(query)

    if not dense:
        hits = _search(store, idx, tokenize(query), date_range, top_k)
        return hits, SearchTrace(len(hits), 0, None, False)

    pool = max(top_k * _DENSE_POOL_MULT, _DENSE_POOL_FLOOR)
    bm25_hits = _search(store, idx, tokenize(query), date_range, pool)

    es = load_embed_store(store)
    if es is None:
        return bm25_hits[:top_k], SearchTrace(len(bm25_hits), 0, "no_embed_store", False)

    ep, mdl, key = resolve_embed_config(store)
    if not ep:
        return bm25_hits[:top_k], SearchTrace(len(bm25_hits), 0, "no_endpoint", False)

    try:
        dense_hits = _dense_search(store, es, [query], date_range, top_k, pool, ep, mdl, key)
    except EmbedUnavailable:
        return bm25_hits[:top_k], SearchTrace(len(bm25_hits), 0, "embed_failed", False)

    if not dense_hits:
        return bm25_hits[:top_k], SearchTrace(len(bm25_hits), 0, None, False)

    merged = rrf_merge([bm25_hits, dense_hits])[:top_k]
    return merged, SearchTrace(len(bm25_hits), len(dense_hits), None, False)


def search_hybrid(
    store: Path,
    query: str,
    top_k: int = 10,
    *,
    dense: bool = True,
) -> list[Hit]:
    """BM25 search with optional dense leg (no LLM expansion)."""
    hits, _ = search_hybrid_traced(store, query, top_k, dense=dense)
    return hits


def search_with_expansion_traced(
    store: Path,
    question: str,
    top_k: int = 20,
    endpoint: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    *,
    dense: bool = True,
) -> tuple[list[Hit], SearchTrace]:
    """Multi-query BM25 + LLM expansion + optional dense, with diagnostic trace."""
    idx = load_index(store)
    if idx is None:
        raise FileNotFoundError(
            f"No index found at {store / '.zkm-index'}. Run: zkm index"
        )
    ep, mdl, key = _resolve_expand_config(store)
    if endpoint:
        ep = endpoint
    if model:
        mdl = model
    if api_key:
        key = api_key
    date_range = _temporal_filter(question)

    from zkm.expand import expand_query_with_hyp  # lazy import avoids circular dependency

    variant_lists, hyp_text, keywords = expand_query_with_hyp(question, store, ep, mdl, key)

    if not dense:
        hit_lists = [_search(store, idx, tokens, date_range, top_k) for tokens in variant_lists]
        hits = rrf_merge(hit_lists)[:top_k]
        return hits, SearchTrace(len(hits), 0, None, True, keywords, hyp_text)

    pool = max(top_k * _DENSE_POOL_MULT, _DENSE_POOL_FLOOR)
    hit_lists = [_search(store, idx, tokens, date_range, pool) for tokens in variant_lists]
    bm25_rrf_hits = rrf_merge(hit_lists)

    es = load_embed_store(store)
    if es is None:
        return bm25_rrf_hits[:top_k], SearchTrace(len(bm25_rrf_hits), 0, "no_embed_store", True, keywords, hyp_text)

    e_ep, e_mdl, e_key = resolve_embed_config(store)
    if not e_ep:
        return bm25_rrf_hits[:top_k], SearchTrace(len(bm25_rrf_hits), 0, "no_endpoint", True, keywords, hyp_text)

    embed_texts_input = [question]
    if hyp_text:
        embed_texts_input.append(hyp_text)

    try:
        dense_hits = _dense_search(
            store, es, embed_texts_input, date_range, top_k, pool, e_ep, e_mdl, e_key
        )
    except EmbedUnavailable:
        return bm25_rrf_hits[:top_k], SearchTrace(len(bm25_rrf_hits), 0, "embed_failed", True, keywords, hyp_text)

    if not dense_hits:
        return bm25_rrf_hits[:top_k], SearchTrace(len(bm25_rrf_hits), 0, None, True, keywords, hyp_text)

    merged = rrf_merge([bm25_rrf_hits, dense_hits])[:top_k]
    return merged, SearchTrace(len(bm25_rrf_hits), len(dense_hits), None, True, keywords, hyp_text)


def search_with_expansion(
    store: Path,
    question: str,
    top_k: int = 20,
    endpoint: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    *,
    dense: bool = True,
) -> list[Hit]:
    """Multi-query BM25 with LLM query expansion merged via RRF, plus optional dense leg."""
    hits, _ = search_with_expansion_traced(
        store, question, top_k, endpoint, model, api_key, dense=dense
    )
    return hits


# ---------------------------------------------------------------------------
# LLM query
# ---------------------------------------------------------------------------

_DEFAULT_ENDPOINT = "http://localhost:8080"
_DEFAULT_MODEL = "qwen3.5-0.8b"


def _resolve_llm_config(
    store: Path,
    endpoint: str | None,
    model: str | None,
    api_key: str | None,
) -> tuple[str, str, str]:
    env = load_env(store)

    def _get(key: str, override: str | None, default: str) -> str:
        if override:
            return override
        if key in os.environ:
            return os.environ[key]
        if key in env:
            return env[key]
        return default

    resolved_endpoint = _get("ZKM_LLM_ENDPOINT", endpoint, _DEFAULT_ENDPOINT)
    resolved_model = _get("ZKM_LLM_MODEL", model, _DEFAULT_MODEL)
    resolved_key = _get("ZKM_LLM_KEY", api_key, "")
    return resolved_endpoint, resolved_model, resolved_key


def _resolve_expand_config(store: Path) -> tuple[str, str, str]:
    """Resolve expansion-model config, falling back to main LLM config.

    ZKM_LLM_EXPAND_ENDPOINT / ZKM_LLM_EXPAND_MODEL / ZKM_LLM_EXPAND_KEY override
    the main LLM settings so a bilingual-capable model can be used for keyword
    extraction while a smaller model handles the RAG answer.
    """
    main_ep, main_mdl, main_key = _resolve_llm_config(store, None, None, None)
    env = load_env(store)

    def _get(key: str, fallback: str) -> str:
        if key in os.environ:
            return os.environ[key]
        if key in env:
            return env[key]
        return fallback

    ep = _get("ZKM_LLM_EXPAND_ENDPOINT", main_ep)
    mdl = _get("ZKM_LLM_EXPAND_MODEL", main_mdl)
    key = _get("ZKM_LLM_EXPAND_KEY", main_key)
    return ep, mdl, key


def _chat_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    if endpoint.endswith("/v1"):
        return endpoint + "/chat/completions"
    return endpoint + "/v1/chat/completions"


def llm_stream(
    store: Path,
    hits: list[Hit],
    question: str,
    endpoint: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> Iterator[str]:
    """Stream an LLM answer for pre-retrieved hits."""
    ep, mdl, key = _resolve_llm_config(store, endpoint, model, api_key)
    max_chars = int(os.environ.get("ZKM_LLM_MAX_DOC_CHARS", _DEFAULT_MAX_DOC_CHARS))

    context_blocks: list[str] = []
    for i, hit in enumerate(hits, 1):
        try:
            post = frontmatter.load(store / hit.path)
            body = post.content[:max_chars]
        except Exception:
            body = hit.snippet
        context_blocks.append(f"[{i}] {hit.path}\n{body}")

    if context_blocks:
        context_text = "\n\n---\n\n".join(context_blocks)
        user_content = f"Sources:\n\n{context_text}\n\n---\n\nQuestion: {question}"
    else:
        user_content = f"Question: {question}"

    messages = [
        {
            "role": "system",
            "content": (
                f"Today's date: {date.today().isoformat()}. "
                "Answer the user's question using only the provided sources. "
                "Cite sources by their path in square brackets, e.g. [notes/foo.md]."
            ),
        },
        {"role": "user", "content": user_content},
    ]

    url = _chat_url(ep)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {"model": mdl, "messages": messages, "stream": True}

    with httpx.stream(
        "POST", url, headers=headers, json=payload, timeout=120.0
    ) as resp:
        if resp.status_code >= 400:
            body_text = resp.read().decode(errors="replace")
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code} from {url}: {body_text[:400]}",
                request=resp.request,
                response=resp,
            )
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                content = chunk["choices"][0]["delta"].get("content")
                if content:
                    yield content
            except (KeyError, json.JSONDecodeError):
                continue


def llm_query(
    store: Path,
    question: str,
    top_k: int = 20,
    endpoint: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    expand: bool = True,
    dense: bool = True,
) -> Iterator[str]:
    """Search top_k docs and stream an LLM answer with citations.

    expand=True (default): LLM query expansion + RRF.
    dense=True (default): also runs dense retrieval and fuses with RRF.
    expand=False + dense=False: falls back to plain BM25.
    """
    if expand:
        hits = search_with_expansion(store, question, top_k, endpoint, model, api_key, dense=dense)
    elif dense:
        hits = search_hybrid(store, question, top_k, dense=True)
    else:
        hits = search(store, question, top_k=top_k)
    return llm_stream(store, hits, question, endpoint=endpoint, model=model, api_key=api_key)
