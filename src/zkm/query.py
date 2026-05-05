"""Search + LLM context assembly."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import frontmatter
import httpx

from zkm.convert import load_env
from zkm.index import Index, load_index, tokenize

_DEFAULT_MAX_DOC_CHARS = 4000
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


def _search(store: Path, idx: Index, query: str, top_k: int) -> list[Hit]:
    q_tokens = tokenize(query)
    if not q_tokens or idx.bm25 is None:
        return []

    import numpy as np

    scores = idx.bm25.get_scores(q_tokens)
    q_set = set(q_tokens)
    order = np.argsort(scores)[::-1]

    hits: list[Hit] = []
    for i in order:
        if len(hits) >= top_k:
            break
        doc = idx.docs[i]
        if not q_set.intersection(doc.tokens):
            continue
        date = str(doc.metadata.get("date", ""))
        path = store / doc.rel_path
        snippet = _make_snippet(path, q_tokens)
        hits.append(Hit(path=doc.rel_path, score=float(scores[i]), date=date, snippet=snippet))

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


def _resolve_llm_config(
    store: Path,
    endpoint: str | None,
    model: str | None,
    api_key: str | None,
) -> tuple[str, str, str]:
    env = load_env(store)

    def _get(key: str, override: str | None) -> str:
        if override:
            return override
        if key in os.environ:
            return os.environ[key]
        if key in env:
            return env[key]
        raise ValueError(
            f"Missing required LLM config: {key}\n"
            f"Set it in the environment or add it to {store / '.env'}"
        )

    resolved_endpoint = _get("ZKM_LLM_ENDPOINT", endpoint)
    resolved_model = _get("ZKM_LLM_MODEL", model)
    resolved_key = _get("ZKM_LLM_KEY", api_key)
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
    top_k: int = 5,
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
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": mdl, "messages": messages, "stream": True}

    with httpx.stream(
        "POST", url, headers=headers, json=payload, timeout=120.0
    ) as resp:
        resp.raise_for_status()
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
