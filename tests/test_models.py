"""Tests for Pydantic data models."""
from datetime import UTC, datetime, timezone

import pytest
from pydantic import ValidationError

from papyrus.models import (
    Confidence,
    Link,
    LinkType,
    Need,
    NeedType,
    Scope,
    Status,
)


def test_need_type_values() -> None:
    assert {t.value for t in NeedType} == {"mem", "dec", "fact", "pref", "risk", "goal", "q"}


def test_confidence_values() -> None:
    assert {c.value for c in Confidence} == {"low", "medium", "high"}


def test_scope_values() -> None:
    assert {s.value for s in Scope} == {"local", "program", "org"}


def test_link_type_values() -> None:
    expected = {"relates", "supports", "depends", "supersedes", "contradicts", "extends", "derives", "satisfies"}
    assert {lt.value for lt in LinkType} == expected


def test_status_values() -> None:
    assert {s.value for s in Status} == {"active", "promoted", "deprecated", "review", "draft"}


def test_need_minimal_construction() -> None:
    now = datetime.now(UTC)
    need = Need(
        id="FACT_example",
        type=NeedType.FACT,
        title="Example fact",
        created_at=now,
        updated_at=now,
    )
    assert need.body == ""
    assert need.tags == []
    assert need.links == []
    assert need.confidence == Confidence.MEDIUM
    assert need.scope == Scope.LOCAL
    assert need.status == Status.ACTIVE
    assert need.review_after is None
    assert need.source == ""


def test_need_with_links() -> None:
    now = datetime.now(UTC)
    need = Need(
        id="DEC_example",
        type=NeedType.DEC,
        title="Example decision",
        body="We chose X because Y.",
        tags=["topic:arch", "scope:papyrus"],
        confidence=Confidence.HIGH,
        created_at=now,
        updated_at=now,
        links=[
            Link(type=LinkType.RELATES, target="FACT_example"),
            Link(type=LinkType.SUPERSEDES, target="DEC_old"),
        ],
    )
    assert len(need.links) == 2
    assert need.links[0].type == LinkType.RELATES


def test_need_id_must_match_type_prefix() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        Need(
            id="WRONG_prefix",
            type=NeedType.FACT,
            title="x",
            created_at=now,
            updated_at=now,
        )


def test_need_title_required() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        Need(
            id="FACT_x",
            type=NeedType.FACT,
            title="",
            created_at=now,
            updated_at=now,
        )


def test_link_serialization_roundtrip() -> None:
    link = Link(type=LinkType.RELATES, target="FACT_x")
    data = link.model_dump()
    assert data == {"type": "relates", "target": "FACT_x"}
    restored = Link.model_validate(data)
    assert restored == link


def test_link_type_satisfies_exists() -> None:
    from papyrus.models import LinkType
    assert LinkType.SATISFIES.value == "satisfies"


def test_need_can_have_satisfies_link() -> None:
    now = datetime.now(UTC)
    need = Need(
        id="DEC_auth_choice",
        type=NeedType.DEC,
        title="Use JWT",
        created_at=now,
        updated_at=now,
        links=[Link(type=LinkType.SATISFIES, target="REQ_042")],
    )
    assert need.links[0].type == LinkType.SATISFIES
    assert need.links[0].target == "REQ_042"
