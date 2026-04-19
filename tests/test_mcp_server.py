"""Tests for Papyrus MCP server."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from mcp.types import CallToolResult, TextContent

from papyrus.config import PapyrusConfig, Preset, WorkspaceSpec
from papyrus.mcp_server import _HANDLERS, PapyrusServer, build_server
from papyrus.models import Confidence, Need, NeedType, Scope
from papyrus.workspace import WorkspaceChain


def _text(result: CallToolResult, index: int = 0) -> str:
    """Narrow CallToolResult.content[i] to TextContent and return its text.

    Handlers always return TextContent; this helper keeps pyright happy by
    asserting the narrowing instead of relying on the union type.
    """
    block = result.content[index]
    assert isinstance(block, TextContent), f"expected TextContent, got {type(block).__name__}"
    return block.text


def _chain(tmp_path: Path) -> tuple[WorkspaceChain, PapyrusConfig]:
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
    return chain, cfg


def test_server_has_expected_tool_names(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    server = PapyrusServer(chain, cfg)
    names = set(server.tool_names())
    assert names == {
        "memory_recall", "memory_get", "memory_add", "memory_update",
        "memory_deprecate", "memory_tags", "memory_stale", "memory_rebuild",
        "memory_promote", "memory_link", "memory_impact", "memory_trace",
    }


def test_build_server_returns_mcp_server(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    srv = build_server(chain, cfg)
    assert srv.name == "papyrus"


def _add(chain, scope, nid, ntype, **extra):
    now = datetime.now(UTC)
    need = Need(
        id=nid, type=ntype, title=nid, created_at=now, updated_at=now, **extra,
    )
    chain.backend_for(scope).append_need(need)


async def test_memory_recall_brief(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_a", NeedType.FACT, tags=["topic:x"])
    _add(chain, Scope.PROGRAM, "DEC_b", NeedType.DEC)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_recall"]
    result = await handler(srv, {"format": "brief"})
    assert result.isError is False
    text = result.content[0].text
    assert "FACT_a" in text
    assert "DEC_b" in text


async def test_memory_recall_filter_by_tag(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_a", NeedType.FACT, tags=["topic:x"])
    _add(chain, Scope.LOCAL, "FACT_b", NeedType.FACT, tags=["topic:y"])
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_recall"]
    result = await handler(srv, {"tags": ["topic:x"]})
    assert result.isError is False
    assert "FACT_a" in result.content[0].text
    assert "FACT_b" not in result.content[0].text


async def test_memory_get_returns_full(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_a", NeedType.FACT)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_get"]
    result = await handler(srv, {"id": "FACT_a"})
    assert result.isError is False
    assert "FACT_a" in result.content[0].text


async def test_memory_get_unknown_id_returns_error_text(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_get"]
    result = await handler(srv, {"id": "NOPE_x"})
    assert result.isError is True
    assert "not found" in result.content[0].text.lower()


async def test_memory_tags_aggregates_counts(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_a", NeedType.FACT, tags=["topic:x", "scope:y"])
    _add(chain, Scope.LOCAL, "FACT_b", NeedType.FACT, tags=["topic:x"])
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_tags"]
    result = await handler(srv, {})
    assert result.isError is False
    data = json.loads(result.content[0].text)
    assert data["topic:x"] == 2
    assert data["scope:y"] == 1


async def test_memory_stale_returns_overdue_needs(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    past = datetime.now(UTC) - timedelta(days=10)
    _add(chain, Scope.LOCAL, "MEM_old", NeedType.MEM, review_after=past)
    _add(chain, Scope.LOCAL, "MEM_new", NeedType.MEM)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_stale"]
    result = await handler(srv, {})
    assert result.isError is False
    assert "MEM_old" in result.content[0].text
    assert "MEM_new" not in result.content[0].text


async def test_memory_add_writes_to_default_scope(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_add"]
    result = await handler(srv, {"type": "fact", "title": "Hello world"})
    assert result.isError is False
    assert "FACT_" in result.content[0].text
    assert chain.backend_for(Scope.LOCAL).find_by_id("FACT_hello_world") is not None


async def test_memory_add_explicit_workspace(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_add"]
    await handler(srv, {"type": "fact", "title": "Target program", "workspace": "program"})
    assert chain.backend_for(Scope.PROGRAM).find_by_id("FACT_target_program") is not None
    assert chain.backend_for(Scope.LOCAL).find_by_id("FACT_target_program") is None


async def test_memory_update_changes_body(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_a", NeedType.FACT, body="old")
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_update"]
    await handler(srv, {"id": "FACT_a", "body": "new"})
    updated_fact = chain.backend_for(Scope.LOCAL).find_by_id("FACT_a")
    assert updated_fact is not None
    assert updated_fact.body == "new"


async def test_memory_deprecate_sets_status(tmp_path: Path) -> None:
    from papyrus.models import Status
    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_old", NeedType.FACT)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_deprecate"]
    await handler(srv, {"id": "FACT_old"})
    deprecated_fact = chain.backend_for(Scope.LOCAL).find_by_id("FACT_old")
    assert deprecated_fact is not None
    assert deprecated_fact.status == Status.DEPRECATED


async def test_memory_deprecate_with_supersedes_link(tmp_path: Path) -> None:
    from papyrus.models import Status
    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "DEC_old", NeedType.DEC)
    _add(chain, Scope.LOCAL, "DEC_new", NeedType.DEC)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_deprecate"]
    await handler(srv, {"id": "DEC_old", "by": "DEC_new"})
    updated = chain.backend_for(Scope.LOCAL).find_by_id("DEC_old")
    assert updated is not None
    assert updated.status == Status.DEPRECATED
    assert any(lk.target == "DEC_new" for lk in updated.links)


async def test_memory_rebuild_writes_index(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_a", NeedType.FACT)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_rebuild"]
    result = await handler(srv, {"workspace": "local"})
    assert result.isError is False
    assert "1" in result.content[0].text  # count
    assert (tmp_path / "local_ws" / ".papyrus" / "index.json").is_file()


async def test_memory_promote_moves_need(tmp_path: Path) -> None:
    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_a", NeedType.FACT, confidence=Confidence.HIGH)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_promote"]
    result = await handler(srv, {"id": "FACT_a", "to": "program"})
    assert result.isError is False
    assert "Promoted" in result.content[0].text
    assert chain.backend_for(Scope.PROGRAM).find_by_id("FACT_a") is not None
    assert chain.backend_for(Scope.LOCAL).find_by_id("FACT_a") is None


async def test_memory_promote_low_confidence_rejected(tmp_path: Path) -> None:
    from papyrus.config import PromoteConfig
    cfg = PapyrusConfig(
        preset=Preset.CUSTOM,
        default_write=Scope.LOCAL,
        workspaces=[
            WorkspaceSpec(path=str(tmp_path / "local_ws"), scope=Scope.LOCAL),
            WorkspaceSpec(path=str(tmp_path / "prog_ws"), scope=Scope.PROGRAM),
        ],
        promote=PromoteConfig(to_program_requires_confidence=Confidence.HIGH),
    )
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    chain.initialize_all()
    _add(chain, Scope.LOCAL, "FACT_low", NeedType.FACT, confidence=Confidence.LOW)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_promote"]
    result = await handler(srv, {"id": "FACT_low", "to": "program"})
    assert result.isError is True
    assert "ERROR" in result.content[0].text or "confidence" in result.content[0].text.lower()


# --- Task 5: Concurrency correctness --------------------------------------------


async def test_concurrent_adds_serialize_per_workspace(tmp_path: Path) -> None:
    """Many concurrent memory_add calls to same workspace must all land correctly."""
    import asyncio as _asyncio
    chain, cfg = _chain(tmp_path)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_add"]
    n = 20

    async def add_one(i: int) -> str:
        result = await handler(srv, {"type": "fact", "title": f"Concurrent {i}"})
        return result.content[0].text

    await _asyncio.gather(*(add_one(i) for i in range(n)))

    loaded = chain.backend_for(Scope.LOCAL).load_needs()
    ids = {nd.id for nd in loaded}
    assert len(ids) == n, f"expected {n} distinct needs, got {len(ids)}"


async def test_concurrent_adds_across_workspaces_independent(tmp_path: Path) -> None:
    """Writes to different workspaces do not block each other (different locks)."""
    import asyncio as _asyncio
    chain, cfg = _chain(tmp_path)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_add"]

    async def add_to(scope: str, i: int) -> None:
        await handler(srv, {"type": "fact", "title": f"WS {scope} {i}", "workspace": scope})

    await _asyncio.gather(
        *(add_to("local", i) for i in range(5)),
        *(add_to("program", i) for i in range(5)),
    )

    assert len(chain.backend_for(Scope.LOCAL).load_needs()) == 5
    assert len(chain.backend_for(Scope.PROGRAM).load_needs()) == 5


# --- Task 6: stdio smoke + CLI help --------------------------------------------


async def test_build_server_list_tools_handler(tmp_path: Path) -> None:
    """Verify the mcp Server exposes the list_tools request handler."""
    chain, cfg = _chain(tmp_path)
    mcp = build_server(chain, cfg)
    try:
        from mcp.types import ListToolsRequest
    except ImportError:
        return  # SDK version lacks the type — smoke via .name alone in another test
    handler = mcp.request_handlers.get(ListToolsRequest)
    assert handler is not None, "list_tools handler not registered on mcp.Server"


def test_memory_link_tool_exposed():
    from papyrus.mcp_server import _TOOL_NAMES
    assert "memory_link" in _TOOL_NAMES


def test_memory_link_handler_attaches_edge(tmp_path):
    # Direct handler call (avoids mcp.Server internals).
    import asyncio
    from datetime import datetime

    from papyrus.config import PapyrusConfig, Preset, WorkspaceSpec
    from papyrus.mcp_server import PapyrusServer, _handle_link
    from papyrus.models import Need, NeedType, Scope
    from papyrus.storage.rst import RSTBackend
    from papyrus.workspace import WorkspaceChain

    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    now = datetime.now(UTC)
    be.append_need(Need(id="DEC_a", type=NeedType.DEC, title="a", created_at=now, updated_at=now))
    be.append_need(Need(id="FACT_b", type=NeedType.FACT, title="b", created_at=now, updated_at=now))

    cfg = PapyrusConfig(
        preset=Preset.CUSTOM,
        default_write=Scope.LOCAL,
        workspaces=[WorkspaceSpec(path=str(tmp_path), scope=Scope.LOCAL)],
    )
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    server = PapyrusServer(chain, cfg, base=tmp_path)

    out = asyncio.run(_handle_link(server, {"mem_id": "DEC_a", "target_id": "FACT_b", "link_type": "satisfies"}))
    assert out.isError is False
    assert "Linked" in _text(out)
    stored = be.find_by_id("DEC_a")
    assert stored is not None
    assert any(lk.target == "FACT_b" and lk.type.value == "satisfies" for lk in stored.links)


def test_memory_impact_handler_returns_reachable(tmp_path):
    import asyncio
    from datetime import datetime

    from papyrus.config import PapyrusConfig, Preset, WorkspaceSpec
    from papyrus.mcp_server import PapyrusServer, _handle_impact
    from papyrus.models import Link, LinkType, Need, NeedType, Scope
    from papyrus.storage.rst import RSTBackend
    from papyrus.workspace import WorkspaceChain

    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    now = datetime.now(UTC)
    be.append_need(Need(id="FACT_req", type=NeedType.FACT, title="r", created_at=now, updated_at=now))
    be.append_need(Need(
        id="DEC_a", type=NeedType.DEC, title="a", created_at=now, updated_at=now,
        links=[Link(type=LinkType.SATISFIES, target="FACT_req")],
    ))

    cfg = PapyrusConfig(
        preset=Preset.CUSTOM,
        default_write=Scope.LOCAL,
        workspaces=[WorkspaceSpec(path=str(tmp_path), scope=Scope.LOCAL)],
    )
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    server = PapyrusServer(chain, cfg, base=tmp_path)

    out = asyncio.run(_handle_impact(server, {"need_id": "FACT_req", "depth": 1}))
    assert out.isError is False
    text = _text(out)
    assert "FACT_req" in text
    assert "DEC_a" in text


def test_memory_trace_handler_shows_direct_and_chain(tmp_path):
    import asyncio
    from datetime import datetime

    from papyrus.config import PapyrusConfig, Preset, WorkspaceSpec
    from papyrus.mcp_server import PapyrusServer, _handle_trace
    from papyrus.models import Link, LinkType, Need, NeedType, Scope
    from papyrus.storage.rst import RSTBackend
    from papyrus.workspace import WorkspaceChain

    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    now = datetime.now(UTC)
    be.append_need(Need(id="DEC_v1", type=NeedType.DEC, title="v1", created_at=now, updated_at=now))
    be.append_need(Need(
        id="DEC_v2", type=NeedType.DEC, title="v2", created_at=now, updated_at=now,
        links=[Link(type=LinkType.SUPERSEDES, target="DEC_v1")],
    ))

    cfg = PapyrusConfig(
        preset=Preset.CUSTOM,
        default_write=Scope.LOCAL,
        workspaces=[WorkspaceSpec(path=str(tmp_path), scope=Scope.LOCAL)],
    )
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    server = PapyrusServer(chain, cfg, base=tmp_path)

    out = asyncio.run(_handle_trace(server, {"mem_id": "DEC_v2"}))
    assert out.isError is False
    text = _text(out)
    assert "DEC_v2" in text
    assert "DEC_v1" in text
    assert "supersedes" in text.lower()


def test_memory_impact_warns_when_external_unavailable(tmp_path):
    """Regression: MCP must surface external-load failures, not silently return partial graph."""
    import asyncio
    from datetime import datetime

    from papyrus.config import ExternalWorkspaceSpec, PapyrusConfig, Preset, WorkspaceSpec
    from papyrus.mcp_server import PapyrusServer, _handle_impact
    from papyrus.models import Need, NeedType, Scope
    from papyrus.storage.rst import RSTBackend
    from papyrus.workspace import WorkspaceChain

    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    now = datetime.now(UTC)
    be.append_need(Need(id="DEC_x", type=NeedType.DEC, title="x", created_at=now, updated_at=now))

    cfg = PapyrusConfig(
        preset=Preset.CUSTOM,
        default_write=Scope.LOCAL,
        workspaces=[WorkspaceSpec(path=str(tmp_path), scope=Scope.LOCAL)],
        external=ExternalWorkspaceSpec(pharaoh_workspace="does-not-exist", needs_json="needs.json"),
    )
    chain = WorkspaceChain.from_config(cfg, base=tmp_path)
    server = PapyrusServer(chain, cfg, base=tmp_path)

    out = asyncio.run(_handle_impact(server, {"need_id": "DEC_x", "depth": 1}))
    # Partial-graph warning is still a successful response (local data returned).
    assert out.isError is False
    text = _text(out)
    assert "WARNING" in text
    assert "external needs unavailable" in text
    assert "DEC_x" in text  # local part still returned


async def test_memory_get_unknown_id_returns_is_error(tmp_path: Path) -> None:
    """Domain error (id not found) must surface as isError=True at envelope."""
    from papyrus.mcp_server import PapyrusServer, _handle_get

    chain, cfg = _chain(tmp_path)
    srv = PapyrusServer(chain, cfg)

    result = await _handle_get(srv, {"id": "DOES_NOT_EXIST"})

    assert isinstance(result, CallToolResult)
    assert result.isError is True, "not-found must set isError=True"
    assert "not found" in _text(result).lower()


async def test_memory_recall_coerces_scalar_tags(tmp_path: Path) -> None:
    """memory_recall with tags='topic:x' must behave as tags=['topic:x']."""
    from papyrus.mcp_server import _handle_add, _handle_recall

    chain, cfg = _chain(tmp_path)
    srv = PapyrusServer(chain, cfg)

    await _handle_add(srv, {"type": "fact", "title": "One", "tags": ["topic:safety"]})
    await _handle_add(srv, {"type": "fact", "title": "Two", "tags": ["topic:other"]})

    scalar_result = await _handle_recall(srv, {"tags": "topic:safety"})
    list_result = await _handle_recall(srv, {"tags": ["topic:safety"]})

    scalar_text = _text(scalar_result)
    list_text = _text(list_result)
    assert scalar_text == list_text, "scalar tag must match list-of-one behaviour"
    assert "One" in scalar_text
    assert "Two" not in scalar_text


async def test_memory_recall_semantic_errors_when_extra_missing(tmp_path: Path, monkeypatch) -> None:
    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_temp", NeedType.FACT, body="celsius")
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_recall"]

    monkeypatch.setattr("papyrus.semantic.semantic_available", lambda: False)
    result = await handler(srv, {"semantic": True, "query": "temperature"})
    assert result.isError is True
    assert "papyrus[semantic]" in _text(result, 0)


async def test_memory_recall_semantic_requires_query(tmp_path: Path, monkeypatch) -> None:
    chain, cfg = _chain(tmp_path)
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_recall"]

    monkeypatch.setattr("papyrus.semantic.semantic_available", lambda: True)
    result = await handler(srv, {"semantic": True})  # no query
    assert result.isError is True


async def test_memory_recall_semantic_ranks_related_first(tmp_path: Path, monkeypatch) -> None:
    from papyrus.semantic import FakeEncoder, SemanticIndex

    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_temp", NeedType.FACT, body="sensor celsius reading")
    _add(chain, Scope.LOCAL, "DEC_auth", NeedType.DEC, body="use bcrypt password hashing")
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_recall"]

    encoder = FakeEncoder(
        axes=["thermal", "auth"],
        keyword_map={
            "thermal": ["temperature", "celsius", "hot"],
            "auth": ["password", "bcrypt"],
        },
    )
    monkeypatch.setattr("papyrus.semantic.semantic_available", lambda: True)
    monkeypatch.setattr(
        "papyrus.semantic.build_default_index",
        lambda ws: SemanticIndex(ws / ".papyrus", encoder=encoder, model_name="fake"),
    )
    # Populate vectors by reindexing the LOCAL backend (the primary workspace).
    chain.backend_for(Scope.LOCAL).rebuild_index()

    result = await handler(srv, {"semantic": True, "query": "temperature"})
    assert result.isError is False
    text = _text(result, 0)
    assert "FACT_temp" in text
    assert text.index("FACT_temp") < text.index("DEC_auth")


async def test_memory_recall_semantic_merges_hits_across_scopes(tmp_path: Path, monkeypatch) -> None:
    """Semantic recall must search every scope in the chain, not just the first."""
    from papyrus.semantic import FakeEncoder, SemanticIndex

    chain, cfg = _chain(tmp_path)
    # Thermal-related need in LOCAL, auth-related need in PROGRAM.
    _add(chain, Scope.LOCAL, "FACT_temp", NeedType.FACT, body="sensor celsius reading")
    _add(chain, Scope.PROGRAM, "DEC_auth", NeedType.DEC, body="bcrypt password hashing")
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_recall"]

    encoder = FakeEncoder(
        axes=["thermal", "auth"],
        keyword_map={
            "thermal": ["temperature", "celsius", "hot"],
            "auth": ["password", "bcrypt", "authentication"],
        },
    )
    monkeypatch.setattr("papyrus.semantic.semantic_available", lambda: True)
    monkeypatch.setattr(
        "papyrus.semantic.build_default_index",
        lambda ws: SemanticIndex(ws / ".papyrus", encoder=encoder, model_name="fake"),
    )
    # Populate vectors in BOTH scopes.
    chain.backend_for(Scope.LOCAL).rebuild_index()
    chain.backend_for(Scope.PROGRAM).rebuild_index()

    # Query matching the PROGRAM-scope need — would return empty pre-fix.
    result = await handler(srv, {"semantic": True, "query": "authentication"})
    assert result.isError is False
    text = _text(result, 0)
    assert "DEC_auth" in text


async def test_memory_recall_semantic_show_scores(tmp_path: Path, monkeypatch) -> None:
    from papyrus.semantic import FakeEncoder, SemanticIndex

    chain, cfg = _chain(tmp_path)
    _add(chain, Scope.LOCAL, "FACT_temp", NeedType.FACT, body="celsius")
    srv = PapyrusServer(chain, cfg)
    handler = _HANDLERS["memory_recall"]

    encoder = FakeEncoder(axes=["x"], keyword_map={"x": ["temperature", "celsius"]})
    monkeypatch.setattr("papyrus.semantic.semantic_available", lambda: True)
    monkeypatch.setattr(
        "papyrus.semantic.build_default_index",
        lambda ws: SemanticIndex(ws / ".papyrus", encoder=encoder, model_name="fake"),
    )
    chain.backend_for(Scope.LOCAL).rebuild_index()

    result = await handler(srv, {"semantic": True, "query": "temperature", "show_scores": True})
    assert result.isError is False
    text = _text(result, 0)
    # Brief with scores: "<score>  <id>..." — first token is a numeric string.
    first_line = text.strip().splitlines()[0]
    assert first_line.split()[0].replace(".", "").isdigit()
