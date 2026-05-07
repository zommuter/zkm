"""Dense embedding client + EmbedStore for hybrid BM25 + dense retrieval.

Embeddings are fetched via an OpenAI-compatible /v1/embeddings endpoint (e.g.
llama.cpp server, Ollama, llama-swap serving bge-m3). No local inference deps.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np

from zkm.convert import load_env

_DEFAULT_ENDPOINT = "http://localhost:8080"
_DEFAULT_MODEL = "bge-m3"
_EMBED_BATCH = 32
# ~335 tokens worst-case (dense German subwords ~6 chars/tok → ~2000/6=333 tok).
# Requires --ubatch-size >= 512 on the llama-server side (default is 512, raise to 2048+
# for headroom). Override with ZKM_EMBED_MAX_CHARS env var.
_DEFAULT_EMBED_MAX_CHARS = 2000
_NPZ_FILE = ".zkm-index/embeddings.npz"
_META_FILE = ".zkm-index/embeddings-meta.json"


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
    """Resolve embed config from overrides → env vars → .env → defaults.

    Returns (endpoint, model, key). Endpoint is empty string when not configured.
    """
    import os

    env = load_env(store)

    def _get(key: str, override: str | None, default: str) -> str:
        if override:
            return override
        if key in os.environ:
            return os.environ[key]
        if key in env:
            return env[key]
        return default

    ep = _get("ZKM_EMBED_ENDPOINT", endpoint, _DEFAULT_ENDPOINT)
    mdl = _get("ZKM_EMBED_MODEL", model, _DEFAULT_MODEL)
    key = _get("ZKM_EMBED_KEY", api_key, "")
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


@dataclass
class EmbedStore:
    """In-memory embedding matrix with path→row index for fast lookup."""

    paths: list[str]
    mtimes_ns: list[int]
    vectors: np.ndarray  # float32 (N, D), L2-normalized
    model: str = _DEFAULT_MODEL
    _path_index: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._path_index = {p: i for i, p in enumerate(self.paths)}

    def topk(self, query_vec: np.ndarray, k: int) -> list[tuple[int, float]]:
        """Return up to k (row_index, score) pairs, descending cosine similarity."""
        if not self.paths:
            return []
        scores: np.ndarray = self.vectors @ query_vec
        k = min(k, len(self.paths))
        top_idx = np.argpartition(scores, -k)[-k:]
        top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]
        return [(int(i), float(scores[i])) for i in top_idx]

    def lookup(self, rel_path: str) -> int | None:
        return self._path_index.get(rel_path)


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
            vectors=es.vectors,
        )
    os.replace(npz_tmp, npz_path)

    meta = {
        "model": es.model,
        "dim": int(es.vectors.shape[1]) if es.paths else 0,
        "built_at": datetime.now(tz=UTC).isoformat(),
        "n_docs": len(es.paths),
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
        data = np.load(npz_path, allow_pickle=True)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return EmbedStore(
            paths=list(data["paths"]),
            mtimes_ns=list(map(int, data["mtimes_ns"].tolist())),
            vectors=data["vectors"].astype(np.float32),
            model=meta.get("model", _DEFAULT_MODEL),
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
    checkpoint_every: int = 500,
    progress=None,  # ProgressCallback | None
) -> EmbedStore:
    """Build or incrementally update an EmbedStore for the given docs.

    Reuses cached vectors for docs whose mtime_ns is unchanged and whose
    model matches. Saves a checkpoint to disk every checkpoint_every newly
    embedded docs so that interrupted runs can resume without re-embedding.
    """
    # Build lookup from previous store (None → empty)
    prev_paths: dict[str, tuple[int, int]] = {}  # rel_path → (row, mtime_ns)
    prev_vecs: dict[str, np.ndarray] = {}
    if prev_es is not None and prev_es.model == model:
        for idx, (p, m) in enumerate(zip(prev_es.paths, prev_es.mtimes_ns)):
            prev_paths[p] = (idx, m)
            prev_vecs[p] = prev_es.vectors[idx]

    # Partition docs into cached vs. needing embedding
    # acc_* grows through the loop — starts with already-cached vectors so
    # checkpoints always include everything done so far.
    acc_paths: list[str] = []
    acc_mtimes: list[int] = []
    acc_vecs: list[np.ndarray] = []
    new_docs: list = []

    for doc in docs:
        prev = prev_paths.get(doc.rel_path)
        if prev is not None and prev[1] == doc.mtime_ns:
            acc_paths.append(doc.rel_path)
            acc_mtimes.append(doc.mtime_ns)
            acc_vecs.append(prev_vecs[doc.rel_path])
        else:
            new_docs.append(doc)

    # Embed new/changed docs, checkpointing every checkpoint_every docs
    if new_docs:
        n = len(new_docs)
        if progress is not None:
            progress(0, n, "embedding…")
        url = _embeddings_url(endpoint)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        done = 0
        for batch_start in range(0, n, _EMBED_BATCH):
            batch_docs = new_docs[batch_start : batch_start + _EMBED_BATCH]
            texts = [_embed_text(store, doc) for doc in batch_docs]
            try:
                resp = httpx.post(
                    url, headers=headers, json={"model": model, "input": texts}, timeout=timeout
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                data.sort(key=lambda x: x["index"])
                batch_vecs = np.array([item["embedding"] for item in data], dtype=np.float32)
                norms = np.linalg.norm(batch_vecs, axis=1, keepdims=True)
                norms = np.where(norms == 0.0, 1.0, norms)
                batch_vecs = (batch_vecs / norms).astype(np.float32)
            except EmbedUnavailable:
                raise
            except Exception as exc:
                raise EmbedUnavailable(f"embed_texts failed: {exc}") from exc
            for doc, vec in zip(batch_docs, batch_vecs):
                acc_paths.append(doc.rel_path)
                acc_mtimes.append(doc.mtime_ns)
                acc_vecs.append(vec)
            done += len(batch_docs)
            if progress is not None:
                progress(done, n, batch_docs[-1].rel_path.split("/")[-1])
            if checkpoint_every and done % checkpoint_every < _EMBED_BATCH:
                _save_partial(store, acc_paths, acc_mtimes, acc_vecs, model)

    # acc_* now contains everything (cached + newly embedded); reconstruct in doc order
    path_to_vec: dict[str, tuple[int, np.ndarray]] = {
        p: (m, v) for p, m, v in zip(acc_paths, acc_mtimes, acc_vecs)
    }

    final_paths: list[str] = []
    final_mtimes: list[int] = []
    final_vecs: list[np.ndarray] = []
    for doc in docs:
        if doc.rel_path in path_to_vec:
            m, v = path_to_vec[doc.rel_path]
            final_paths.append(doc.rel_path)
            final_mtimes.append(m)
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
    )


def _save_partial(
    store: Path,
    paths: list[str],
    mtimes_ns: list[int],
    vecs: list[np.ndarray],
    model: str,
) -> None:
    """Write a partial EmbedStore to disk for interrupt/resume support."""
    if not vecs:
        return
    mat = np.stack(vecs, axis=0).astype(np.float32)
    es = EmbedStore(paths=list(paths), mtimes_ns=list(mtimes_ns), vectors=mat, model=model)
    save_embed_store(store, es)


def _embed_text(store: Path, doc) -> str:  # doc: Doc
    """Build embed text: title + tags + first N chars of body.

    N defaults to _DEFAULT_EMBED_MAX_CHARS (~375 tokens); override with ZKM_EMBED_MAX_CHARS.
    """
    import os

    import frontmatter

    max_chars = int(os.environ.get("ZKM_EMBED_MAX_CHARS", _DEFAULT_EMBED_MAX_CHARS))
    try:
        post = frontmatter.load(store / doc.rel_path)
        title = str(post.metadata.get("title", ""))
        tags = post.metadata.get("tags", [])
        tag_str = " ".join(str(t) for t in tags) if tags else ""
        body = post.content[:max_chars]
        return "\n".join(p for p in [title, tag_str, body] if p)
    except Exception:
        return " ".join(doc.tokens[:200])
