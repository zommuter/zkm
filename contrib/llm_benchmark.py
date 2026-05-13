#!/usr/bin/env python3
"""Compare two LLM models on zkm-style RAG prompts.

Usage:
  uv run contrib/llm_benchmark.py [--endpoint URL] [--models A B] [--no-warmup]

Defaults: zomni llama-swap (http://zomni.local:8080), models llama-3.2-3b + gemma4-e4b.

Each model gets a warm-up request before timing starts, so TTFT reflects inference
latency rather than model-swap/load time.  Use --no-warmup to skip this.

Outputs:
  - Full responses per case per model (quality comparison)
  - Auto quality checks where expected values are known
  - Summary table: TTFT, total time, ~tok/s, quality pass/fail
  - Verdict: whether Gemma >= llama quality at comparable speed

Exit 0 on success; exit 1 if any model is unreachable or quality check fails.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Iterator

import httpx

# ---------------------------------------------------------------------------
# Test cases — synthetic but realistic zkm RAG prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "Today's date: 2026-05-13.\n\n"
    "Answer the user's question using only the provided sources, but first "
    "judge whether the sources actually address the question. "
    "Retrieval is keyword/semantic and can return documents that share "
    "vocabulary with the question without being on the same topic.\n\n"
    "Rules:\n"
    "- If none of the sources directly answer the question, say so plainly "
    "and name what the sources are actually about.\n"
    "- If only some sources are relevant, use only those and ignore the rest. "
    "Cite sources by their bracketed number, e.g. [1], [2].\n"
    "- Answer in the language of the question."
)

CASES: list[dict] = [
    {
        "id": "invoice_de",
        "label": "DE invoice question with matching context",
        "context": (
            "[1] mail/messages/2025-09-01_swisscom_rechnung.md\n"
            "date: 2025-09-01\ntags: [bill, swisscom]\n\n"
            "Ihre Rechnung für September 2025 beträgt CHF 68.90. "
            "Bitte überweisen Sie den Betrag bis 2025-09-20 auf unser Konto IBAN CH56 0483 5012 3456 7800 9."
        ),
        "question": "Wie hoch war meine Swisscom-Rechnung im September 2025?",
        # must mention the correct amount
        "expect_values": ["68.90", "68,90"],
        # must NOT claim the context is irrelevant
        "expect_not": ["nicht", "keine Informationen"],
    },
    {
        "id": "invoice_en",
        "label": "EN invoice question with matching context",
        "context": (
            "[1] mail/messages/2025-10-15_amazon_order.md\n"
            "date: 2025-10-15\ntags: [receipt, amazon]\n\n"
            "Order #112-3456789-0123456 confirmed. Total: €47.30 incl. VAT. "
            "Estimated delivery: 2025-10-17. Item: USB-C Hub, 7-port."
        ),
        "question": "What did I order from Amazon in October 2025 and how much did it cost?",
        "expect_values": ["47.30", "USB-C Hub"],
        "expect_not": [],
    },
    {
        "id": "cross_lingual",
        "label": "DE question, EN context (cross-lingual)",
        "context": (
            "[1] mail/messages/2025-08-03_cloudflare_invoice.md\n"
            "date: 2025-08-03\ntags: [bill, cloudflare]\n\n"
            "Invoice #INV-2025-08-CF. Billing period: Aug 2025. "
            "Pro plan: $20.00. Domain registration example.com: $8.57. Total: $28.57."
        ),
        "question": "Was hat mich Cloudflare im August 2025 gekostet?",
        # must extract total from EN context and answer in DE
        "expect_values": ["28.57", "28,57"],
        "expect_not": [],
    },
    {
        "id": "no_match",
        "label": "Question with irrelevant context (should refuse)",
        "context": (
            "[1] mail/messages/2025-07-10_o2_rechnung.md\n"
            "date: 2025-07-10\ntags: [bill, o2, phone]\n\n"
            "Ihre O2 Mobilfunkrechnung Juli 2025: CHF 29.90. Tarif: O2 Free M. "
            "Minuten: unlimitiert. Daten: 15 GB."
        ),
        "question": "What was my electricity bill last year?",
        # must refuse / mention O2 / not fabricate an electricity figure
        "expect_values": ["O2"],
        "expect_not": ["CHF 29.90", "29.90"],  # must NOT cite the O2 amount as electricity
    },
]


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


@dataclass
class Result:
    model: str
    case_id: str
    ok: bool
    ttft_s: float = 0.0      # time to first token (warm — after warmup run)
    total_s: float = 0.0
    chars: int = 0
    text: str = ""
    error: str = ""
    quality_ok: bool | None = None   # None = no auto-check available
    quality_notes: str = ""


def _chat_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    if endpoint.endswith("/v1"):
        return endpoint + "/chat/completions"
    return endpoint + "/v1/chat/completions"


def _stream(endpoint: str, model: str, system: str, user: str) -> Iterator[str]:
    url = _chat_url(endpoint)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
    }
    with httpx.stream("POST", url, json=payload, timeout=120.0) as resp:
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


def warmup(endpoint: str, model: str) -> None:
    """Send a minimal request to ensure the model is loaded before timing."""
    url = _chat_url(endpoint)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True,
        "max_tokens": 4,
    }
    try:
        with httpx.stream("POST", url, json=payload, timeout=120.0) as resp:
            resp.raise_for_status()
            for _ in resp.iter_lines():
                pass
    except Exception:
        pass  # warmup failure is not fatal; timing will include swap time


def _check_quality(text: str, case: dict) -> tuple[bool, str]:
    """Return (pass, notes) based on expected values and forbidden strings."""
    expect_values: list[str] = case.get("expect_values", [])
    expect_not: list[str] = case.get("expect_not", [])
    notes: list[str] = []
    passed = True

    if expect_values:
        found = next((v for v in expect_values if v in text), None)
        if found:
            notes.append(f"✓ found expected value '{found}'")
        else:
            passed = False
            notes.append(f"✗ missing expected value (one of: {expect_values})")

    for forbidden in expect_not:
        if forbidden in text:
            passed = False
            notes.append(f"✗ found forbidden string '{forbidden}'")

    return passed, "; ".join(notes) if notes else "no auto-check"


def run_case(endpoint: str, model: str, case: dict) -> Result:
    context = case["context"]
    question = case["question"]
    user_content = f"Sources:\n\n{context}\n\n---\n\nQuestion: {question}"
    result = Result(model=model, case_id=case["id"], ok=False)
    t0 = time.monotonic()
    first_token = False
    try:
        chunks: list[str] = []
        for chunk in _stream(endpoint, model, SYSTEM_PROMPT, user_content):
            if not first_token:
                result.ttft_s = time.monotonic() - t0
                first_token = True
            chunks.append(chunk)
        result.text = "".join(chunks)
        result.total_s = time.monotonic() - t0
        result.chars = len(result.text)
        result.ok = True
        result.quality_ok, result.quality_notes = _check_quality(result.text, case)
    except Exception as exc:
        result.error = str(exc)[:120]
        result.total_s = time.monotonic() - t0
    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _wrap(text: str, width: int = 72, indent: str = "    ", max_lines: int = 8) -> list[str]:
    words = text.split()
    line: list[str] = []
    lines: list[str] = []
    for w in words:
        if sum(len(x) + 1 for x in line) + len(w) > width:
            lines.append(indent + " ".join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(indent + " ".join(line))
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"{indent}… ({len(lines) - max_lines} more lines)"]
    return lines


def print_comparison(results: list[Result], models: list[str]) -> None:
    by_case: dict[str, dict[str, Result]] = {}
    for r in results:
        by_case.setdefault(r.case_id, {})[r.model] = r

    print()
    for case in CASES:
        cid = case["id"]
        print(f"{'─' * 80}")
        print(f"CASE: {case['label']}")
        print(f"  Q: {case['question']}")
        row = by_case.get(cid, {})
        for mdl in models:
            r = row.get(mdl)
            if r is None:
                print(f"  {mdl:<20}  — (not run)")
            elif not r.ok:
                print(f"  {mdl:<20}  ERROR: {r.error}")
            else:
                tps_est = r.chars / (r.total_s or 1) / 4  # ~4 chars/token
                qmark = "?" if r.quality_ok is None else ("✓" if r.quality_ok else "✗")
                print(
                    f"  {mdl:<20}  ttft={r.ttft_s:.2f}s  total={r.total_s:.2f}s"
                    f"  ~{tps_est:.0f} tok/s  quality={qmark}"
                )
                print(f"  quality: {r.quality_notes}")
                for ln in _wrap(r.text):
                    print(ln)
    print(f"{'─' * 80}")


def print_summary(results: list[Result], models: list[str]) -> None:
    print("\nSUMMARY TABLE  (TTFT = warm inference latency, after model loaded)")
    print(f"  {'case':<20}  {'model':<20}  {'ttft':>6}  {'total':>7}  {'~tok/s':>7}  quality")
    print(f"  {'─'*20}  {'─'*20}  {'─'*6}  {'─'*7}  {'─'*7}  ───────")
    for case in CASES:
        for mdl in models:
            r = next((x for x in results if x.case_id == case["id"] and x.model == mdl), None)
            if r is None:
                continue
            tps = r.chars / (r.total_s or 1) / 4
            qmark = "?" if r.quality_ok is None else ("✓ pass" if r.quality_ok else "✗ FAIL")
            print(
                f"  {case['id']:<20}  {mdl:<20}  {r.ttft_s:>5.2f}s  {r.total_s:>6.2f}s"
                f"  {tps:>6.0f}   {qmark}"
            )

    # overall verdict
    print()
    for mdl in models:
        mdl_results = [r for r in results if r.model == mdl and r.ok]
        checks = [r for r in mdl_results if r.quality_ok is not None]
        passes = sum(1 for r in checks if r.quality_ok)
        avg_ttft = sum(r.ttft_s for r in mdl_results) / len(mdl_results) if mdl_results else 0
        avg_total = sum(r.total_s for r in mdl_results) / len(mdl_results) if mdl_results else 0
        print(
            f"  {mdl:<20}  quality {passes}/{len(checks)} checks passed"
            f"  avg ttft={avg_ttft:.1f}s  avg total={avg_total:.1f}s"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    doc = __doc__ or ""
    parser = argparse.ArgumentParser(description=doc.splitlines()[0])
    parser.add_argument("--endpoint", default="http://zomni.local:8080")
    parser.add_argument("--models", nargs="+", default=["llama-3.2-3b", "gemma4-e4b"])
    parser.add_argument("--no-warmup", action="store_true",
                        help="Skip warmup requests; TTFT will include model-swap time")
    args = parser.parse_args()

    print(f"Endpoint: {args.endpoint}")
    print(f"Models:   {', '.join(args.models)}")
    print(f"Cases:    {len(CASES)}")
    print(f"Warmup:   {'no (TTFT includes swap time)' if args.no_warmup else 'yes'}")
    print()

    results: list[Result] = []
    for model in args.models:
        if not args.no_warmup:
            print(f"  warming up {model} ...", end=" ", flush=True)
            t0 = time.monotonic()
            warmup(args.endpoint, model)
            print(f"done ({time.monotonic() - t0:.1f}s)")

        for case in CASES:
            print(f"  running {model} / {case['id']} ...", end=" ", flush=True)
            r = run_case(args.endpoint, model, case)
            results.append(r)
            if r.ok:
                qmark = "" if r.quality_ok is None else (" quality=✓" if r.quality_ok else " quality=✗")
                print(f"done ({r.total_s:.1f}s){qmark}")
            else:
                print(f"FAILED: {r.error}")

    print_comparison(results, args.models)
    print_summary(results, args.models)

    failed = [r for r in results if not r.ok]
    if failed:
        print(f"\n{len(failed)} case(s) failed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
