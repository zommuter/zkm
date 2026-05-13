#!/usr/bin/env python3
"""Benchmark all llama-swap models on zkm-style RAG prompts.

Usage:
  uv run contrib/llm_benchmark.py [--endpoint URL] [--models A B ...] [--exclude A B ...] [--thinking-disabled]

Defaults: zomni llama-swap (http://zomni.local:8080).
Models: auto-discovered from /v1/models, minus known embedding-only models (bge-m3).
Each model is loaded via a warmup request, then polled on /running until
state == "ready" before timing starts.

Outputs:
  - GPU contention warning if unexpected models are running at warmup time
  - Full responses per case per model (quality comparison)
  - Auto quality checks (expect_values / expect_not)
  - Summary table: load time, TTFT, total time, ~tok/s, quality pass/fail
  - Per-model verdict line

Exit 0 always (individual failures noted in output).
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
        "expect_values": ["68.90", "68,90"],
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
        "expect_values": ["O2"],
        "expect_not": ["CHF 29.90", "29.90"],  # must NOT cite O2 amount as electricity
    },
]

# Models that are embeddings-only or otherwise not suitable for chat
_SKIP_MODELS = {"bge-m3"}


# ---------------------------------------------------------------------------
# llama-swap helpers
# ---------------------------------------------------------------------------


def list_models(endpoint: str) -> list[str]:
    """Return all model IDs from /v1/models, excluding embedding-only models."""
    try:
        resp = httpx.get(endpoint.rstrip("/") + "/v1/models", timeout=10.0)
        resp.raise_for_status()
        ids = [m["id"] for m in resp.json().get("data", [])]
        return [m for m in ids if m not in _SKIP_MODELS]
    except Exception as exc:
        print(f"  WARNING: could not list models: {exc}", file=sys.stderr)
        return []


def running_models(endpoint: str) -> list[dict]:
    """Return the list of currently-loaded models from /running."""
    try:
        resp = httpx.get(endpoint.rstrip("/") + "/running", timeout=5.0)
        resp.raise_for_status()
        return resp.json().get("running", [])
    except Exception:
        return []


def wait_until_ready(endpoint: str, model: str, *, poll_interval: float = 0.5, timeout: float = 180.0) -> bool:
    """Poll /running until `model` appears with state=='ready'. Return True on success."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for entry in running_models(endpoint):
            if entry.get("model") == model and entry.get("state") == "ready":
                return True
        time.sleep(poll_interval)
    return False


def warn_contention(endpoint: str, target_model: str) -> None:
    """Print a warning if unexpected non-always-on models are loaded alongside target."""
    loaded = running_models(endpoint)
    # ttl==0 means always-on (preloaded); filter those out
    others = [e["model"] for e in loaded if e.get("ttl", 1) != 0 and e.get("model") != target_model]
    if others:
        print(f"  ⚠  GPU contention: {', '.join(others)} also loaded alongside {target_model}")


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


@dataclass
class Result:
    model: str
    case_id: str
    ok: bool
    load_s: float = 0.0      # time for warmup request + ready poll
    ttft_s: float = 0.0      # time to first token (after model is ready)
    total_s: float = 0.0
    chars: int = 0
    text: str = ""
    error: str = ""
    quality_ok: bool | None = None
    quality_notes: str = ""


def _chat_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    if endpoint.endswith("/v1"):
        return endpoint + "/chat/completions"
    return endpoint + "/v1/chat/completions"


def _stream(endpoint: str, model: str, system: str, user: str, *, thinking_disabled: bool = False) -> Iterator[str]:
    url = _chat_url(endpoint)
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
    }
    if thinking_disabled:
        payload["thinking"] = {"type": "disabled"}
    with httpx.stream("POST", url, json=payload, timeout=180.0) as resp:
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


def load_model(endpoint: str, model: str, *, thinking_disabled: bool = False) -> float:
    """Trigger model load via a warmup request, then poll until state==ready.

    Returns elapsed seconds (load time). Prints progress inline.
    """
    t0 = time.monotonic()

    # Check if already ready
    for entry in running_models(endpoint):
        if entry.get("model") == model and entry.get("state") == "ready":
            elapsed = time.monotonic() - t0
            print(f"  load {model}: already ready ({elapsed:.1f}s)")
            return elapsed

    # Send a minimal request to trigger the swap
    url = _chat_url(endpoint)
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True,
        "max_tokens": 4,
    }
    if thinking_disabled:
        payload["thinking"] = {"type": "disabled"}
    print(f"  load {model}: triggering swap ...", end=" ", flush=True)
    try:
        with httpx.stream("POST", url, json=payload, timeout=180.0) as resp:
            resp.raise_for_status()
            for _ in resp.iter_lines():
                pass
    except Exception as exc:
        print(f"warmup request failed: {exc}")

    # Poll until state==ready
    print("polling ready ...", end=" ", flush=True)
    ready = wait_until_ready(endpoint, model)
    elapsed = time.monotonic() - t0
    if ready:
        print(f"ready ({elapsed:.1f}s)")
    else:
        print(f"TIMEOUT after {elapsed:.1f}s (proceeding anyway)")
    return elapsed


def _check_quality(text: str, case: dict) -> tuple[bool, str]:
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


