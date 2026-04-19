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


from typing import Protocol, runtime_checkable


@runtime_checkable
class Encoder(Protocol):
    """Anything that turns a list of strings into an (N, dim) float32 matrix of L2-unit vectors."""

    dim: int

    def encode(self, texts: list[str]) -> "np.ndarray": ...


class FakeEncoder:
    """Test-only deterministic encoder. Maps keywords to named axes."""

    def __init__(self, *, axes: list[str], keyword_map: dict[str, list[str]]) -> None:
        import numpy as np

        self._np = np
        self.dim = len(axes)
        self._axis_index = {axis: i for i, axis in enumerate(axes)}
        self._keyword_to_axis: dict[str, int] = {}
        for axis, keywords in keyword_map.items():
            if axis not in self._axis_index:
                raise ValueError(f"axis {axis!r} not in axes")
            for kw in keywords:
                self._keyword_to_axis[kw.casefold()] = self._axis_index[axis]

    def encode(self, texts: list[str]) -> "np.ndarray":
        out = self._np.zeros((len(texts), self.dim), dtype=self._np.float32)
        for row, text in enumerate(texts):
            lowered = text.casefold()
            for kw, axis in self._keyword_to_axis.items():
                if kw in lowered:
                    out[row, axis] += 1.0
        # L2 normalise; zero vectors stay zero
        norms = self._np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_DEFAULT_DIM = 384


class SentenceTransformerEncoder:
    """Production encoder. Requires `pip install papyrus[semantic]`.

    Import of `sentence_transformers` is deferred to __init__ so the
    module-level import graph stays lightweight.
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "papyrus semantic features require the 'semantic' extra. "
                "Install with: pip install papyrus[semantic]"
            ) from e
        self._model = SentenceTransformer(model_name)
        self._model_name = model_name
        # sentence-transformers exposes .get_sentence_embedding_dimension()
        self.dim = int(self._model.get_sentence_embedding_dimension())

    @property
    def model_name(self) -> str:
        return self._model_name

    def encode(self, texts: list[str]) -> "np.ndarray":
        import numpy as np

        arr = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return arr.astype(np.float32, copy=False)

from collections.abc import Iterable


def _need_text(need: Need) -> str:
    parts = [need.title, need.body]
    if need.tags:
        parts.append(" ".join(need.tags))
    return "\n".join(p for p in parts if p)


class SemanticIndex:
    """Orchestrates incremental embedding + similarity search."""

    def __init__(
        self,
        base: Path,
        *,
        encoder: Encoder,
        model_name: str | None = None,
    ) -> None:
        self.base = Path(base)
        self.encoder = encoder
        self.model_name = model_name or getattr(encoder, "model_name", _DEFAULT_MODEL)
        self.store = VectorStore(self.base, model=self.model_name, dim=encoder.dim)

    def reindex(self, needs: Iterable[Need]) -> int:
        """Re-embed any need whose content_hash changed. Drop orphans. Return count changed."""
        needs_list = list(needs)
        current_ids = {n.id for n in needs_list}
        orphans = [nid for nid in self.store.ids() if nid not in current_ids]
        if orphans:
            self.store.delete(orphans)

        to_embed: list[tuple[str, Need]] = []
        for n in needs_list:
            h = content_hash(n)
            if self.store.hash_of(n.id) != h:
                to_embed.append((n.id, n))
        if not to_embed:
            if orphans:
                self.store.save()
            return 0

        texts = [_need_text(n) for _, n in to_embed]
        vectors = self.encoder.encode(texts)
        items: list[tuple[str, "np.ndarray", str]] = [
            (nid, vectors[row], content_hash(n)) for row, (nid, n) in enumerate(to_embed)
        ]
        self.store.upsert(items)
        self.store.save()
        return len(to_embed)
