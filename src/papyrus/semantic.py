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
