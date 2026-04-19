"""Progressive-disclosure query: filter + render needs at 3 levels.

BRIEF:   one-liner per need (id | type | title) — ~50 tokens each
COMPACT: + tags + confidence + status — ~100 tokens each
FULL:    + body + links + metadata — ~500+ tokens each

Filter supports: tag AND (all tags must be present), exact type, substring query
against title+body. Any combination.
"""
from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from papyrus.models import Need, NeedType, Scope


class QueryFormat(str, Enum):
    BRIEF = "brief"
    COMPACT = "compact"
    FULL = "full"


def filter_needs(
    needs: Iterable[Need],
    *,
    tags: list[str] | None = None,
    type: NeedType | None = None,
    query: str | None = None,
) -> list[Need]:
    """Return needs matching ALL supplied filters."""
    out: list[Need] = []
    needle = query.casefold() if query else None
    for n in needs:
        if tags and not all(t in n.tags for t in tags):
            continue
        if type is not None and n.type is not type:
            continue
        if needle is not None and needle not in n.title.casefold() and needle not in n.body.casefold():
            continue
        out.append(n)
    return out


def render(
    needs: Iterable[Need],
    fmt: QueryFormat,
    *,
    scope_by_id: dict[str, Scope] | None = None,
) -> str:
    needs = list(needs)
    if not needs:
        return "(no needs match)"
    annotations = scope_by_id or {}
    if fmt is QueryFormat.BRIEF:
        return "\n".join(_render_brief(n, annotations.get(n.id)) for n in needs)
    if fmt is QueryFormat.COMPACT:
        return "\n".join(_render_compact(n, annotations.get(n.id)) for n in needs)
    return "\n\n".join(_render_full(n, annotations.get(n.id)) for n in needs)


def _render_brief(n: Need, scope: Scope | None = None) -> str:
    tail = f"  [from: {scope.value}]" if scope is not None else ""
    return f"{n.id:<40} [{n.type.value}] {n.title}{tail}"


def _render_compact(n: Need, scope: Scope | None = None) -> str:
    tag_str = ", ".join(n.tags) if n.tags else "-"
    tail = f"   [from: {scope.value}]" if scope is not None else ""
    return (
        f"{n.id:<40} [{n.type.value}] conf={n.confidence.value:<6} "
        f"status={n.status.value:<10} tags={tag_str}{tail}\n"
        f"  {n.title}"
    )


def _render_full(n: Need, scope: Scope | None = None) -> str:
    lines = [
        f"# {n.id}",
        f"Type: {n.type.value}   Status: {n.status.value}   Confidence: {n.confidence.value}   Scope: {n.scope.value}",
    ]
    if scope is not None:
        lines.append(f"Loaded from: {scope.value}")
    lines.append(f"Title: {n.title}")
    if n.tags:
        lines.append(f"Tags: {', '.join(n.tags)}")
    lines.append(f"Created: {n.created_at.isoformat()}   Updated: {n.updated_at.isoformat()}")
    if n.review_after:
        lines.append(f"Review after: {n.review_after.isoformat()}")
    if n.source:
        lines.append(f"Source: {n.source}")
    if n.links:
        lines.append("Links:")
        for lk in n.links:
            lines.append(f"  - {lk.type.value} -> {lk.target}")
    if n.body:
        lines.append("")
        lines.append(n.body)
    return "\n".join(lines)


def render_with_scores(
    hits: list[tuple[Need, float]],
    fmt: QueryFormat,
    *,
    scope_by_id: dict[str, Scope] | None = None,
    show_scores: bool = True,
) -> str:
    """Render semantic hits, optionally prefixing each line with the similarity score."""
    if not hits:
        return "(no needs match)"
    if not show_scores:
        return render([n for n, _ in hits], fmt, scope_by_id=scope_by_id)
    annotations = scope_by_id or {}
    if fmt is QueryFormat.BRIEF:
        return "\n".join(
            f"{score:.2f}  " + _render_brief(n, annotations.get(n.id))
            for n, score in hits
        )
    if fmt is QueryFormat.COMPACT:
        return "\n".join(
            f"[score={score:.3f}]\n" + _render_compact(n, annotations.get(n.id))
            for n, score in hits
        )
    return "\n\n".join(
        f"[score={score:.3f}]\n" + _render_full(n, annotations.get(n.id))
        for n, score in hits
    )