def run_case(endpoint: str, model: str, case: dict, *, thinking_disabled: bool = False) -> Result:
    context = case["context"]
    question = case["question"]
    user_content = f"Sources:\n\n{context}\n\n---\n\nQuestion: {question}"
    result = Result(model=model, case_id=case["id"], ok=False)
    t0 = time.monotonic()
    first_token = False
    try:
        chunks: list[str] = []
        for chunk in _stream(endpoint, model, SYSTEM_PROMPT, user_content, thinking_disabled=thinking_disabled):
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
        result.error = str(exc)[:200]
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
                print(f"  {mdl:<22}  — (not run)")
            elif not r.ok:
                print(f"  {mdl:<22}  ERROR: {r.error}")
            else:
                tps_est = r.chars / (r.total_s or 1) / 4
                qmark = "?" if r.quality_ok is None else ("✓" if r.quality_ok else "✗")
                print(
                    f"  {mdl:<22}  ttft={r.ttft_s:.2f}s  total={r.total_s:.2f}s"
                    f"  ~{tps_est:.0f} tok/s  quality={qmark}"
                )
                print(f"  {'':22}  {r.quality_notes}")
                for ln in _wrap(r.text):
                    print(ln)
    print(f"{'─' * 80}")


def print_summary(results: list[Result], models: list[str], load_times: dict[str, float]) -> None:
    print("\nSUMMARY  (load = warmup+ready time; TTFT = first-token latency when warm)")
    print(f"  {'model':<22}  {'load':>6}  {'ttft avg':>8}  {'total avg':>9}  {'~tok/s':>7}  quality")
    print(f"  {'─'*22}  {'─'*6}  {'─'*8}  {'─'*9}  {'─'*7}  ───────")
    for mdl in models:
        mdl_results = [r for r in results if r.model == mdl and r.ok]
        if not mdl_results:
            print(f"  {mdl:<22}  — all cases failed")
            continue
        checks = [r for r in mdl_results if r.quality_ok is not None]
        passes = sum(1 for r in checks if r.quality_ok)
        avg_ttft = sum(r.ttft_s for r in mdl_results) / len(mdl_results)
        avg_total = sum(r.total_s for r in mdl_results) / len(mdl_results)
        avg_tps = sum(r.chars / (r.total_s or 1) / 4 for r in mdl_results) / len(mdl_results)
        q_str = f"{passes}/{len(checks)}" if checks else "n/a"
        load = load_times.get(mdl, 0.0)
        print(
            f"  {mdl:<22}  {load:>5.1f}s  {avg_ttft:>7.2f}s  {avg_total:>8.2f}s"
            f"  {avg_tps:>6.0f}   {q_str}"
        )

    print()
    print("PER-CASE DETAIL")
    print(f"  {'case':<15}  {'model':<22}  {'ttft':>6}  {'total':>7}  quality")
    print(f"  {'─'*15}  {'─'*22}  {'─'*6}  {'─'*7}  ───────")
    for case in CASES:
        for mdl in models:
            r = next((x for x in results if x.case_id == case["id"] and x.model == mdl), None)
            if r is None:
                continue
            if not r.ok:
                print(f"  {case['id']:<15}  {mdl:<22}  ERROR")
                continue
            qmark = "?" if r.quality_ok is None else ("✓ pass" if r.quality_ok else "✗ FAIL")
            print(
                f"  {case['id']:<15}  {mdl:<22}  {r.ttft_s:>5.2f}s  {r.total_s:>6.2f}s  {qmark}"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    doc = __doc__ or ""
    parser = argparse.ArgumentParser(description=doc.splitlines()[0])
    parser.add_argument("--endpoint", default="http://zomni.local:8080")
    parser.add_argument("--models", nargs="+", default=[],
                        help="Models to benchmark (default: auto-discover all chat models)")
    parser.add_argument("--exclude", nargs="+", default=[],
                        help="Model IDs to skip (added to built-in embedding skip list)")
    parser.add_argument("--thinking-disabled", action="store_true",
                        help="Inject {\"thinking\":{\"type\":\"disabled\"}} into all requests (for reasoning models)")
    args = parser.parse_args()

    endpoint = args.endpoint
    thinking_disabled: bool = args.thinking_disabled
    skip = _SKIP_MODELS | set(args.exclude)

    if args.models:
        models = [m for m in args.models if m not in skip]
    else:
        models = list_models(endpoint)
        models = [m for m in models if m not in skip]
        if not models:
            print("ERROR: no models discovered. Pass --models explicitly.")
            return 1

    print(f"Endpoint: {endpoint}")
    print(f"Models ({len(models)}): {', '.join(models)}")
    print(f"Cases:  {len(CASES)}")
    if thinking_disabled:
        print("Thinking: disabled (injecting {\"thinking\":{\"type\":\"disabled\"}})")
    print()

    results: list[Result] = []
    load_times: dict[str, float] = {}

    for model in models:
        warn_contention(endpoint, model)
        load_s = load_model(endpoint, model, thinking_disabled=thinking_disabled)
        load_times[model] = load_s

        for case in CASES:
            print(f"  run {model} / {case['id']} ...", end=" ", flush=True)
            r = run_case(endpoint, model, case, thinking_disabled=thinking_disabled)
            r.load_s = load_s
            results.append(r)
            if r.ok:
                qmark = "" if r.quality_ok is None else (" ✓" if r.quality_ok else " ✗")
                print(f"ttft={r.ttft_s:.2f}s total={r.total_s:.2f}s{qmark}")
            else:
                print(f"FAILED: {r.error}")

        print()

    print_comparison(results, models)
    print_summary(results, models, load_times)
    return 0


if __name__ == "__main__":
    sys.exit(main())
