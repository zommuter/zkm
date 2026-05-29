#!/usr/bin/env python3
"""Seed a dev store with the committed synthetic corpus for offline BM25 testing.

Usage:
    uv run python scripts/seed_dev_store.py [--store PATH] [--with-pathological]

Produces a searchable BM25 store in <1 s with no embed required.
The committed corpus at tests/fixtures/corpus/ is the source of truth.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "corpus"
PATHOLOGICAL_DIR = REPO_ROOT / "tests" / "fixtures" / "pathological"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store",
        default="/tmp/zkm-dev-store",
        help="Target store path (default: /tmp/zkm-dev-store)",
    )
    parser.add_argument(
        "--with-pathological",
        action="store_true",
        help="Also include pathological test fixtures under <store>/pathological/",
    )
    args = parser.parse_args()

    store = Path(args.store)

    from zkm.store import init_store

    init_store(store, backend="none")

    # Copy committed corpus (mail/**/*.md and any other subdirs)
    for src in CORPUS_DIR.rglob("*.md"):
        rel = src.relative_to(CORPUS_DIR)
        dst = store / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Optionally include pathological fixtures
    if args.with_pathological:
        if not PATHOLOGICAL_DIR.exists():
            print(f"warning: pathological dir not found: {PATHOLOGICAL_DIR}")
        else:
            for src in PATHOLOGICAL_DIR.rglob("*.md"):
                rel = src.relative_to(PATHOLOGICAL_DIR)
                dst = store / "pathological" / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    from zkm.index import build_index, save_index

    idx = build_index(store)
    save_index(store, idx)

    print(f"Seeded {len(idx.docs)} docs → {store}")
    print(f"Sample:  uv run zkm search --store {store} --no-dense invoice")


if __name__ == "__main__":
    main()
