"""Shared scanned-only PDF routing decision for zkm.

Owns the single source of truth for whether a PDF is "scanned-only" (i.e. has
too few extractable characters to be processed as a text PDF). This eliminates
the drift between zkm-pdf and zkm-scan that caused whitespace-heavy PDFs to be
skipped by both plugins with different thresholds.

Routing contract (pinned here and in ARCHITECTURE.md §Routing contract):
  total_chars = Σ len(page.extract_text().strip()) over all pages,
  where None returns from extract_text() contribute 0 (strip-safe).

A PDF is scanned-only when total_chars < threshold (strict less-than).

Usage (plugin side)::

    import pypdf
    from zkm.pdftext import probe, is_scanned_only, resolve_threshold

    reader = pypdf.PdfReader(path)
    p = probe(reader)
    threshold = resolve_threshold(store_config)
    if is_scanned_only(p, threshold):
        # route to OCR / scan plugin
        ...

Design meeting: docs/meeting-notes/2026-06-22-1546-pdf-routing-unify-pdftext.md
ROADMAP id: 9e13
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

DEFAULT_TEXT_THRESHOLD: int = 100
"""Default minimum stripped-character count below which a PDF is scanned-only."""


@dataclass(frozen=True)
class PdfTextProbe:
    """Measurement result of a PDF's extractable text.

    Attributes:
        total_chars: Sum of ``len(page.extract_text().strip())`` over all pages.
            Pages returning None from extract_text() contribute 0.
        n_pages: Total number of pages in the PDF.
    """

    total_chars: int
    n_pages: int


def probe(reader: Any) -> PdfTextProbe:
    """Measure extractable text in an already-open PDF reader.

    *reader* is duck-typed: any object with a ``.pages`` attribute where each
    page exposes ``.extract_text()`` (returning a str or None). The caller owns
    the single parse — this function performs no double-extraction.

    Canonical measurand:
        total_chars = Σ len(page.extract_text().strip()) over all pages;
        pages returning None contribute 0.
    """
    pages = reader.pages
    total = 0
    for page in pages:
        text = page.extract_text()
        if text is not None:
            total += len(text.strip())
    return PdfTextProbe(total_chars=total, n_pages=len(pages))


def is_scanned_only(p: PdfTextProbe, threshold: int) -> bool:
    """Return True iff *p* represents a scanned-only PDF.

    A PDF is scanned-only when ``total_chars < threshold`` (strict less-than).
    A PDF at exactly the threshold is NOT scanned-only.
    """
    return p.total_chars < threshold


def resolve_threshold(store_config: dict[str, Any]) -> int:
    """Resolve the PDF text threshold from a store config dict.

    Resolution order (first match wins):
    1. Top-level ``pdf_text_threshold`` key.
    2. Per-section values under any plugin section dict that contains
       ``pdf_text_threshold``; if two or more per-section values are present
       and differ, emits a warning (best-effort, never raises) and uses the
       first one found.
    3. ``DEFAULT_TEXT_THRESHOLD`` (100).

    *store_config* is the parsed YAML dict (plugin sections are top-level keys
    whose values are dicts).
    """
    # Priority 1: top-level key
    if "pdf_text_threshold" in store_config:
        return int(store_config["pdf_text_threshold"])

    # Priority 2: per-section fallback — collect all per-section values
    per_section_values: list[int] = []
    for key, value in store_config.items():
        if isinstance(value, dict) and "pdf_text_threshold" in value:
            per_section_values.append(int(value["pdf_text_threshold"]))

    if per_section_values:
        if len(per_section_values) > 1:
            unique = set(per_section_values)
            if len(unique) > 1:
                warnings.warn(
                    f"pdf_text_threshold is set in multiple config sections with "
                    f"different values {sorted(unique)}; using the first one found "
                    f"({per_section_values[0]}). Set a top-level pdf_text_threshold "
                    f"to silence this warning.",
                    stacklevel=2,
                )
        return per_section_values[0]

    # Priority 3: default
    return DEFAULT_TEXT_THRESHOLD
