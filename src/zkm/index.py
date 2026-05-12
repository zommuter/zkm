"""BM25 indexer over the knowledge store."""

from __future__ import annotations

import pickle
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import frontmatter
import snowballstemmer
from rank_bm25 import BM25Okapi

from zkm.atomic import write_atomic

# Bumped when tokenization schema changes — forces index rebuild on load mismatch.
_PICKLE_VERSION = 4
_INDEX_FILE = ".zkm-index/bm25.pkl"
_WATERMARK_FILE = ".zkm-index/last-commit"

_stemmer_en = snowballstemmer.stemmer("english")
_stemmer_de = snowballstemmer.stemmer("german")

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
    """Tokenize text with Unicode support and bilingual (en+de) Snowball stemming.

    Each raw token expands to itself plus its English and German stems, deduplicated.
    This lets "meetings" match "meeting", "Rechnungen" match "Rechnung", etc.
    """
    raw_tokens = re.findall(r"\w[\w'-]+", text.lower(), re.UNICODE)
    seen: set[str] = set()
    result: list[str] = []
    for tok in raw_tokens:
        for variant in (tok, _stemmer_en.stemWord(tok), _stemmer_de.stemWord(tok)):
            if variant and variant not in seen:
                seen.add(variant)
                result.append(variant)
    return result


def _tokenize_doc(post: frontmatter.Post) -> list[str]:
    tokens = tokenize(post.content)
    tokens += tokenize(post.metadata.get("title", ""))
    for tag in post.metadata.get("tags", []):
        tokens.append(str(tag).lower())
    for ent in post.metadata.get("entities", []):
        if isinstance(ent, dict):
            if ent.get("valid", True) is False:
                continue
            tokens += tokenize(str(ent.get("value", "")))
            if ent.get("canonical"):
                tokens += tokenize(str(ent["canonical"]))
    for p in post.metadata.get("participants", []):
        if isinstance(p, dict):
            if p.get("address"):
                tokens += tokenize(str(p["address"]))
            if p.get("name"):
                tokens += tokenize(str(p["name"]))
    return tokens


def _should_skip(rel: Path) -> bool:
    return bool(rel.parts) and rel.parts[0] in _SKIP_DIRS


def _read_watermark(store: Path) -> str | None:
    p = store / _WATERMARK_FILE
    if not p.exists():
        return None
    text = p.read_text().strip()
    return text or None


def write_watermark(store: Path, sha: str) -> None:
    """Atomically record *sha* as the last-indexed commit for *store*."""
    watermark_path = store / _WATERMARK_FILE
    watermark_path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(watermark_path, sha + "\n")


def _changed_md_paths(store: Path, watermark: str) -> tuple[set[str], set[str]] | None:
    """Return (candidates, deleted) of rel-posix .md paths since *watermark*, or None to fall back.

    candidates: .md paths added/modified/renamed (new name) since watermark or dirty in work tree
    deleted: .md paths deleted since watermark
    Returns None when watermark is not an ancestor of HEAD or any git call fails.
    """
    try:
        r = subprocess.run(
            ["git", "merge-base", "--is-ancestor", watermark, "HEAD"],
            cwd=store, capture_output=True, timeout=10,
        )
        if r.returncode != 0:
            return None

        diff_out = subprocess.run(
            ["git", "diff", "--name-status", watermark, "HEAD", "--", "*.md"],
            cwd=store, check=True, capture_output=True, text=True, timeout=30,
        ).stdout

        candidates: set[str] = set()
        deleted: set[str] = set()
        for line in diff_out.splitlines():
            if not line:
                continue
            parts = line.split("\t")
            status = parts[0].rstrip("0123456789")
            if status == "D":
                deleted.add(parts[1])
            elif status.startswith("R") and len(parts) > 2:
                deleted.add(parts[1])
                candidates.add(parts[2])
            elif len(parts) >= 2:
                candidates.add(parts[1])

        status_out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=store, check=True, capture_output=True, text=True, timeout=10,
        ).stdout
        for line in status_out.splitlines():
            if len(line) < 4:
                continue
            xy, path = line[:2], line[3:]
            if " -> " in path:
                old, path = path.split(" -> ", 1)
                if old.endswith(".md"):
                    deleted.add(old)
            if not path.endswith(".md"):
                continue
            if "D" in xy:
                deleted.add(path)
            else:
                candidates.add(path)

        candidates -= deleted
        return candidates, deleted
    except Exception:
        return None


def build_index(
    store: Path,
    *,
    progress: ProgressCallback | None = None,
    full: bool = False,
) -> Index:
    """Walk store for *.md, tokenize, build BM25 index.

    Incremental by default: on first call after a ``write_watermark`` the fast path
    uses ``git diff`` to enumerate only changed files.  Falls back to a full
    ``rglob`` scan when *full* is True, the watermark is absent, or git reports
    the watermark as unreachable.

    Within either path, mtime_ns caching avoids re-tokenising files that haven't
    changed on disk.
    """
    prev_index = load_index(store)
    prev: dict[str, Doc] = {d.rel_path: d for d in prev_index.docs} if prev_index else {}

    fast: tuple[set[str], set[str]] | None = None
    if not full and prev_index is not None:
        watermark = _read_watermark(store)
        if watermark:
            fast = _changed_md_paths(store, watermark)

    docs: list[Doc]

    if fast is not None:
        changed, deleted = fast
        for d in deleted:
            prev.pop(d, None)
        for c in changed:
            prev.pop(c, None)

        changed_candidates = sorted(r for r in changed if not _should_skip(Path(r)))
        total = len(changed_candidates)
        new_docs: list[Doc] = []
        for i, rel in enumerate(changed_candidates):
            if progress is not None:
                progress(i, total, Path(rel).name)
            path = store / rel
            if not path.exists():
                continue
            mtime_ns = path.stat().st_mtime_ns
            try:
                post = frontmatter.load(path)
            except Exception:
                continue
            new_docs.append(Doc(
                rel_path=rel, mtime_ns=mtime_ns,
                metadata=dict(post.metadata), tokens=_tokenize_doc(post),
            ))

        if progress is not None:
            progress(total, total, "done")

        docs = list(prev.values()) + new_docs
    else:
        candidates = sorted(
            p for p in store.rglob("*.md") if not _should_skip(p.relative_to(store))
        )
        total = len(candidates)
        docs = []
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
    return Index(docs=docs, bm25=bm25)


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
