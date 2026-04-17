"""Tests for cross-workspace promote."""
from datetime import UTC, datetime, timezone
from pathlib import Path

import pytest

import papyrus.promote as promote_mod
from papyrus.config import PapyrusConfig, Preset, PromoteConfig, WorkspaceSpec
from papyrus.models import Confidence, Link, LinkType, Need, NeedType, Scope
from papyrus.promote import PromoteError, promote
from papyrus.workspace import WorkspaceChain


def _need(nid: str, ntype: NeedType, confidence: Confidence = Confidence.HIGH, **extra: object) -> Need:
    now = datetime.now(UTC)
    return Need(id=nid, type=ntype, title=nid, confidence=confidence, created_at=now, updated_at=now, **extra)  # type: ignore[arg-type]


def _chain(tmp_path: Path, promote_cfg: PromoteConfig | None = None) -> WorkspaceChain:
    cfg = PapyrusConfig(
        preset=Preset.CUSTOM,
        default_write=Scope.LOCAL,
        workspaces=[
            WorkspaceSpec(path=str(tmp_path / "local_ws"), scope=Scope.LOCAL),
            WorkspaceSpec(path=str(tmp_path / "prog_ws"), scope=Scope.PROGRAM),
            WorkspaceSpec(path=str(tmp_path / "org_ws"), scope=Scope.ORG),
        ],
        promote=promote_cfg or PromoteConfig(),
    )
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    chain.initialize_all()
    return chain


def test_promote_local_to_program_moves_need(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    chain.backend_for(Scope.LOCAL).append_need(_need("FACT_a", NeedType.FACT))

    moved = promote(chain, "FACT_a", target_scope=Scope.PROGRAM)
    assert moved.scope == Scope.PROGRAM

    assert chain.backend_for(Scope.PROGRAM).find_by_id("FACT_a") is not None
    assert chain.backend_for(Scope.LOCAL).find_by_id("FACT_a") is None


def test_promote_preserves_links(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    chain.backend_for(Scope.LOCAL).append_need(_need("FACT_target", NeedType.FACT))
    chain.backend_for(Scope.LOCAL).append_need(
        _need("DEC_src", NeedType.DEC, links=[Link(type=LinkType.RELATES, target="FACT_target")])
    )

    promote(chain, "DEC_src", target_scope=Scope.PROGRAM)
    promoted = chain.backend_for(Scope.PROGRAM).find_by_id("DEC_src")
    assert promoted is not None
    assert len(promoted.links) == 1
    assert promoted.links[0].target == "FACT_target"


def test_promote_rejects_low_confidence_to_program(tmp_path: Path) -> None:
    chain = _chain(tmp_path, promote_cfg=PromoteConfig(to_program_requires_confidence=Confidence.HIGH))
    chain.backend_for(Scope.LOCAL).append_need(_need("FACT_low", NeedType.FACT, confidence=Confidence.LOW))
    with pytest.raises(PromoteError, match="confidence"):
        promote(chain, "FACT_low", target_scope=Scope.PROGRAM, promote_cfg=PromoteConfig(to_program_requires_confidence=Confidence.HIGH))


def test_promote_unknown_id_raises(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    with pytest.raises(PromoteError, match="not found"):
        promote(chain, "DEC_missing", target_scope=Scope.PROGRAM)


def test_promote_to_same_scope_rejected(tmp_path: Path) -> None:
    chain = _chain(tmp_path)
    chain.backend_for(Scope.LOCAL).append_need(_need("FACT_a", NeedType.FACT))
    with pytest.raises(PromoteError, match="already at scope"):
        promote(chain, "FACT_a", target_scope=Scope.LOCAL)


def test_promote_target_scope_not_configured(tmp_path: Path) -> None:
    cfg = PapyrusConfig(
        preset=Preset.CUSTOM,
        default_write=Scope.LOCAL,
        workspaces=[
            WorkspaceSpec(path=str(tmp_path / "local_ws"), scope=Scope.LOCAL),
            WorkspaceSpec(path=str(tmp_path / "prog_ws"), scope=Scope.PROGRAM),
        ],
    )
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    chain.initialize_all()
    chain.backend_for(Scope.LOCAL).append_need(_need("FACT_x", NeedType.FACT))
    with pytest.raises(PromoteError, match="no workspace"):
        promote(chain, "FACT_x", target_scope=Scope.ORG)


def test_promote_no_duplicate_on_delete_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If delete-from-source fails after append-to-dst, the need must NOT
    exist in both workspaces simultaneously."""
    chain = _chain(tmp_path)
    src_backend = chain.backend_for(Scope.LOCAL)
    dst_backend = chain.backend_for(Scope.PROGRAM)
    src_backend.append_need(_need("DEC_move", NeedType.DEC))

    real_delete = promote_mod._delete_from_backend

    def exploding_delete(backend: object, need_id: str) -> None:
        if backend is src_backend:
            raise OSError("simulated delete failure")
        real_delete(backend, need_id)  # type: ignore[arg-type]

    monkeypatch.setattr(promote_mod, "_delete_from_backend", exploding_delete)

    with pytest.raises(OSError):
        promote(chain, "DEC_move", target_scope=Scope.PROGRAM)

    in_src = src_backend.find_by_id("DEC_move") is not None
    in_dst = dst_backend.find_by_id("DEC_move") is not None
    assert not in_dst, "Rollback did not remove the need from dst_backend"
    assert in_src, "Original delete failed, so src_backend should still hold the need"
