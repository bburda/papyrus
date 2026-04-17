"""Typed graph traversal for impact analysis and decision-chain trace.

A Node represents either a Papyrus memory or an external (pharaoh) need. An
Edge is a typed directed link. Traversal is undirected (both outgoing and
incoming edges are followed) because "impact" is symmetric: a change to a
requirement affects linked decisions, and inspecting a decision needs the
requirements it satisfies.

This module is storage-agnostic: caller builds {id: Node} and passes it in.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Edge:
    type: str
    target: str


@dataclass(frozen=True)
class Node:
    id: str
    title: str
    kind: str  # "mem" | "external"
    edges: list[Edge] = field(default_factory=list)


@dataclass(frozen=True)
class Hit:
    node: Node
    distance: int
    path_edge_types: tuple[str, ...]


def _reverse_index(graph: dict[str, Node]) -> dict[str, list[tuple[str, str]]]:
    """For each node id, list (source_id, edge_type) of incoming edges."""
    incoming: dict[str, list[tuple[str, str]]] = {}
    for src_id, node in graph.items():
        for edge in node.edges:
            incoming.setdefault(edge.target, []).append((src_id, edge.type))
    return incoming


def impact_walk(
    graph: dict[str, Node],
    *,
    start: str,
    depth: int,
    link_types: list[str] | None,
) -> list[Hit]:
    """BFS from `start` following edges in both directions up to `depth` hops.

    When `link_types` is not None, only edges whose type is in that list are
    traversed. The start node is returned at distance 0.
    """
    if start not in graph:
        raise KeyError(f"start node {start!r} not in graph")

    allowed = set(link_types) if link_types is not None else None
    incoming = _reverse_index(graph)
    visited: dict[str, Hit] = {start: Hit(node=graph[start], distance=0, path_edge_types=())}
    queue: deque[tuple[str, tuple[str, ...]]] = deque([(start, ())])

    while queue:
        current_id, path = queue.popleft()
        current_depth = len(path)
        if current_depth >= depth:
            continue
        neighbors: list[tuple[str, str]] = []
        for edge in graph[current_id].edges:
            if (allowed is None or edge.type in allowed) and edge.target in graph:
                neighbors.append((edge.target, edge.type))
        for src_id, edge_type in incoming.get(current_id, []):
            if allowed is None or edge_type in allowed:
                neighbors.append((src_id, edge_type))

        for neighbor_id, edge_type in neighbors:
            if neighbor_id in visited:
                continue
            new_path = path + (edge_type,)
            visited[neighbor_id] = Hit(
                node=graph[neighbor_id],
                distance=current_depth + 1,
                path_edge_types=new_path,
            )
            queue.append((neighbor_id, new_path))

    return sorted(visited.values(), key=lambda h: (h.distance, h.node.id))
