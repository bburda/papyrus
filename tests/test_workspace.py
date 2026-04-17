"""Tests for WorkspaceChain (multi-workspace read/write routing)."""
from datetime import UTC, datetime, timezone
from pathlib import Path

import pytest

from papyrus.config import PapyrusConfig, Preset, WorkspaceSpec
from papyrus.models import Need, NeedType, Scope
from papyrus.workspace import WorkspaceChain


def _need(nid: str, ntype: NeedType) -> Need:
    now = datetime.now(UTC)
    return Need(id=nid, type=ntype, title=nid, created_at=now, updated_at=now)


def _config(tmp_path: Path, *pairs: tuple[str, Scope]) -> PapyrusConfig:
    workspaces = [WorkspaceSpec(path=str(tmp_path / name), scope=scope) for name, scope in pairs]
    return PapyrusConfig(
        preset=Preset.CUSTOM,
        default_write=workspaces[0].scope,
        workspaces=workspaces,
    )


def test_chain_from_config_initializes_all_workspaces(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ("local_ws", Scope.LOCAL), ("prog_ws", Scope.PROGRAM))
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    chain.initialize_all()
    assert (tmp_path / "local_ws" / "conf.py").is_file()
    assert (tmp_path / "prog_ws" / "conf.py").is_file()


def test_resolve_read_union_across_workspaces(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ("local_ws", Scope.LOCAL), ("prog_ws", Scope.PROGRAM))
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    chain.initialize_all()

    chain.backend_for(Scope.LOCAL).append_need(_need("FACT_local", NeedType.FACT))
    chain.backend_for(Scope.PROGRAM).append_need(_need("FACT_program", NeedType.FACT))

    result = chain.resolve_read()
    ids = {sn.need.id: sn.scope for sn in result}
    assert ids == {"FACT_local": Scope.LOCAL, "FACT_program": Scope.PROGRAM}


def test_resolve_write_routes_to_scope(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ("local_ws", Scope.LOCAL), ("prog_ws", Scope.PROGRAM))
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    chain.initialize_all()

    target = chain.resolve_write(Scope.PROGRAM)
    target.append_need(_need("FACT_x", NeedType.FACT))
    assert any("FACT_x" in (tmp_path / "prog_ws" / "memory" / f"{p}.rst").read_text()
               for p in ("facts",))


def test_resolve_write_unknown_scope_raises(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ("local_ws", Scope.LOCAL))
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    chain.initialize_all()
    with pytest.raises(KeyError):
        chain.resolve_write(Scope.ORG)


def test_list_scopes_returns_declared(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ("a", Scope.LOCAL), ("b", Scope.PROGRAM))
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    assert chain.list_scopes() == [Scope.LOCAL, Scope.PROGRAM]


def test_find_by_id_searches_all_workspaces(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ("local_ws", Scope.LOCAL), ("prog_ws", Scope.PROGRAM))
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    chain.initialize_all()
    chain.backend_for(Scope.PROGRAM).append_need(_need("DEC_x", NeedType.DEC))

    hit = chain.find_by_id("DEC_x")
    assert hit is not None
    assert hit.scope == Scope.PROGRAM
    assert hit.need.id == "DEC_x"

    miss = chain.find_by_id("DEC_ghost")
    assert miss is None
