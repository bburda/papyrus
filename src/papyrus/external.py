"""Read-only index over a pharaoh (sphinx-needs) needs.json file.

Papyrus uses this as a target for memory-to-requirement links and as an
extension of the impact graph. It never writes — pharaoh owns its own
storage.

Schema: sphinx-needs produces `{"versions": {"<ver>": {"needs": {...}}}}`.
We pick the highest version key using natural-number sort so "1.10" beats
"1.9" — matches typical sphinx-needs release numbering.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

from papyrus.graph import Edge, Node

_VERSION_PART = re.compile(r"\d+|\D+")


def _version_sort_key(v: str) -> tuple[tuple[int, int | str], ...]:
    """Natural-sort key: '1.10' > '1.9'; chunks are wrapped in (rank, value)
    pairs so tuple comparison never hits str-vs-int TypeError.

    rank=0 for string chunks, rank=1 for integer chunks. This means strings
    sort below ints at the same position — matches the intuition that
    'v1.9' < '1.9' when treated as version keys.
    """
    parts: list[tuple[int, int | str]] = []
    for p in _VERSION_PART.findall(v):
        if p.isdigit():
            parts.append((1, int(p)))
        else:
            parts.append((0, p))
    return tuple(parts)

_KNOWN_LINK_FIELDS: tuple[str, ...] = (
    "satisfies",
    "realizes",
    "derived_from",
    "extends",
    "depends_on",
    "supersedes",
    "contradicts",
    "relates",
)


class ExternalLoadError(ValueError):
    """Raised when a needs.json file is missing or malformed."""


class ExternalNeedsIndex:
    """In-memory lookup of external pharaoh needs by id."""

    def __init__(self, nodes: dict[str, Node]) -> None:
        self._nodes = nodes

    @classmethod
    def from_needs_json(cls, path: Path) -> ExternalNeedsIndex:
        if not path.is_file():
            raise ExternalLoadError(f"needs.json not found: {path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ExternalLoadError(f"malformed JSON in {path}: {e}") from e

        versions = raw.get("versions")
        if not isinstance(versions, dict) or not versions:
            raise ExternalLoadError(f"no 'versions' section in {path}")

        latest_key = max(versions.keys(), key=_version_sort_key)
        needs_dict = versions[latest_key].get("needs")
        if not isinstance(needs_dict, dict):
            raise ExternalLoadError(f"no needs under versions['{latest_key}'] in {path}")

        nodes: dict[str, Node] = {}
        for nid, raw_need in needs_dict.items():
            edges: list[Edge] = []
            # "links" is sphinx-needs' untyped generic link list; map to "relates".
            for target in raw_need.get("links", []) or []:
                edges.append(Edge(type="relates", target=str(target)))
            for field in _KNOWN_LINK_FIELDS:
                if field == "relates":
                    continue  # already handled above via "links"
                for target in raw_need.get(field, []) or []:
                    edges.append(Edge(type=field, target=str(target)))
            nodes[nid] = Node(
                id=nid,
                title=str(raw_need.get("title", nid)),
                kind="external",
                edges=edges,
            )
        return cls(nodes)

    def has_id(self, need_id: str) -> bool:
        return need_id in self._nodes

    def get(self, need_id: str) -> Node | None:
        return self._nodes.get(need_id)

    def iter_nodes(self) -> Iterator[Node]:
        return iter(self._nodes.values())
