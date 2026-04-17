"""Cross-reference validation for needs links.

Link type enum lives in `papyrus.models` (shared with Need). This module adds
validation: every link target must exist in the corpus.
"""
from __future__ import annotations

from collections.abc import Iterable

from papyrus.models import Need


class UnknownTargetError(ValueError):
    """Raised when a link references an ID not present in the corpus."""


def validate_links(needs: Iterable[Need]) -> None:
    """Ensure every link's target exists in the provided corpus.

    Raises:
        UnknownTargetError: if any link references an unknown ID.
    """
    corpus = list(needs)
    known_ids = {n.id for n in corpus}
    for n in corpus:
        for link in n.links:
            if link.target not in known_ids:
                raise UnknownTargetError(
                    f"{n.id} -> {link.type.value} -> {link.target!r} (target not in corpus)"
                )
