"""BM25 indexer over the knowledge store. Phase 1 TODO."""

from pathlib import Path


def build_index(store: Path) -> None:
    """Walk store/*.md, parse frontmatter, build BM25 index. Not yet implemented."""
    raise NotImplementedError("zkm index — see TODO.md")


def load_index(store: Path) -> object:
    """Load the persisted BM25 index from store/.zkm-index/bm25.pkl."""
    raise NotImplementedError("zkm index — see TODO.md")
