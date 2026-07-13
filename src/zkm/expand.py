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

_EXPAND_TIMEOUT_DEFAULT = 30.0       # warm model; override ZKM_LLM_EXPAND_TIMEOUT
_EXPAND_COLD_TIMEOUT_DEFAULT = 180.0  # cold model loading; override ZKM_LLM_EXPAND_COLD_TIMEOUT
_MAX_TOKENS = 150
_CACHE_FILE = ".zkm-index/expansion-cache.json"

_EXPANSION_PROMPT = (
    "The user question may be in English or German. The document corpus contains BOTH languages.\n"
    "Output Section 1, then a blank line, then Section 2.\n\n"
    "Section 1 — Search terms: produce keyword phrases in BOTH languages, one per line, "
    "no blank lines, no bullets, no markdown. Each phrase must be ≤4 words. "
    "Output 3 English phrases, then 3 German phrases. "
    "Translate the question's main concepts into the OTHER language. Do not repeat phrases. "
    "Do NOT echo the question verbatim or as a near-verbatim substring — "
    "every phrase must be a paraphrase, synonym, or related concept, never the question itself.\n\n"
    "Section 2 — Hypothetical answer: one sentence that would be a plausible answer, "
    "in either language.\n\n"
    "Question: {question}"
)
# WHY: cache keys include a prompt hash so stale entries are ignored when the prompt changes
_PROMPT_HASH = hashlib.sha256(_EXPANSION_PROMPT.encode()).hexdigest()[:8]
# Bump whenever _parse_keywords / _parse_hypothetical semantics change so cached entries
# written by the old parser become unreachable and the file is rewritten clean.
_PARSER_VERSION = "v2"

# Matches "Section 2" with optional leading markdown heading markers (## Section 2, etc.)
_SEC2_RE = re.compile(r"\n#*\s*Section\s*2\b", re.IGNORECASE)
# Leaked end-of-turn tokens from some models (e.g. aya-expanse via llama-server)
_EOS_TOKEN_RE = re.compile(r"<\|[A-Z_]+_TOKEN\|>")


def _probe_model_loaded(endpoint: str, model: str, *, timeout: float = 2.0) -> bool | None:
    """Check whether `model` is currently loaded in a llama-swap instance.

    Returns True if loaded, False if confirmed absent, None on any error or
    if the endpoint is not a llama-swap instance (no /running route).
    """
    try:
        resp = httpx.get(endpoint.rstrip("/") + "/running", timeout=timeout)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        raw = json.dumps(resp.json())
        return model in raw
    except Exception:
        return None


def _chat_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    if endpoint.endswith("/v1"):
        return endpoint + "/chat/completions"
    return endpoint + "/v1/chat/completions"


def _parse_keywords(text: str) -> list[str]:
    """Extract keyword phrases from section 1 of LLM output.

    Handles both the expected one-per-line format and the inline format where the
    model puts all keywords on the same line as the section header (comma- or
    space-quote-separated). Section 1 ends at the first blank line or Section 2 marker.
    """
    keywords: list[str] = []
    # Isolate section 1.
    # Prefer the explicit "Section 2" marker (with optional leading ## for markdown models);
    # fall back to the first blank line for models that omit the Section 2 label.
    m = _SEC2_RE.search(text)
    section1 = text[: m.start()] if m else re.split(r"\n\s*\n", text, maxsplit=1)[0]
    for line in section1.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip markdown sub-headers: **English:**, **German:**, ## Section 1, ## alone, etc.
        if re.match(r"^#|^\*{2}[A-Za-z]", line):
            continue
        # Strip "Section N — Label:" prefix (colon optional — aya sometimes omits it)
        line = re.sub(
            r"^Section\s*\d+\s*[—–\-]+\s*[^:]+:?\s*", "", line, flags=re.IGNORECASE
        ).strip()
        if not line:
            continue
        # Strip leading list markers: "1.", "1)", "-", "*", "•"
        line = re.sub(r"^[\d]+[.)]\s*|^[-*•]\s*", "", line).strip()
        if not line:
            continue
        # If line looks like inline list (commas, or ≥4 quoted terms), split it
        if "," in line or line.count('"') >= 4:
            parts = re.split(r',\s*|(?<=["”])\s+(?=["“"])', line)
        else:
            parts = [line]
        for part in parts:
            part = re.sub(r'^["""\'\'\']+|["""\'\'\']+$', "", part).strip()
            part = re.sub(r"[^\w\s''\-]", "", part, flags=re.UNICODE).strip()
            if part and len(part) >= 2 and len(part.split()) <= 5:
                keywords.append(part)
    return keywords[:12]


