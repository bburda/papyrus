"""Tests for link cross-reference validation."""
from datetime import UTC, datetime, timezone

import pytest

from papyrus.links import UnknownTargetError, validate_links
from papyrus.models import Link, LinkType, Need, NeedType


def _need(nid: str, ntype: NeedType) -> Need:
    now = datetime.now(UTC)
    return Need(id=nid, type=ntype, title=nid, created_at=now, updated_at=now)


def test_validate_links_all_targets_known() -> None:
    a = _need("FACT_a", NeedType.FACT)
    b = _need("DEC_b", NeedType.DEC)
    b.links.append(Link(type=LinkType.RELATES, target="FACT_a"))
    # Must not raise
    validate_links([a, b])


def test_validate_links_unknown_target() -> None:
    a = _need("FACT_a", NeedType.FACT)
    a.links.append(Link(type=LinkType.SUPPORTS, target="GHOST_x"))
    with pytest.raises(UnknownTargetError) as ei:
        validate_links([a])
    assert "GHOST_x" in str(ei.value)
    assert "FACT_a" in str(ei.value)


def test_validate_links_empty_corpus() -> None:
    # No needs → trivially valid
    validate_links([])


def test_validate_links_self_reference_allowed() -> None:
    # A need linking to itself is silly but not a cross-ref error (caller can forbid separately).
    a = _need("FACT_a", NeedType.FACT)
    a.links.append(Link(type=LinkType.EXTENDS, target="FACT_a"))
    validate_links([a])
