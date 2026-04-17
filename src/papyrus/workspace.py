"""WorkspaceChain: resolve reads as union, route writes by scope.

Each scope in the chain maps to one RSTBackend at a configured path. Reads
merge needs across all backends and annotate each with its source scope.
Writes pick the backend matching the requested scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from papyrus.config import PapyrusConfig
from papyrus.models import Need, Scope
from papyrus.storage.rst import RSTBackend


@dataclass(frozen=True)
class ScopedNeed:
    """A need paired with the scope of the workspace it was loaded from."""

    need: Need
    scope: Scope


class WorkspaceChain:
    """List of (scope, backend) pairs with union-read and scoped-write."""

    def __init__(self, entries: list[tuple[Scope, RSTBackend]]) -> None:
        if not entries:
            raise ValueError("WorkspaceChain requires at least one entry")
        self._entries = entries
        self._by_scope: dict[Scope, RSTBackend] = {scope: be for scope, be in entries}
        if len(self._by_scope) != len(entries):
            raise ValueError("duplicate scope in workspace chain")

    @classmethod
    def from_config(cls, cfg: PapyrusConfig, base: Path) -> WorkspaceChain:
        entries: list[tuple[Scope, RSTBackend]] = []
        for ws in cfg.workspaces:
            resolved = ws.resolved_path(base)
            entries.append((ws.scope, RSTBackend(resolved)))
        return cls(entries)

    def initialize_all(self) -> None:
        """Run init_workspace on every backend (idempotent)."""
        for _, backend in self._entries:
            backend.init_workspace(backend.workspace)

    def list_scopes(self) -> list[Scope]:
        return [scope for scope, _ in self._entries]

    def backend_for(self, scope: Scope) -> RSTBackend:
        """Return the backend registered for `scope`. Raises KeyError if absent."""
        if scope not in self._by_scope:
            raise KeyError(f"no workspace configured for scope {scope.value!r}")
        return self._by_scope[scope]

    def resolve_write(self, scope: Scope) -> RSTBackend:
        """Route a write to the backend for `scope`."""
        return self.backend_for(scope)

    def resolve_read(self) -> list[ScopedNeed]:
        """Union of all needs across the chain, annotated with source scope."""
        out: list[ScopedNeed] = []
        for scope, backend in self._entries:
            for need in backend.load_needs():
                out.append(ScopedNeed(need=need, scope=scope))
        return out

    def find_by_id(self, need_id: str) -> ScopedNeed | None:
        """Search all workspaces for a need. Returns first match (lowest scope first)."""
        for scope, backend in self._entries:
            hit = backend.find_by_id(need_id)
            if hit is not None:
                return ScopedNeed(need=hit, scope=scope)
        return None
