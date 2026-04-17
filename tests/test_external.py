"""Tests for ExternalNeedsIndex (read-only pharaoh needs.json)."""
from pathlib import Path

import pytest

from papyrus.external import ExternalLoadError, ExternalNeedsIndex

FIXTURE = Path(__file__).parent / "fixtures" / "eclipse-score-sample" / "needs.json"


def test_loads_all_needs_from_fixture() -> None:
    idx = ExternalNeedsIndex.from_needs_json(FIXTURE)
    assert idx.has_id("REQ_auth")
    assert idx.has_id("REQ_session")
    assert idx.has_id("COMP_jwt")
    assert not idx.has_id("REQ_missing")


def test_node_exposes_typed_edges() -> None:
    idx = ExternalNeedsIndex.from_needs_json(FIXTURE)
    comp = idx.get("COMP_jwt")
    assert comp is not None
    edges = {(e.type, e.target) for e in comp.edges}
    assert ("satisfies", "REQ_auth") in edges


def test_node_exposes_plain_links_as_relates() -> None:
    # sphinx-needs "links" field (untyped) becomes "relates" edges.
    idx = ExternalNeedsIndex.from_needs_json(FIXTURE)
    req = idx.get("REQ_auth")
    assert req is not None
    edge_types = {e.type for e in req.edges}
    assert "relates" in edge_types


def test_iter_nodes_returns_all() -> None:
    idx = ExternalNeedsIndex.from_needs_json(FIXTURE)
    ids = {n.id for n in idx.iter_nodes()}
    assert ids == {"REQ_auth", "REQ_session", "COMP_jwt"}


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ExternalLoadError):
        ExternalNeedsIndex.from_needs_json(tmp_path / "no.json")


def test_malformed_json_raises(tmp_path: Path) -> None:
    p = tmp_path / "needs.json"
    p.write_text("{not json")
    with pytest.raises(ExternalLoadError):
        ExternalNeedsIndex.from_needs_json(p)


def test_picks_highest_version_by_natural_sort(tmp_path: Path) -> None:
    # Regression: "1.10" must beat "1.9" (lexicographic would pick "1.9").
    import json
    p = tmp_path / "needs.json"
    p.write_text(json.dumps({
        "versions": {
            "1.9":  {"needs": {"REQ_old":  {"id": "REQ_old",  "type": "req", "title": "old",  "links": []}}},
            "1.10": {"needs": {"REQ_new":  {"id": "REQ_new",  "type": "req", "title": "new",  "links": []}}},
            "1.2":  {"needs": {"REQ_older":{"id": "REQ_older","type": "req", "title": "older","links": []}}},
        }
    }))
    idx = ExternalNeedsIndex.from_needs_json(p)
    assert idx.has_id("REQ_new")
    assert not idx.has_id("REQ_old")
    assert not idx.has_id("REQ_older")


def test_version_sort_handles_alpha_prefix(tmp_path: Path) -> None:
    """Versions like 'v1.9' must not crash version-picking."""
    import json

    p = tmp_path / "needs.json"
    p.write_text(json.dumps({
        "versions": {
            "1.9":  {"needs": {"REQ_a": {"title": "A"}}},
            "v1.9": {"needs": {"REQ_b": {"title": "B"}}},
            "1.10": {"needs": {"REQ_c": {"title": "C"}}},
        }
    }))

    # Must not raise TypeError
    idx = ExternalNeedsIndex.from_needs_json(p)
    # Behaviour must at minimum be deterministic and not crash.
    assert idx.has_id("REQ_a") or idx.has_id("REQ_b") or idx.has_id("REQ_c")
