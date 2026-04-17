"""Tests for graph traversal primitives (impact, trace)."""
from papyrus.graph import Edge, Node, impact_walk


def _node(nid: str, **adj: list[str]) -> Node:
    return Node(id=nid, title=nid, kind="mem", edges=[Edge(type=t, target=tgt) for t, ts in adj.items() for tgt in ts])


def test_impact_walk_returns_start_at_depth_zero():
    g = {"A": _node("A")}
    hits = impact_walk(g, start="A", depth=3, link_types=None)
    assert [h.node.id for h in hits] == ["A"]
    assert hits[0].distance == 0


def test_impact_walk_bfs_expands_one_hop():
    g = {
        "A": _node("A", relates=["B", "C"]),
        "B": _node("B"),
        "C": _node("C"),
    }
    hits = impact_walk(g, start="A", depth=1, link_types=None)
    ids = sorted(h.node.id for h in hits)
    assert ids == ["A", "B", "C"]
    at_one = {h.node.id for h in hits if h.distance == 1}
    assert at_one == {"B", "C"}


def test_impact_walk_respects_depth_limit():
    g = {
        "A": _node("A", relates=["B"]),
        "B": _node("B", relates=["C"]),
        "C": _node("C"),
    }
    hits = impact_walk(g, start="A", depth=1, link_types=None)
    assert {h.node.id for h in hits} == {"A", "B"}


def test_impact_walk_follows_reverse_edges():
    # D <-satisfies- A. Starting from D must still find A.
    g = {
        "A": _node("A", satisfies=["D"]),
        "D": _node("D"),
    }
    hits = impact_walk(g, start="D", depth=2, link_types=None)
    assert {h.node.id for h in hits} == {"A", "D"}


def test_impact_walk_filters_by_link_type():
    g = {
        "A": _node("A", satisfies=["D"], relates=["E"]),
        "D": _node("D"),
        "E": _node("E"),
    }
    hits = impact_walk(g, start="A", depth=1, link_types=["satisfies"])
    assert {h.node.id for h in hits} == {"A", "D"}


def test_impact_walk_handles_cycles():
    g = {
        "A": _node("A", relates=["B"]),
        "B": _node("B", relates=["A"]),
    }
    hits = impact_walk(g, start="A", depth=5, link_types=None)
    assert {h.node.id for h in hits} == {"A", "B"}


def test_impact_walk_missing_start_raises():
    import pytest
    with pytest.raises(KeyError):
        impact_walk({}, start="X", depth=1, link_types=None)
