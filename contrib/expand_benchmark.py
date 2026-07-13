#!/usr/bin/env python3
"""Benchmark expand-call latency for zkm query expansion models.

Measures wall-clock time for the expand call (non-streaming LLM keyword extraction)
in warm and cold states. Designed to compare gemma4-e4b vs aya-expanse-8b.

Metrics per model:
  - Load time: llama-swap warm-up (0 if already loaded as always-on)
  - Warm call latency: model ready → expand → response (n=7 by default)
  - Keyword count: avg keywords extracted per call
  - Echo rate: % of calls where any keyword repeats the question verbatim
  - Cold call latency (--cold): expand call when model is not yet loaded

Usage:
  uv run contrib/expand_benchmark.py [--endpoint URL] [--models A B ...]
                                      [--n N] [--cold] [--api-key KEY]

Defaults: zomni llama-swap (http://zomni.local:8080), gemma4-e4b aya-expanse-8b, n=7.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

# Reuse llama-swap helpers from sibling script
sys.path.insert(0, str(Path(__file__).parent))
from llm_benchmark import load_model, warn_contention  # noqa: E402

# Reuse production expand logic (prompt + parsers)
from zkm.expand import (  # noqa: E402
    _EOS_TOKEN_RE,
    _EXPANSION_PROMPT,
    _chat_url,
    _parse_keywords,
)

# ---------------------------------------------------------------------------
# Questions — same bilingual mix as the 2026-05-14 n=7 expand benchmark
# ---------------------------------------------------------------------------

QUESTIONS: list[tuple[str, str]] = [
    ("de", "Wie hoch war meine Swisscom-Rechnung im September?"),
    ("en", "What was my Amazon order total in October?"),
    ("de", "Wann ist das nächste Treffen mit dem Team?"),
    ("en", "Who sent me the contract for the apartment?"),
    ("de", "Wo ist die Quittung für den Laptop?"),
    ("en", "What did I spend on cloud services last year?"),
    ("de", "Hat jemand meine E-Mail zu Cloudflare beantwortet?"),
]

_MODELS_DEFAULT = ["gemma4-e4b", "aya-expanse-8b"]
_EXPAND_TIMEOUT = 60.0
_EXPAND_COLD_TIMEOUT = 180.0


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


@dataclass
class ExpandResult:
    model: str
    lang: str
    question: str
    state: str          # "warm" or "cold"
    elapsed_s: float = 0.0
    keywords: list[str] = field(default_factory=list)
    echoes: list[str] = field(default_factory=list)
    ok: bool = False
    error: str = ""

    @property
    def n_keywords(self) -> int:
        return len(self.keywords)


def _is_echo(kw: str, question: str) -> bool:
    """Return True if keyword is a near-verbatim repeat of the question."""
    kw_l = kw.lower().strip()
    q_l = question.lower().strip()
    # keyword appears verbatim in question (whole-phrase substring)
    if kw_l in q_l:
        return True
    # keyword covers >50% of question (long near-duplicate)
    if len(kw_l) > 10 and len(kw_l) / max(len(q_l), 1) > 0.5:
        return True
    return False


def expand_once(
    endpoint: str,
    model: str,
    lang: str,
    question: str,
    *,
    api_key: str = "",
    state: str = "warm",
) -> ExpandResult:
    """Make one non-streaming expand call; return timing and parsed keywords."""
    timeout = _EXPAND_COLD_TIMEOUT if state == "cold" else _EXPAND_TIMEOUT
    url = _chat_url(endpoint)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _EXPANSION_PROMPT.format(question=question)}],
        "stream": False,
        "max_tokens": 150,
    }

    result = ExpandResult(model=model, lang=lang, question=question, state=state)
    t0 = time.monotonic()
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        raw: str = resp.json()["choices"][0]["message"]["content"] or ""
        result.elapsed_s = time.monotonic() - t0
        raw = _EOS_TOKEN_RE.sub("", raw).strip()
        result.keywords = _parse_keywords(raw)
        result.echoes = [kw for kw in result.keywords if _is_echo(kw, question)]
        result.ok = True
    except Exception as exc:
        result.elapsed_s = time.monotonic() - t0
        result.error = str(exc)[:200]
    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def print_detail(results: list[ExpandResult]) -> None:
    print()
    print("DETAIL")
    print(
        f"  {'model':<22}  {'st':<4}  {'lang':<4}  {'s':>5}  {'kw':>2}  {'echo':>4}"
        f"  question"
    )
    print(
        f"  {'─'*22}  {'─'*4}  {'─'*4}  {'─'*5}  {'─'*2}  {'─'*4}"
        f"  {'─'*42}"
    )
    for r in results:
        if r.ok:
            echo_mark = "!" if r.echoes else " "
            print(
                f"  {r.model:<22}  {r.state:<4}  {r.lang:<4}  {r.elapsed_s:>5.2f}"
                f"  {r.n_keywords:>2}  {echo_mark:>4}  {r.question[:42]!r}"
            )
        else:
            print(
                f"  {r.model:<22}  {r.state:<4}  {r.lang:<4}  ERROR: {r.error[:50]}"
            )


def print_summary(
    results: list[ExpandResult],
    models: list[str],
    load_times: dict[str, float],
) -> None:
    warm_results = {
        mdl: [r for r in results if r.model == mdl and r.state == "warm" and r.ok]
        for mdl in models
    }
    cold_results = {
        mdl: [r for r in results if r.model == mdl and r.state == "cold" and r.ok]
        for mdl in models
    }

    print()
    print("SUMMARY  (load = llama-swap warmup; warm = model already loaded)")
    print(
        f"  {'model':<22}  {'load':>6}  {'warm avg':>8}  {'warm min':>7}  {'warm max':>7}"
        f"  {'kw avg':>6}  {'echo%':>5}"
    )
    print(
        f"  {'─'*22}  {'─'*6}  {'─'*8}  {'─'*7}  {'─'*7}"
        f"  {'─'*6}  {'─'*5}"
    )
    for mdl in models:
        warm = warm_results[mdl]
        if not warm:
            print(f"  {mdl:<22}  — no warm results")
            continue
        avg_s = sum(r.elapsed_s for r in warm) / len(warm)
        min_s = min(r.elapsed_s for r in warm)
        max_s = max(r.elapsed_s for r in warm)
        avg_kw = sum(r.n_keywords for r in warm) / len(warm)
        echo_pct = 100.0 * sum(1 for r in warm if r.echoes) / len(warm)
        load = load_times.get(mdl, 0.0)
        print(
            f"  {mdl:<22}  {load:>5.1f}s  {avg_s:>7.2f}s  {min_s:>6.2f}s  {max_s:>6.2f}s"
            f"  {avg_kw:>5.1f}   {echo_pct:>4.0f}%"
        )

    if any(cold_results[mdl] for mdl in models):
        print()
        print("COLD CALL  (model not preloaded — llama-swap swap triggered by expand request)")
        print(f"  {'model':<22}  {'cold avg':>8}  {'kw avg':>6}")
        print(f"  {'─'*22}  {'─'*8}  {'─'*6}")
        for mdl in models:
            cold = cold_results[mdl]
            if not cold:
                continue
            avg_cold = sum(r.elapsed_s for r in cold) / len(cold)
            avg_kw = sum(r.n_keywords for r in cold) / len(cold)
            print(f"  {mdl:<22}  {avg_cold:>7.2f}s  {avg_kw:>5.1f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--endpoint", default="http://zomni.local:8080")
    parser.add_argument(
        "--models", nargs="+", default=_MODELS_DEFAULT,
        help=f"Models to benchmark (default: {' '.join(_MODELS_DEFAULT)})",
    )
    parser.add_argument(
        "--n", type=int, default=len(QUESTIONS),
        help=f"Questions per model (default: {len(QUESTIONS)})",
    )
    parser.add_argument(
        "--cold", action="store_true",
        help="After warm run, force model cold by loading the next model, then re-measure",
    )
    parser.add_argument("--api-key", default="", dest="api_key")
    args = parser.parse_args()

    endpoint = args.endpoint
    models = args.models
    questions = QUESTIONS[: args.n]

    print(f"Endpoint: {endpoint}")
    print(f"Models ({len(models)}): {', '.join(models)}")
    print(f"Questions: {len(questions)}")
    if args.cold:
        print("Cold measurement: enabled")
    print()

    results: list[ExpandResult] = []
    load_times: dict[str, float] = {}

    for model in models:
        warn_contention(endpoint, model)
        load_s = load_model(endpoint, model)
        load_times[model] = load_s

        print(f"  warm run: {model} × {len(questions)} questions")
        for lang, q in questions:
            print(f"    [{lang}] {q[:50]!r:<53}", end=" ", flush=True)
            r = expand_once(endpoint, model, lang, q, api_key=args.api_key, state="warm")
            results.append(r)
            if r.ok:
                echo_note = f"  echo: {r.echoes}" if r.echoes else ""
                print(f"→ {r.elapsed_s:.2f}s  {r.n_keywords}kw{echo_note}")
            else:
                print(f"→ ERROR: {r.error[:60]}")
        print()

    if args.cold and len(models) >= 2:
        print("Cold run (alternating model load to force swap) ...")
        for i, model in enumerate(models):
            evict_by = models[(i + 1) % len(models)]
            print(f"  loading {evict_by!r} to evict {model!r} ...")
            load_model(endpoint, evict_by)
            lang, q = questions[i % len(questions)]
            print(f"  cold expand {model!r} / {q[:45]!r:<48}", end=" ", flush=True)
            r = expand_once(
                endpoint, model, lang, q, api_key=args.api_key, state="cold"
            )
            results.append(r)
            if r.ok:
                print(f"→ {r.elapsed_s:.2f}s  {r.n_keywords}kw")
            else:
                print(f"→ ERROR: {r.error[:60]}")
        print()

    print_detail(results)
    print_summary(results, models, load_times)
    return 0


if __name__ == "__main__":
    sys.exit(main())
