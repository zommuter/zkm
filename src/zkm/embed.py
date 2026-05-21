"""Dense embedding client + EmbedStore for hybrid BM25 + dense retrieval.

Embeddings are fetched via an OpenAI-compatible /v1/embeddings endpoint (e.g.
llama.cpp server, Ollama, llama-swap serving bge-m3). No local inference deps.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np

from zkm.config import load_config

_DEFAULT_ENDPOINT = "http://localhost:8080"
_DEFAULT_MODEL = "bge-m3"
_EMBED_BATCH = 32
# ~335 tokens worst-case (dense German subwords ~6 chars/tok → ~2000/6=333 tok).
# Requires --ubatch-size >= 512 on the llama-server side (default is 512, raise to 2048+
# for headroom). Override with ZKM_EMBED_CHUNK_CHARS env var.
_DEFAULT_CHUNK_CHARS = 2000
# Retry sleeps (seconds) on transient 500s. Spans the ~30-40s self-recovery window
# observed in bge-m3/llama-server embedding mode under sustained load. Attempt 2
# fires at ~45s (0+15+30), well past the recovery window.
_EMBED_RETRY_SLEEPS = (0, 15, 30, 60)
_DEFAULT_CHUNK_OVERLAP = 200
_NPZ_FILE = ".zkm-index/embeddings.npz"
_META_FILE = ".zkm-index/embeddings-meta.json"
_STORE_SCHEMA_VERSION = 3


class EmbedUnavailable(Exception):
    """Raised when the embedding endpoint is unconfigured or unreachable."""


def _embeddings_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/embeddings"):
        return endpoint
    if endpoint.endswith("/v1"):
        return endpoint + "/embeddings"
    return endpoint + "/v1/embeddings"


def resolve_embed_config(
    store: Path,
    endpoint: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> tuple[str, str, str]:
    """Resolve embed config from overrides → store config → defaults.

    Returns (endpoint, model, key). Endpoint is empty string when not configured.
    """
    cfg = load_config(store)
    ep = endpoint or cfg.core_value("embed", "endpoint") or _DEFAULT_ENDPOINT
    mdl = model or cfg.core_value("embed", "model") or _DEFAULT_MODEL
    key = api_key if api_key is not None else (cfg.core_value("embed", "key") or "")
    return ep, mdl, key


def embed_texts(
    texts: list[str],
    endpoint: str,
    model: str,
    api_key: str = "",
    *,
    timeout: float = 60.0,
) -> np.ndarray:
    """POST texts to /v1/embeddings. Returns float32 (N, D) L2-normalized matrix."""
    if not endpoint:
        raise EmbedUnavailable("ZKM_EMBED_ENDPOINT not set")

    url = _embeddings_url(endpoint)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    all_vecs: list[np.ndarray] = []
    for i in range(0, len(texts), _EMBED_BATCH):
        batch = texts[i : i + _EMBED_BATCH]
        payload = {"model": model, "input": batch}
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()["data"]
            data.sort(key=lambda x: x["index"])
            vecs = np.array([item["embedding"] for item in data], dtype=np.float32)
        except EmbedUnavailable:
            raise
        except Exception as exc:
            raise EmbedUnavailable(f"embed_texts failed: {exc}") from exc
        all_vecs.append(vecs)

    mat = np.concatenate(all_vecs, axis=0)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return (mat / norms).astype(np.float32)


def _post_embed_batch(
    url: str, headers: dict[str, str], model: str, texts: list[str], timeout: float
) -> np.ndarray:
    """POST one batch, return L2-normalized float32 (N, D). Raises httpx errors as-is."""
    resp = httpx.post(url, headers=headers, json={"model": model, "input": texts}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda x: x["index"])
    vecs = np.array([item["embedding"] for item in data], dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return (vecs / norms).astype(np.float32)


def _is_too_large_error(exc: Exception) -> bool:
    """True if exc is the server rejecting an input that exceeds its physical batch size.

    This 500 is *deterministic* — the same oversized input fails identically every time —
    so it must NOT be retried with backoff; the offending text is split instead.
    """
    return isinstance(exc, httpx.HTTPStatusError) and "too large to process" in exc.response.text


def _embed_single_with_split(
    url: str, headers: dict[str, str], model: str, text: str, timeout: float, *, depth: int = 0
) -> np.ndarray:
    """Embed one text; if the server rejects it as too large, split in half and mean-pool
    the sub-vectors so the chunk still maps to a single normalized (D,) row."""
    try:
        return _post_embed_batch(url, headers, model, [text], timeout)[0]
    except httpx.HTTPStatusError as exc:
        if not _is_too_large_error(exc) or len(text) <= 1 or depth >= 24:
            raise
    mid = len(text) // 2
    left = _embed_single_with_split(url, headers, model, text[:mid], timeout, depth=depth + 1)
    right = _embed_single_with_split(url, headers, model, text[mid:], timeout, depth=depth + 1)
    pooled = (left + right) / 2.0
    norm = float(np.linalg.norm(pooled))
    return (pooled / (norm or 1.0)).astype(np.float32)


def _log_embed_stall(batch_start: int, attempt: int, exc: Exception) -> None:
    """Log a transient embed stall (status, body, origin, position) to stderr."""
    nxt = _EMBED_RETRY_SLEEPS[attempt + 1] if attempt + 1 < len(_EMBED_RETRY_SLEEPS) else None
    retry_msg = f"retrying in {nxt}s" if nxt is not None else "giving up"
    if isinstance(exc, httpx.HTTPStatusError):
        origin = exc.response.headers.get("server", exc.response.headers.get("via", "unknown"))
        print(
            f"[zkm-embed] stall at text {batch_start}: attempt {attempt},"
            f" status={exc.response.status_code}, origin={origin!r},"
            f" body={exc.response.text!r}, {retry_msg}",
            file=sys.stderr,
        )
    else:
        print(
            f"[zkm-embed] stall at text {batch_start}: attempt {attempt}, exc={exc!r}, {retry_msg}",
            file=sys.stderr,
        )


@dataclass
class EmbedStore:
    """In-memory embedding matrix with one row per (path, chunk_index) pair."""

    paths: list[str]
    mtimes_ns: list[int]
    vectors: np.ndarray  # float32 (N, D), L2-normalized
    model: str = _DEFAULT_MODEL
    chunk_indices: list[int] = field(default_factory=list)
    _path_to_rows: dict[str, list[int]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.chunk_indices:
            self.chunk_indices = [0] * len(self.paths)
        self._path_to_rows = {}
        for i, p in enumerate(self.paths):
            self._path_to_rows.setdefault(p, []).append(i)

    def topk(self, query_vec: np.ndarray, k: int) -> list[tuple[int, float]]:
        """Return up to k (row_index, score) pairs, descending cosine similarity."""
        if not self.paths:
            return []
        scores: np.ndarray = self.vectors @ query_vec
        k = min(k, len(self.paths))
        top_idx = np.argpartition(scores, -k)[-k:]
        top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]
        return [(int(i), float(scores[i])) for i in top_idx]


def save_embed_store(store: Path, es: EmbedStore) -> None:
    index_dir = store / ".zkm-index"
    index_dir.mkdir(parents=True, exist_ok=True)

    npz_path = store / _NPZ_FILE
    npz_tmp = npz_path.with_name(npz_path.name + ".tmp")
    # Pass a file handle so numpy doesn't append an extra `.npz` suffix.
    with open(npz_tmp, "wb") as f:
        np.savez_compressed(
            f,
            paths=np.array(es.paths, dtype=object),
            mtimes_ns=np.array(es.mtimes_ns, dtype=np.int64),
            chunk_indices=np.array(es.chunk_indices, dtype=np.int32),
            vectors=es.vectors,
        )
    os.replace(npz_tmp, npz_path)

    meta = {
        "model": es.model,
        "dim": int(es.vectors.shape[1]) if es.paths else 0,
        "built_at": datetime.now(tz=UTC).isoformat(),
        "n_docs": len(set(es.paths)),
        "schema_version": _STORE_SCHEMA_VERSION,
    }
    meta_path = store / _META_FILE
    meta_tmp = meta_path.with_name(meta_path.name + ".tmp")
    meta_tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(meta_tmp, meta_path)


def load_embed_store(store: Path) -> EmbedStore | None:
    npz_path = store / _NPZ_FILE
    meta_path = store / _META_FILE
    if not npz_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("schema_version") != _STORE_SCHEMA_VERSION:
            return None
        data = np.load(npz_path, allow_pickle=True)
        chunk_indices = list(map(int, data["chunk_indices"].tolist()))
        return EmbedStore(
            paths=list(data["paths"]),
            mtimes_ns=list(map(int, data["mtimes_ns"].tolist())),
            vectors=data["vectors"].astype(np.float32),
            model=meta.get("model", _DEFAULT_MODEL),
            chunk_indices=chunk_indices,
        )
    except Exception:
        return None


def build_embed_store(
    store: Path,
    docs: list,  # list[Doc] — avoid circular import, typed structurally
    *,
    prev_es: EmbedStore | None,
    endpoint: str,
    model: str,
    api_key: str,
    timeout: float = 60.0,
    checkpoint_every: int = 100,
    progress=None,  # ProgressCallback | None
) -> EmbedStore:
    """Build or incrementally update an EmbedStore for the given docs.

    Reuses all cached chunks for docs whose mtime_ns is unchanged and whose
    model matches. Saves a checkpoint to disk every checkpoint_every newly
    embedded texts so that interrupted runs can resume without re-embedding.
    """
    # Group previous store by rel_path: {path: (mtime_ns, [(chunk_idx, vec), ...])}
    prev_cached: dict[str, tuple[int, list[tuple[int, np.ndarray]]]] = {}
    if prev_es is not None and prev_es.model == model:
        groups: dict[str, list[tuple[int, np.ndarray]]] = {}
        prev_path_mtime: dict[str, int] = {}
        for idx, (p, m, ci) in enumerate(
            zip(prev_es.paths, prev_es.mtimes_ns, prev_es.chunk_indices)
        ):
            groups.setdefault(p, []).append((ci, prev_es.vectors[idx]))
            prev_path_mtime[p] = m
        for p, chunks in groups.items():
            prev_cached[p] = (prev_path_mtime[p], chunks)

    # Partition docs into cached vs. needing embedding.
    # acc_* grows through the loop — starts with cached vectors so checkpoints
    # always include everything done so far.
    acc_paths: list[str] = []
    acc_mtimes: list[int] = []
    acc_chunk_indices: list[int] = []
    acc_vecs: list[np.ndarray] = []
    new_docs: list = []

    for doc in docs:
        if doc.rel_path in prev_cached:
            cached_mtime, cached_chunks = prev_cached[doc.rel_path]
            if cached_mtime == doc.mtime_ns:
                for ci, vec in sorted(cached_chunks, key=lambda x: x[0]):
                    acc_paths.append(doc.rel_path)
                    acc_mtimes.append(doc.mtime_ns)
                    acc_chunk_indices.append(ci)
                    acc_vecs.append(vec)
                continue
        new_docs.append(doc)

    # Embed new/changed docs
    if new_docs:
        # Pre-compute chunks for all new docs to avoid double-reading files
        new_doc_chunks = [(doc, _chunk_texts(store, doc)) for doc in new_docs]

        # Flatten to one text per chunk, keeping (doc, chunk_idx) metadata
        flat_texts: list[str] = []
        flat_meta: list[tuple] = []  # (doc, chunk_idx)
        for doc, chunks in new_doc_chunks:
            for ci, text in enumerate(chunks):
                flat_texts.append(text)
                flat_meta.append((doc, ci))

        n = len(flat_texts)
        if progress is not None:
            progress(0, n, "embedding…")

        url = _embeddings_url(endpoint)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        done = 0
        for batch_start in range(0, n, _EMBED_BATCH):
            batch_texts = flat_texts[batch_start : batch_start + _EMBED_BATCH]
            batch_meta = flat_meta[batch_start : batch_start + _EMBED_BATCH]
            batch_vecs: np.ndarray = np.empty(0)
            last_exc: Exception | None = None
            for attempt, sleep_s in enumerate(_EMBED_RETRY_SLEEPS):
                try:
                    if sleep_s:
                        time.sleep(sleep_s)
                    batch_vecs = _post_embed_batch(url, headers, model, batch_texts, timeout)
                    last_exc = None
                    break
                except EmbedUnavailable:
                    raise
                except httpx.HTTPStatusError as exc:
                    if _is_too_large_error(exc):
                        # Deterministic: a chunk exceeds the server's physical batch size.
                        # Retrying is futile (identical input) — embed each text individually,
                        # splitting + mean-pooling any oversized one. No backoff.
                        print(
                            f"[zkm-embed] oversized chunk at text {batch_start}:"
                            f" {exc.response.text!r}; embedding individually with split",
                            file=sys.stderr,
                        )
                        batch_vecs = np.stack(
                            [_embed_single_with_split(url, headers, model, t, timeout)
                             for t in batch_texts]
                        )
                        last_exc = None
                        break
                    # Transient HTTP error — back off and retry.
                    last_exc = exc
                    _log_embed_stall(batch_start, attempt, exc)
                except Exception as exc:
                    # Transient (connection reset, timeout, …) — back off and retry.
                    last_exc = exc
                    _log_embed_stall(batch_start, attempt, exc)
            if last_exc is not None:
                raise EmbedUnavailable(f"embed_texts failed: {last_exc}") from last_exc
            for (doc, ci), vec in zip(batch_meta, batch_vecs):
                acc_paths.append(doc.rel_path)
                acc_mtimes.append(doc.mtime_ns)
                acc_chunk_indices.append(ci)
                acc_vecs.append(vec)
            done += len(batch_texts)
            if progress is not None:
                progress(done, n, batch_meta[-1][0].rel_path.split("/")[-1])
            if checkpoint_every and done % checkpoint_every < _EMBED_BATCH:
                _save_partial(store, acc_paths, acc_mtimes, acc_chunk_indices, acc_vecs, model)

    # Reconstruct in doc order, with chunks sorted by chunk_index per path
    path_chunks: dict[str, list[tuple[int, int, np.ndarray]]] = {}
    for p, m, ci, v in zip(acc_paths, acc_mtimes, acc_chunk_indices, acc_vecs):
        path_chunks.setdefault(p, []).append((m, ci, v))

    final_paths: list[str] = []
    final_mtimes: list[int] = []
    final_chunk_indices: list[int] = []
    final_vecs: list[np.ndarray] = []
    for doc in docs:
        if doc.rel_path in path_chunks:
            for m, ci, v in sorted(path_chunks[doc.rel_path], key=lambda x: x[1]):
                final_paths.append(doc.rel_path)
                final_mtimes.append(m)
                final_chunk_indices.append(ci)
                final_vecs.append(v)

    if final_vecs:
        mat = np.stack(final_vecs, axis=0).astype(np.float32)
    else:
        mat = np.zeros((0, 1), dtype=np.float32)

    return EmbedStore(
        paths=final_paths,
        mtimes_ns=final_mtimes,
        vectors=mat,
        model=model,
        chunk_indices=final_chunk_indices,
    )


def _save_partial(
    store: Path,
    paths: list[str],
    mtimes_ns: list[int],
    chunk_indices: list[int],
    vecs: list[np.ndarray],
    model: str,
) -> None:
    """Write a partial EmbedStore to disk for interrupt/resume support."""
    if not vecs:
        return
    mat = np.stack(vecs, axis=0).astype(np.float32)
    es = EmbedStore(
        paths=list(paths),
        mtimes_ns=list(mtimes_ns),
        vectors=mat,
        model=model,
        chunk_indices=list(chunk_indices),
    )
    save_embed_store(store, es)


def _chunk_texts(store: Path, doc) -> list[str]:  # doc: Doc
    """Produce one embed text per char-window chunk of the document body.

    ZKM_EMBED_CHUNK_CHARS (default 2000) sets the window size.
    ZKM_EMBED_CHUNK_OVERLAP (default 200) sets the overlap between consecutive chunks.
    ZKM_EMBED_MAX_CHARS is a deprecated alias for ZKM_EMBED_CHUNK_CHARS.
    """
    cfg = load_config(store)
    chunk_chars = int(cfg.core_value("embed", "chunk_chars") or _DEFAULT_CHUNK_CHARS)
    chunk_overlap = int(cfg.core_value("embed", "chunk_overlap") or _DEFAULT_CHUNK_OVERLAP)

    # Keep env overrides for runtime use
    if "ZKM_EMBED_CHUNK_CHARS" in os.environ:
        chunk_chars = int(os.environ["ZKM_EMBED_CHUNK_CHARS"])
    if "ZKM_EMBED_CHUNK_OVERLAP" in os.environ:
        chunk_overlap = int(os.environ["ZKM_EMBED_CHUNK_OVERLAP"])
    if "ZKM_EMBED_MAX_CHARS" in os.environ:
        print(
            "ZKM_EMBED_MAX_CHARS is deprecated; use ZKM_EMBED_CHUNK_CHARS",
            file=sys.stderr,
        )
        chunk_chars = int(os.environ["ZKM_EMBED_MAX_CHARS"])

    try:
        import frontmatter

        post = frontmatter.load(store / doc.rel_path)
        title = str(post.metadata.get("title", ""))
        tags = post.metadata.get("tags", [])
        tag_str = " ".join(str(t) for t in tags) if tags else ""
        body = post.content

        entity_parts: list[str] = []
        for ent in post.metadata.get("entities", []):
            if isinstance(ent, dict) and ent.get("valid", True) is not False:
                val = str(ent.get("value", ""))
                if val:
                    entity_parts.append(val)
                if ent.get("canonical"):
                    entity_parts.append(str(ent["canonical"]))
        entity_str = " ".join(entity_parts)

        participant_parts: list[str] = []
        for p in post.metadata.get("participants", []):
            if isinstance(p, dict):
                if p.get("address"):
                    participant_parts.append(str(p["address"]))
                if p.get("name"):
                    participant_parts.append(str(p["name"]))
        participant_str = " ".join(participant_parts)
    except Exception:
        return [" ".join(doc.tokens[:200])]

    if not body:
        text = "\n".join(p for p in [title, tag_str, entity_str, participant_str] if p)
        return [text or " ".join(doc.tokens[:200])]

    stride = max(1, chunk_chars - chunk_overlap)
    chunks: list[str] = []
    start = 0
    while start < len(body):
        window = body[start : start + chunk_chars]
        text = "\n".join(p for p in [title, tag_str, entity_str, participant_str, window] if p)
        chunks.append(text)
        if start + chunk_chars >= len(body):
            break
        start += stride

    return chunks or [" ".join(doc.tokens[:200])]
