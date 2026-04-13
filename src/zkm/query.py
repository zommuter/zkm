"""Search + LLM context assembly. Phase 1 TODO."""

from pathlib import Path


def search(store: Path, query: str, top_k: int = 10) -> list[dict]:
    """BM25 search over the index. Returns ranked hits. Not yet implemented."""
    raise NotImplementedError("zkm search — see TODO.md")


def llm_query(store: Path, question: str, top_k: int = 5) -> None:
    """Search + assemble context + call LLM endpoint. Not yet implemented."""
    raise NotImplementedError("zkm query — see TODO.md")
