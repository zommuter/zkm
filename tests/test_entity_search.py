"""7c typed-value probe: BM25 entity-canonical retrieval regression (E8).

Verifies that entities[].canonical is indexed by BM25 (since commit e56dd55, E8).
The decisive test: corpus_iban_invoice has the IBAN in spaced form in the body,
but NOT in compact form. Searching the compact canonical can only match via
entities[].canonical — never via body text.

Uses the committed synthetic corpus (pre-populated entities[] from zkm-ner regen).
No live zkm-ner dependency at test time.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import frontmatter
import pytest

from zkm.index import build_index, save_index
from zkm.query import search

CORPUS_DIR = Path(__file__).parent / "fixtures" / "corpus"
IBAN_INVOICE_MID = "<corpus-iban-invoice@example.com>"
IBAN_COMPACT = "DE44500105175407324931"
IBAN_SPACED = "DE44 5001 0517 5407 3249 31"


@pytest.fixture()
def corpus_store(tmp_path: Path) -> Path:
    """Seed a temp store from the committed corpus and build BM25 index."""
    store = tmp_path / "store"
    store.mkdir()
    (store / ".git").mkdir()
    # Copy committed corpus .md files (entities[] already baked in from regen)
    for src in (CORPUS_DIR / "mail" / "messages").rglob("*.md"):
        rel = src.relative_to(CORPUS_DIR)
        dst = store / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    idx = build_index(store)
    save_index(store, idx)
    return store


def _iban_invoice_path(store: Path) -> Path:
    """Locate the IBAN invoice .md in the store by message_id."""
    for p in (store / "mail" / "messages").rglob("*.md"):
        post = frontmatter.load(p)
        if post.metadata.get("message_id") == IBAN_INVOICE_MID:
            return p
    pytest.fail(f"IBAN invoice fixture not found in store (message_id={IBAN_INVOICE_MID})")


# ---------------------------------------------------------------------------
# Prerequisite: corpus fixture sanity
# ---------------------------------------------------------------------------


def test_iban_invoice_body_has_spaced_not_compact(corpus_store: Path) -> None:
    """Body has spaced IBAN; compact canonical absent — prerequisite for the search probe."""
    p = _iban_invoice_path(corpus_store)
    post = frontmatter.load(p)
    assert IBAN_SPACED in post.content, "Spaced IBAN missing from body"
    assert IBAN_COMPACT not in post.content, (
        "Compact canonical must NOT appear in body — "
        "otherwise canonical search could match via body text"
    )


def test_iban_invoice_has_entities(corpus_store: Path) -> None:
    """Committed corpus must carry pre-baked entities[] with type:iban and type:amount."""
    p = _iban_invoice_path(corpus_store)
    post = frontmatter.load(p)
    entities = post.metadata.get("entities", [])
    assert entities, "No entities[] in IBAN invoice — run corpus regen with NER step"
    types = {e.get("type") for e in entities if isinstance(e, dict)}
    assert "iban" in types, f"type:iban missing from entities[]; found: {types}"
    assert "amount" in types, f"type:amount missing from entities[]; found: {types}"


# ---------------------------------------------------------------------------
# 7c probe: entity-canonical BM25 retrieval (E8 regression)
# ---------------------------------------------------------------------------


def test_canonical_iban_search_finds_invoice(corpus_store: Path) -> None:
    """Searching the compact IBAN canonical finds the invoice via entities[].canonical.

    The compact form is absent from the body, so a hit can ONLY come from
    the entities[] index path (index.py:73-74). This is the E8 regression check.
    """
    hits = search(corpus_store, IBAN_COMPACT, top_k=5)
    assert hits, f"No hits for compact IBAN canonical '{IBAN_COMPACT}'"
    top_path = str(hits[0].path)
    assert "iban" in top_path or "payment" in top_path or "4da2286f" in top_path, (
        f"Top hit '{top_path}' does not look like the IBAN invoice"
    )
    # Confirm entities[].type:iban is present on the matched doc
    p = _iban_invoice_path(corpus_store)
    post = frontmatter.load(p)
    iban_ents = [e for e in post.metadata.get("entities", [])
                 if isinstance(e, dict) and e.get("type") == "iban"]
    assert iban_ents, "IBAN invoice has no type:iban entity"
    assert iban_ents[0].get("canonical") == IBAN_COMPACT
    assert iban_ents[0].get("valid", True) is not False


def test_amount_search_finds_invoice(corpus_store: Path) -> None:
    """Searching 'CHF 1250' finds the IBAN invoice; that doc has type:amount in entities[]."""
    hits = search(corpus_store, "CHF 1250", top_k=5)
    assert hits, "No hits for 'CHF 1250'"
    # Collect all matched doc paths
    matched_paths = {h.path for h in hits}
    p = _iban_invoice_path(corpus_store)
    rel = str(p.relative_to(corpus_store))
    assert rel in matched_paths, (
        f"IBAN invoice ({rel}) not in top-5 hits for 'CHF 1250'; got: {matched_paths}"
    )
    post = frontmatter.load(p)
    amount_ents = [e for e in post.metadata.get("entities", [])
                   if isinstance(e, dict) and e.get("type") == "amount"]
    assert amount_ents, "IBAN invoice has no type:amount entity"
    chf_ents = [e for e in amount_ents if e.get("unit") == "CHF"]
    assert chf_ents, f"No CHF amount entity; found units: {[e.get('unit') for e in amount_ents]}"
