"""Abstract StorageBackend interface.

Backends implement this contract. No logic here — interface only. Tests
live with concrete implementations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from papyrus.models import Need


class StorageBackend(ABC):
    """Contract for a Papyrus storage backend."""

    @abstractmethod
    def init_workspace(self, path: Path) -> None:
        """Scaffold a new workspace at `path`.

        Idempotent: safe to call on existing workspace (no overwrite).
        Raises FileExistsError if path exists and is non-empty.
        """

    @abstractmethod
    def load_needs(self) -> list[Need]:
        """Return all needs in the workspace (order by created_at ascending)."""

    @abstractmethod
    def find_by_id(self, need_id: str) -> Need | None:
        """Return the need with matching id, or None."""

    @abstractmethod
    def append_need(self, need: Need) -> None:
        """Append a new need. Raises ValueError if id already exists."""

    @abstractmethod
    def update_need(self, need_id: str, **fields: object) -> Need:
        """Update mutable fields of an existing need.

        Allowed fields: status, confidence, scope, review_after, source, tags,
        body, title, links.
        Immutable: id, type, created_at.
        Automatically refreshes updated_at.
        Returns the updated need. Raises KeyError if id not found.
        """

    @abstractmethod
    def rebuild_index(self) -> int:
        """Refresh derived artefacts (e.g. needs.json). Returns count of needs."""