def _parse_hypothetical_text(text: str) -> str:
    """Return the raw hypothetical-answer section, stripped of any section label.

    Splits on a blank line (expected format) or a 'Section 2' marker on a new line
    (model sometimes omits the blank line). Strips any remaining 'Section 2 — …:'
    label from the extracted text.
    """
    parts = re.split(r"\n\s*\n", text, maxsplit=1)
    if len(parts) >= 2:
        hyp = parts[1].strip()
    else:
        # No blank line — try splitting on the Section 2 marker itself
        parts = re.split(r"\nSection\s*2\b[^:]*:\s*", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) >= 2:
            return parts[1].strip()
        return ""
    # Strip leading "Section 2 — Hypothetical answer:" label if the model included it
    hyp = re.sub(r"^Section\s*2\s*[—–\-]+\s*[^:]+:\s*", "", hyp, flags=re.IGNORECASE).strip()
    return hyp


def _parse_hypothetical(text: str) -> list[str]:
    """Tokenize the hypothetical-answer section of LLM output."""
    return tokenize(_parse_hypothetical_text(text))


def _cache_path(store: Path) -> Path:
    return store / _CACHE_FILE


def _load_cache(store: Path) -> dict:
    p = _cache_path(store)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("_parser_version") != _PARSER_VERSION:
            return {}
        return data.get("entries", {})
    except Exception:
        return {}


def _save_cache(store: Path, cache: dict) -> None:
    p = _cache_path(store)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        envelope = {"_parser_version": _PARSER_VERSION, "entries": cache}
        p.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def expand_query_with_hyp(
    question: str,
    store: Path,
    endpoint: str,
    model: str,
    api_key: str,
) -> tuple[list[list[str]], str, list[str], str | None]:
    """Return (token_lists, hyp_text, keywords, reason) for multi-BM25 + dense retrieval.

    token_lists: first entry is always tokenize(question); subsequent entries are
    LLM keyword variants + hypothetical-answer tokens (for BM25).
    hyp_text: raw hypothetical-answer paragraph (for dense embedding).
    keywords: LLM-generated keyword strings (for display/debugging).
    reason: None on success; "timeout" | "endpoint_error" | "parse_error" on failure.
    Falls back to ([tokenize(question)], "", [], reason) on any LLM error.
    """
    raw_tokens = tokenize(question)
    _fallback_tokens: list[list[str]] = [raw_tokens]

    cache_key = hashlib.sha256(
        (_PARSER_VERSION + _PROMPT_HASH + model + question).encode()
    ).hexdigest()[:24]
    cache = _load_cache(store)
    if cache_key in cache:
        entry = cache[cache_key]
        keywords: list[str] = entry.get("keywords", [])
        hyp_tokens: list[str] = entry.get("hyp_tokens", [])
        hyp_text: str = entry.get("hyp_text", "")
        result = [raw_tokens] + [t for kw in keywords if (t := tokenize(kw))]
        if hyp_tokens:
            result.append(hyp_tokens)
        return (result if len(result) > 1 else [raw_tokens]), hyp_text, keywords, None

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

    import os

    from zkm.config import load_config
    cfg = load_config(store)
    warm_timeout = float(
        os.environ.get("ZKM_LLM_EXPAND_TIMEOUT")
        or cfg.core_value("expand", "timeout")
        or _EXPAND_TIMEOUT_DEFAULT
    )
    cold_timeout = float(
        os.environ.get("ZKM_LLM_EXPAND_COLD_TIMEOUT")
        or cfg.core_value("expand", "cold_timeout")
        or _EXPAND_COLD_TIMEOUT_DEFAULT
    )

    loaded = _probe_model_loaded(endpoint, model)
    if loaded is False:
        timeout = cold_timeout
        print(
            f"zkm: expand model '{model}' not loaded — warming up (allowing {timeout:.0f}s)",
            file=sys.stderr,
        )
    else:
        timeout = warm_timeout

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        raw_output: str = resp.json()["choices"][0]["message"]["content"] or ""
        raw_output = _EOS_TOKEN_RE.sub("", raw_output).strip()
    except httpx.TimeoutException as exc:
        print(f"zkm: query expansion timed out ({str(exc)[:80]}), using raw query", file=sys.stderr)
        return _fallback_tokens, "", [], "timeout"
    except httpx.HTTPError as exc:
        print(f"zkm: query expansion failed ({str(exc)[:80]}), using raw query", file=sys.stderr)
        return _fallback_tokens, "", [], "endpoint_error"
    except Exception as exc:
        print(f"zkm: query expansion failed ({str(exc)[:80]}), using raw query", file=sys.stderr)
        return _fallback_tokens, "", [], "endpoint_error"

    keywords = _parse_keywords(raw_output)
    hyp_tokens = _parse_hypothetical(raw_output)
    hyp_text = _parse_hypothetical_text(raw_output)

    cache[cache_key] = {
        "question": question,
        "keywords": keywords,
        "hyp_tokens": hyp_tokens,
        "hyp_text": hyp_text,
    }
    _save_cache(store, cache)

    if not keywords and not hyp_tokens:
        return _fallback_tokens, "", [], "parse_error"

    result = [raw_tokens] + [t for kw in keywords if (t := tokenize(kw))]
    if hyp_tokens:
        result.append(hyp_tokens)
    return result, hyp_text, keywords, None


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
    variants, *_ = expand_query_with_hyp(question, store, endpoint, model, api_key)
    return variants
