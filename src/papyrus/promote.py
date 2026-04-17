"""Cross-workspace promote: move a need from one scope to a higher one.

Gating rules (from PromoteConfig):
- to_program_requires_confidence: need.confidence must meet/exceed
- to_org_requires_confidence: same for org
- to_org_requires_human_review: a flag (checked by the caller, not enforced here —
  CLI will surface a warning)

On success: appends need to target backend, removes from source.
On validation failure: raises PromoteError, no mutation.
"""
from __future__ import annotations

import contextlib

from filelock import FileLock

from papyrus.config import PromoteConfig
from papyrus.models import Confidence, Need, Scope
from papyrus.storage.rst import (  # noqa: PLC2701
    _FILE_BY_TYPE,
    _SECTION_HEADER,
    RSTBackend,
    _render_need,
)
from papyrus.workspace import ScopedNeed, WorkspaceChain


class PromoteError(ValueError):
    """Raised when a promote cannot proceed (validation or config issue)."""


_CONFIDENCE_RANK = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}


def _at_least(actual: Confidence, required: Confidence) -> bool:
    return _CONFIDENCE_RANK[actual] >= _CONFIDENCE_RANK[required]


def promote(
    chain: WorkspaceChain,
    need_id: str,
    *,
    target_scope: Scope,
    promote_cfg: PromoteConfig | None = None,
) -> ScopedNeed:
    """Move the named need to `target_scope`. Returns the resulting ScopedNeed."""
    hit = chain.find_by_id(need_id)
    if hit is None:
        raise PromoteError(f"{need_id!r} not found in any workspace")

    if hit.scope == target_scope:
        raise PromoteError(f"{need_id!r} already at scope {target_scope.value!r}")

    if target_scope not in chain.list_scopes():
        raise PromoteError(f"no workspace configured for target scope {target_scope.value!r}")

    cfg = promote_cfg or PromoteConfig()
    required = _required_confidence(target_scope, cfg)
    if required is not None and not _at_least(hit.need.confidence, required):
        raise PromoteError(
            f"{need_id!r} has confidence={hit.need.confidence.value!r}, "
            f"but target scope {target_scope.value!r} requires {required.value!r}"
        )

    src_backend = chain.backend_for(hit.scope)
    dst_backend = chain.backend_for(target_scope)

    copy = _with_scope(hit.need, target_scope)
    dst_backend.append_need(copy)
    try:
        _delete_from_backend(src_backend, need_id)
    except Exception:
        # Rollback: remove the need we just added to dst. If rollback itself
        # fails, swallow that error and re-raise the original so the caller
        # sees the true root cause.
        with contextlib.suppress(Exception):
            _delete_from_backend(dst_backend, need_id)
        raise

    return ScopedNeed(need=copy, scope=target_scope)


def _required_confidence(target: Scope, cfg: PromoteConfig) -> Confidence | None:
    if target == Scope.PROGRAM:
        return cfg.to_program_requires_confidence
    if target == Scope.ORG:
        return cfg.to_org_requires_confidence
    return None


def _with_scope(need: Need, scope: Scope) -> Need:
    return need.model_copy(update={"scope": scope})


def _delete_from_backend(backend: RSTBackend, need_id: str) -> None:
    """Remove a need by rewriting its type-specific file without it."""
    with FileLock(str(backend.lock_path), timeout=30):
        existing = backend.load_needs()
        target = next((n for n in existing if n.id == need_id), None)
        if target is None:
            return  # nothing to delete
        remaining = [n for n in existing if n.id != need_id]
        plural = _FILE_BY_TYPE[target.type]
        rst_path = backend.memory_dir / f"{plural}.rst"
        same_type = [n for n in remaining if n.type == target.type]
        header = _SECTION_HEADER[plural]
        body = "\n\n".join(_render_need(n) for n in same_type)
        rst_path.write_text(header + "\n" + (body + "\n" if body else ""), encoding="utf-8")
