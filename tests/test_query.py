"""Tests for progressive-disclosure query renderer."""
from datetime import UTC, datetime, timezone

from papyrus.models import Confidence, Link, LinkType, Need, NeedType
from papyrus.query import QueryFormat, filter_needs, render


def _need(nid: str, ntype: NeedType, **extra: object) -> Need:
    now = datetime.now(UTC)
    return Need(id=nid, type=ntype, title=nid.replace("_", " "), created_at=now, updated_at=now, **extra)  # type: ignore[arg-type]


def test_render_brief_one_line_per_need() -> None:
    needs = [_need("FACT_a", NeedType.FACT), _need("DEC_b", NeedType.DEC)]
    out = render(needs, QueryFormat.BRIEF)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "FACT_a" in lines[0]
    assert "DEC_b" in lines[1]


def test_render_compact_includes_tags_and_confidence() -> None:
    n = _need("FACT_a", NeedType.FACT, tags=["topic:demo"], confidence=Confidence.HIGH)
    out = render([n], QueryFormat.COMPACT)
    assert "topic:demo" in out
    assert "high" in out


def test_render_full_includes_body_and_links() -> None:
    n = _need(
        "DEC_x",
        NeedType.DEC,
        body="rationale text",
        links=[Link(type=LinkType.RELATES, target="FACT_a")],
    )
    out = render([n], QueryFormat.FULL)
    assert "rationale text" in out
    assert "relates" in out
    assert "FACT_a" in out


def test_filter_by_tag_and() -> None:
    a = _need("FACT_a", NeedType.FACT, tags=["topic:x", "scope:y"])
    b = _need("FACT_b", NeedType.FACT, tags=["topic:x"])
    result = filter_needs([a, b], tags=["topic:x", "scope:y"])
    assert [n.id for n in result] == ["FACT_a"]


def test_filter_by_type() -> None:
    a = _need("FACT_a", NeedType.FACT)
    b = _need("DEC_b", NeedType.DEC)
    result = filter_needs([a, b], type=NeedType.DEC)
    assert [n.id for n in result] == ["DEC_b"]


def test_filter_by_query_substring_matches_title_or_body() -> None:
    a = _need("FACT_a", NeedType.FACT, body="ecu safety")
    b = _need("FACT_b", NeedType.FACT, body="unrelated")
    result = filter_needs([a, b], query="ecu")
    assert [n.id for n in result] == ["FACT_a"]


def test_filter_combined_tag_and_query() -> None:
    a = _need("FACT_a", NeedType.FACT, tags=["topic:x"], body="ecu")
    b = _need("FACT_b", NeedType.FACT, tags=["topic:x"], body="motor")
    result = filter_needs([a, b], tags=["topic:x"], query="ecu")
    assert [n.id for n in result] == ["FACT_a"]


def test_render_brief_with_scope_annotation() -> None:
    from papyrus.models import Scope
    n = _need("FACT_a", NeedType.FACT)
    out = render([n], QueryFormat.BRIEF, scope_by_id={"FACT_a": Scope.PROGRAM})
    assert "[from: program]" in out


def test_render_full_with_scope_annotation() -> None:
    from papyrus.models import Scope
    n = _need("DEC_x", NeedType.DEC, body="rationale")
    out = render([n], QueryFormat.FULL, scope_by_id={"DEC_x": Scope.ORG})
    assert "from: org" in out
