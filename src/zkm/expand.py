"""LLM-driven query expansion for multi-BM25 retrieval (RAG-Fusion + Query2Doc lite).

Flow: one non-streaming LLM call extracts keyword variants and a hypothetical answer
paragraph → each variant is tokenized → BM25 is run per variant → caller merges with RRF.
Falls back to raw query tokens on any LLM error.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import httpx

from zkm.index import tokenize

_EXPAND_TIMEOUT = 8.0
_MAX_TOKENS = 150
_CACHE_FILE = ".zkm-index/expansion-cache.json"

_EXPANSION_PROMPT = (
    "Given this question, output two sections separated by a blank line.\n\n"
    "Section 1 — Search terms: list 3-5 short keyword phrases, one per line, "
    "in the language(s) most likely used in the source documents "
    "(user has both English and German documents).\n"
    "Section 2 — Hypothetical answer: one sentence that would be a plausible direct answer, "
    "using vocabulary likely to appear in the documents.\n\n"
    "Question: {question}"
)


def _chat_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    if endpoint.endswith("/v1"):
        return endpoint + "/chat/completions"
    return endpoint + "/v1/chat/completions"


def _parse_keywords(text: str) -> list[str]:
    """Extract short keyword lines from section 1 of LLM output (before first blank line)."""
    keywords: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            break  # first blank line ends section 1
        # Strip leading list markers: "1.", "1)", "-", "*", "•"
        line = re.sub(r"^[\d]+[.)]\s*|^[-*•]\s*", "", line).strip()
        if not line or len(line.split()) > 5:
            continue  # skip prose lines
        cleaned = re.sub(r"[^\w\s'''\-]", "", line, flags=re.UNICODE).strip()
        if cleaned and len(cleaned) >= 2:
            keywords.append(cleaned)
    return keywords[:5]


def _parse_hypothetical(text: str) -> list[str]:
    """Tokenize the hypothetical-answer section (after first blank line in LLM output)."""
    parts = re.split(r"\n\s*\n", text, maxsplit=1)
    if len(parts) < 2:
        return []
    return tokenize(parts[1])


def _cache_path(store: Path) -> Path:
    return store / _CACHE_FILE


def _load_cache(store: Path) -> dict:
    p = _cache_path(store)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(store: Path, cache: dict) -> None:
    p = _cache_path(store)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def expand_query(
    question: str,
    store: Path,
    endpoint: str,
    model: str,
    api_key: str,
) -> list[list[str]]:
    """Return token lists for multi-BM25 retrieval.

    First entry is always tokenize(question) as the baseline.
    Subsequent entries are LLM-generated keyword variants + hypothetical-answer tokens.
    Falls back to [tokenize(question)] on any LLM error or empty output.
    """
    raw_tokens = tokenize(question)
    fallback: list[list[str]] = [raw_tokens]

    cache_key = hashlib.sha256(question.encode()).hexdigest()[:24]
    cache = _load_cache(store)
    if cache_key in cache:
        entry = cache[cache_key]
        keywords: list[str] = entry.get("keywords", [])
        hyp_tokens: list[str] = entry.get("hyp_tokens", [])
        result = [raw_tokens] + [t for kw in keywords if (t := tokenize(kw))]
        if hyp_tokens:
            result.append(hyp_tokens)
        return result if len(result) > 1 else fallback

    url = _chat_url(endpoint)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _EXPANSION_PROMPT.format(question=question)}],
        "stream": False,
        "max_tokens": _MAX_TOKENS,
    }

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=_EXPAND_TIMEOUT)
        resp.raise_for_status()
        raw_output: str = resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"zkm: query expansion failed ({str(exc)[:80]}), using raw query", file=sys.stderr)
        return fallback

    keywords = _parse_keywords(raw_output)
    hyp_tokens = _parse_hypothetical(raw_output)

    cache[cache_key] = {"question": question, "keywords": keywords, "hyp_tokens": hyp_tokens}
    _save_cache(store, cache)

    if not keywords and not hyp_tokens:
        return fallback

    result = [raw_tokens] + [t for kw in keywords if (t := tokenize(kw))]
    if hyp_tokens:
        result.append(hyp_tokens)
    return result
