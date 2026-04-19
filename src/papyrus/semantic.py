"""Semantic search: embeddings + vector store + hybrid search.

Gated by the optional `papyrus[semantic]` extra. Core Papyrus never
imports `sentence_transformers` or `numpy` at module load — heavy
imports happen inside `SentenceTransformerEncoder` and `VectorStore`
to keep the lightweight install path usable.
"""

from __future__ import annotations

import hashlib

from papyrus.models import Need


def content_hash(need: Need) -> str:
    """Stable sha256 over the semantically meaningful fields."""
    parts = [
        need.title,
        need.body,
        "\n".join(sorted(need.tags)),
    ]
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


class VectorStore:
    """Numpy-backed sidecar store for per-need embedding vectors.

    Layout under `<workspace>/.papyrus/`:
      - `vectors.npy`        — float32 array, shape (N, dim), rows L2-normalised
      - `vectors_meta.json`  — {"model": str, "dim": int, "entries": [{id, hash}]}

    Model mismatch on load is treated as a full invalidation — the old
    vectors are dropped in memory, not deleted from disk until the next
    save(). Callers should rebuild after a mismatch.

    **Thread safety:** Not thread-safe. Callers must serialise upsert / delete /
    save across threads or processes (Papyrus uses ``FileLock`` in
    ``RSTBackend.rebuild_index``, which is the only production call site).
    """

    def __init__(self, base: Path, *, model: str, dim: int) -> None:
        import numpy as np

        self.base = Path(base)
        self.model = model
        self.dim = dim
        self._np = np
        self._matrix: np.ndarray = np.zeros((0, dim), dtype=np.float32)
        self._ids: list[str] = []
        self._hashes: dict[str, str] = {}
        self._load()

    @property
    def npy_path(self) -> Path:
        return self.base / "vectors.npy"

    @property
    def meta_path(self) -> Path:
        return self.base / "vectors_meta.json"

    def _load(self) -> None:
        if not self.meta_path.exists() or not self.npy_path.exists():
            return
        try:
            meta = json.loads(self.meta_path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        if meta.get("model") != self.model or meta.get("dim") != self.dim:
            return  # invalidate silently; next save() rewrites both files
        self._ids = [e["id"] for e in meta.get("entries", [])]
        self._hashes = {e["id"]: e["hash"] for e in meta.get("entries", [])}
        matrix = self._np.load(self.npy_path)
        if matrix.shape != (len(self._ids), self.dim):
            # Corrupt — reset.
            self._ids = []
            self._hashes = {}
            return
        self._matrix = matrix.astype(self._np.float32, copy=False)

    def ids(self) -> list[str]:
        return list(self._ids)

    def hash_of(self, need_id: str) -> str | None:
        return self._hashes.get(need_id)

    def matrix(self) -> "np.ndarray":
        """Return the internal (N, dim) matrix. DO NOT MUTATE — live view for read-only cosine search."""
        return self._matrix

    def upsert(self, items: list[tuple[str, "np.ndarray", str]]) -> None:
        """Insert or replace (id, vector, content_hash) triples in memory."""
        for need_id, vec, content_hash_ in items:
            if vec.shape != (self.dim,):
                raise ValueError(f"vector for {need_id!r} has shape {vec.shape}, expected ({self.dim},)")
            normalised = vec.astype(self._np.float32, copy=False)
            if need_id in self._hashes:
                idx = self._ids.index(need_id)
                self._matrix[idx] = normalised
            else:
                self._ids.append(need_id)
                self._matrix = self._np.vstack([self._matrix, normalised[None, :]])
            self._hashes[need_id] = content_hash_

    def delete(self, need_ids: list[str]) -> None:
        for nid in need_ids:
            if nid in self._hashes:
                idx = self._ids.index(nid)
                self._matrix = self._np.delete(self._matrix, idx, axis=0)
                del self._ids[idx]
                del self._hashes[nid]

    def save(self) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        self._np.save(self.npy_path, self._matrix)
        meta = {
            "model": self.model,
            "dim": self.dim,
            "entries": [{"id": i, "hash": self._hashes[i]} for i in self._ids],
        }
        tmp = self.meta_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(meta, indent=2))
        tmp.replace(self.meta_path)
