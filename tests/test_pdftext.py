"""Red-test spec for `zkm.pdftext` — the shared scanned-only routing decision (ROADMAP id:9e13).

One core helper owns the PDF routing DECISION (not just the measurement) so zkm-pdf and
zkm-scan can never drift apart (the whitespace-heavy "skipped by both" bug). RED until
`src/zkm/pdftext.py` exists.

Design (meeting note 2026-06-22-1546-pdf-routing-unify-pdftext.md, D1/D2):
- `PdfTextProbe(total_chars, n_pages)` frozen dataclass.
- `probe(reader)` -> PdfTextProbe; reader is an already-open pypdf.PdfReader (duck-typed
  here: any object with `.pages`, each page exposing `.extract_text()`).
- Canonical measurand: total_chars = Σ len(page.extract_text().strip()) over pages,
  empty pages contribute 0.
- `is_scanned_only(probe, threshold)` -> bool  (== total_chars < threshold).
- `resolve_threshold(store_config)`: top-level `pdf_text_threshold` wins → else per-section
  → else DEFAULT_TEXT_THRESHOLD (100); warn (never fail) when two per-section values differ.
"""

from __future__ import annotations


class _Page:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _Reader:
    def __init__(self, texts):
        self.pages = [_Page(t) for t in texts]


def test_probe_canonical_measurand():  # roadmap:9e13
    from zkm.pdftext import probe

    # "  ab  " strips to "ab" (2); "" -> 0; None -> 0; "cde" -> 3
    p = probe(_Reader(["  ab  ", "", None, "cde"]))
    assert p.total_chars == 5
    assert p.n_pages == 4


def test_is_scanned_only_strict_less_than():  # roadmap:9e13
    from zkm.pdftext import PdfTextProbe, is_scanned_only

    assert is_scanned_only(PdfTextProbe(total_chars=99, n_pages=3), 100) is True
    # boundary: equal to threshold is NOT scanned-only (strict <)
    assert is_scanned_only(PdfTextProbe(total_chars=100, n_pages=3), 100) is False
    assert is_scanned_only(PdfTextProbe(total_chars=101, n_pages=3), 100) is False


def test_one_shared_verdict_for_whitespace_heavy_pdf():  # roadmap:9e13
    from zkm.pdftext import is_scanned_only, probe, resolve_threshold

    # whitespace-heavy: raw len would be large, but stripped chars are below threshold
    reader = _Reader(["   \n   \t   ", "    ", "x"])
    p = probe(reader)
    assert p.total_chars == 1  # only the "x" survives strip
    threshold = resolve_threshold({})
    # both plugins call the SAME function -> exactly one verdict, no drift
    assert is_scanned_only(p, threshold) is True


def test_resolve_threshold_default():  # roadmap:9e13
    from zkm.pdftext import DEFAULT_TEXT_THRESHOLD, resolve_threshold

    assert DEFAULT_TEXT_THRESHOLD == 100
    assert resolve_threshold({}) == 100


def test_resolve_threshold_top_level_wins():  # roadmap:9e13
    from zkm.pdftext import resolve_threshold

    cfg = {"pdf_text_threshold": 150, "pdf": {"pdf_text_threshold": 50}}
    assert resolve_threshold(cfg) == 150


def test_resolve_threshold_per_section_fallback():  # roadmap:9e13
    from zkm.pdftext import resolve_threshold

    assert resolve_threshold({"pdf": {"pdf_text_threshold": 75}}) == 75
