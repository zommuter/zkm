"""BM25 indexer over the knowledge store."""

from __future__ import annotations

import pickle
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import frontmatter
from rank_bm25 import BM25Okapi

_PICKLE_VERSION = 1
_INDEX_FILE = ".zkm-index/bm25.pkl"

_SKIP_DIRS = {"plugins", ".zkm-index", "originals", ".git"}

ProgressCallback = Callable[[int, "int | None", str], None]


@dataclass
class Doc:
    rel_path: str
    mtime_ns: int
    metadata: dict
    tokens: list[str] = field(default_factory=list)


@dataclass
class Index:
    docs: list[Doc]
    bm25: BM25Okapi | None  # None when docs is empty


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_][A-Za-z0-9_'-]+", text.lower())


def _tokenize_doc(post: frontmatter.Post) -> list[str]:
    tokens = tokenize(post.content)
    tokens += tokenize(post.metadata.get("title", ""))
    for tag in post.metadata.get("tags", []):
        tokens.append(str(tag).lower())
    return tokens


def _should_skip(rel: Path) -> bool:
    return bool(rel.parts) and rel.parts[0] in _SKIP_DIRS


def build_index(store: Path, *, progress: ProgressCallback | None = None) -> Index:
    """Walk store for *.md, tokenize, build BM25 index. Incremental: reuses
    cached tokens for files whose mtime_ns is unchanged."""
    prev_index = load_index(store)
    prev: dict[str, Doc] = {d.rel_path: d for d in prev_index.docs} if prev_index else {}

    candidates = sorted(
        p for p in store.rglob("*.md") if not _should_skip(p.relative_to(store))
    )
    total = len(candidates)
    docs: list[Doc] = []

    for i, path in enumerate(candidates):
        if progress is not None:
            progress(i, total, path.name)

        rel = path.relative_to(store).as_posix()
        mtime_ns = path.stat().st_mtime_ns

        if rel in prev and prev[rel].mtime_ns == mtime_ns:
            docs.append(prev[rel])
        else:
            try:
                post = frontmatter.load(path)
            except Exception:
                continue
            docs.append(Doc(
                rel_path=rel, mtime_ns=mtime_ns,
                metadata=dict(post.metadata), tokens=_tokenize_doc(post),
            ))

    if progress is not None:
        progress(total, total, "done")

    if docs:
        corpus = [d.tokens if d.tokens else [""] for d in docs]
        bm25: BM25Okapi | None = BM25Okapi(corpus)
    else:
        bm25 = None
    idx = Index(docs=docs, bm25=bm25)
    return idx


def save_index(store: Path, idx: Index) -> None:
    index_dir = store / ".zkm-index"
    index_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _PICKLE_VERSION,
        "store": str(store),
        "built_at": datetime.now(tz=UTC).isoformat(),
        "index": idx,
    }
    with open(store / _INDEX_FILE, "wb") as fh:
        pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)


def load_index(store: Path) -> Index | None:
    path = store / _INDEX_FILE
    if not path.exists():
        return None
    try:
        with open(path, "rb") as fh:
            payload = pickle.load(fh)
        if payload.get("version") != _PICKLE_VERSION:
            return None
        return payload["index"]
    except Exception:
        return None
