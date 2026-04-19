"""Tests for papyrus.semantic. FakeEncoder keeps tests dep-free."""
from __future__ import annotations

from datetime import UTC, datetime

from papyrus.models import Need, NeedType
from papyrus.semantic import content_hash


def _need(nid: str, ntype: NeedType, **extra: object) -> Need:
    now = datetime.now(UTC)
    return Need(
        id=nid, type=ntype, title=nid.replace("_", " "),
        created_at=now, updated_at=now, **extra,  # type: ignore[arg-type]
    )


def test_content_hash_stable_for_same_inputs() -> None:
    n = _need("FACT_temp", NeedType.FACT, body="sensor reads celsius", tags=["topic:thermal"])
    assert content_hash(n) == content_hash(n)


def test_content_hash_changes_on_body_change() -> None:
    a = _need("FACT_temp", NeedType.FACT, body="sensor reads celsius")
    b = _need("FACT_temp", NeedType.FACT, body="sensor reads fahrenheit")
    assert content_hash(a) != content_hash(b)


def test_content_hash_independent_of_tag_order() -> None:
    a = _need("FACT_temp", NeedType.FACT, tags=["topic:a", "topic:b"])
    b = _need("FACT_temp", NeedType.FACT, tags=["topic:b", "topic:a"])
    assert content_hash(a) == content_hash(b)
