"""Search + LLM context assembly."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import frontmatter
import httpx

from zkm.convert import load_env
from zkm.index import Doc, Index, load_index, tokenize

_DEFAULT_MAX_DOC_CHARS = 500  # ~125 tokens; fits 20 docs inside an 8k-token context
_SNIPPET_WINDOW = 240


@dataclass
class Hit:
    path: str
    score: float
    date: str
    snippet: str


def search(store: Path, query: str, top_k: int = 10) -> list[Hit]:
    idx = load_index(store)
    if idx is None:
        raise FileNotFoundError(
            f"No index found at {store / '.zkm-index'}. Run: zkm index"
        )
    return _search(store, idx, query, top_k)


# ---------------------------------------------------------------------------
# Temporal filtering
# ---------------------------------------------------------------------------


def _temporal_filter(query: str) -> tuple[date, date] | None:
    """Return (start, end) date range if the query has a relative temporal phrase."""
    today = date.today()
    q = query.lower()

    if re.search(r"\blast month\b|\bprevious month\b|\bvorigen monat\b", q):
        first_this = today.replace(day=1)
        end = first_this - timedelta(days=1)
        return end.replace(day=1), end

    if re.search(r"\bthis month\b|\bdiesen monat\b|\bim aktuellen monat\b", q):
        return today.replace(day=1), today

    if re.search(r"\blast week\b|\bprevious week\b|\bvorige woche\b", q):
        # Mon–Sun of the calendar week before this one
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6)

    if re.search(r"\bthis week\b|\bdieser woche\b|\bdiese woche\b", q):
        return today - timedelta(days=today.weekday()), today

    if re.search(r"\blast year\b|\bprevious year\b|\bletztes jahr\b", q):
        y = today.year - 1
        return date(y, 1, 1), date(y, 12, 31)

    if re.search(r"\bthis year\b|\bdieses jahr\b|\bin diesem jahr\b", q):
        return date(today.year, 1, 1), today

    if re.search(r"\byesterday\b|\bgestern\b", q):
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday

    if re.search(r"\btoday\b|\bheute\b", q):
        return today, today

    if re.search(r"\brecent(ly)?\b|\blately\b|\bzuletzt\b|\bjüngst\b", q):
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
# Core search
# ---------------------------------------------------------------------------


def _search(store: Path, idx: Index, query: str, top_k: int) -> list[Hit]:
    import numpy as np

    q_tokens = tokenize(query)
    q_set = set(q_tokens)
    scores = idx.bm25.get_scores(q_tokens) if (q_tokens and idx.bm25 is not None) else None

    date_range = _temporal_filter(query)

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


def _chat_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    if endpoint.endswith("/v1"):
        return endpoint + "/chat/completions"
    return endpoint + "/v1/chat/completions"


def llm_query(
    store: Path,
    question: str,
    top_k: int = 20,
    endpoint: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> Iterator[str]:
    """Search top_k docs and stream an LLM answer with citations."""
    ep, mdl, key = _resolve_llm_config(store, endpoint, model, api_key)
    max_chars = int(os.environ.get("ZKM_LLM_MAX_DOC_CHARS", _DEFAULT_MAX_DOC_CHARS))

    hits = search(store, question, top_k=top_k)

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
            body = resp.read().decode(errors="replace")
            raise httpx.HTTPStatusError(
                f"HTTP {resp.status_code} from {url}: {body[:400]}",
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
