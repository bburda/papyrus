"""Papyrus MCP server: 9 tools over stdio.

Tools exposed:
- memory_recall, memory_get, memory_tags, memory_stale (reads)
- memory_add, memory_update, memory_deprecate, memory_rebuild, memory_promote (writes)

Each write tool is serialized per-workspace via asyncio.Lock; reads are lockless.
"""
from __future__ import annotations

import asyncio
import json
import re as _re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from mcp.server import Server
from mcp.types import CallToolResult, TextContent, Tool

from papyrus.config import PapyrusConfig, load_config
from papyrus.models import Confidence, Link, LinkType, Need, NeedType, Scope, Status
from papyrus.promote import PromoteError
from papyrus.promote import promote as promote_need
from papyrus.query import QueryFormat, filter_needs, render
from papyrus.workspace import WorkspaceChain

_ID_SANITIZER = _re.compile(r"[^A-Za-z0-9]+")


def _auto_id(ntype: NeedType, title: str) -> str:
    slug = _ID_SANITIZER.sub("_", title.strip()).strip("_").lower()
    slug = slug[:60] or "entry"
    return f"{ntype.prefix}{slug}"


def _error(msg: str) -> CallToolResult:
    """Build a CallToolResult marked as error per MCP spec."""
    return CallToolResult(
        content=cast(list[Any], [TextContent(type="text", text=msg)]),
        isError=True,
    )


def _ok(content: list[TextContent]) -> CallToolResult:
    """Build a successful CallToolResult from one or more TextContent items.

    Cast is needed because CallToolResult.content is typed as invariant
    list[ContentBlock] in the MCP SDK, but we only ever return TextContent.
    """
    return CallToolResult(content=cast(list[Any], content), isError=False)


_TOOL_NAMES: tuple[str, ...] = (
    "memory_recall",
    "memory_get",
    "memory_add",
    "memory_update",
    "memory_deprecate",
    "memory_tags",
    "memory_stale",
    "memory_rebuild",
    "memory_promote",
    "memory_link",
    "memory_impact",
    "memory_trace",
)


class PapyrusServer:
    """Holds the WorkspaceChain and per-workspace locks.

    Tool handlers live in module-level functions (added in subsequent tasks).
    """

    def __init__(self, chain: WorkspaceChain, cfg: PapyrusConfig, base: Path | None = None) -> None:
        self.chain = chain
        self.cfg = cfg
        self.base = base
        self._locks: dict[Scope, asyncio.Lock] = {s: asyncio.Lock() for s in chain.list_scopes()}

    def tool_names(self) -> tuple[str, ...]:
        return _TOOL_NAMES

    def lock_for(self, scope: Scope) -> asyncio.Lock:
        return self._locks[scope]

    def resolve_scope(self, arg_workspace: str | None) -> Scope:
        """Map a tool's optional 'workspace' arg (scope string) to a Scope.

        Falls back to default_write from config when arg is absent.
        """
        if arg_workspace:
            try:
                return Scope(arg_workspace)
            except ValueError as e:
                raise ValueError(f"unknown workspace scope {arg_workspace!r}") from e
        return self.cfg.default_write


def _build_tool_definitions() -> list[Tool]:
    """Return MCP Tool definitions. Populated in Tasks 2-4."""
    return [
        Tool(
            name="memory_recall",
            description=(
                "Search memories (brief by default). `semantic: true` switches to vector "
                "similarity search over needs (requires papyrus[semantic] extra). Scores "
                "are returned only when `show_scores: true`."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "type": {"type": "string", "enum": [t.value for t in NeedType]},
                    "query": {"type": "string"},
                    "format": {"type": "string", "enum": [f.value for f in QueryFormat], "default": "brief"},
                    "semantic": {"type": "boolean", "default": False},
                    "top_k": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                    "show_scores": {"type": "boolean", "default": False},
                },
            },
        ),
        Tool(
            name="memory_get",
            description="Show a single memory in full by id.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        ),
        Tool(
            name="memory_tags",
            description="Aggregate tags across all workspaces with counts (JSON object).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="memory_stale",
            description="List needs whose review_after has passed.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="memory_add",
            description="Append a new memory. workspace defaults to config.default_write scope.",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": [t.value for t in NeedType]},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": [c.value for c in Confidence]},
                    "workspace": {"type": "string", "enum": [s.value for s in Scope]},
                    "relates": {"type": "array", "items": {"type": "string"}},
                    "id": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["type", "title"],
            },
        ),
        Tool(
            name="memory_update",
            description="Update mutable fields of a memory by id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "body": {"type": "string"},
                    "title": {"type": "string"},
                    "status": {"type": "string", "enum": [s.value for s in Status]},
                    "confidence": {"type": "string", "enum": [c.value for c in Confidence]},
                    "scope": {"type": "string", "enum": [s.value for s in Scope]},
                    "source": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="memory_deprecate",
            description="Mark a memory deprecated; optionally link supersedes via `by`.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "string"}, "by": {"type": "string"}},
                "required": ["id"],
            },
        ),
        Tool(
            name="memory_rebuild",
            description="Rebuild the .papyrus/index.json for a workspace.",
            inputSchema={
                "type": "object",
                "properties": {"workspace": {"type": "string", "enum": [s.value for s in Scope]}},
            },
        ),
        Tool(
            name="memory_promote",
            description="Move a memory from its current scope to a higher scope.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "to": {"type": "string", "enum": [s.value for s in Scope]},
                },
                "required": ["id", "to"],
            },
        ),
        Tool(
            name="memory_link",
            description="Attach a typed link from mem_id to target_id. Target may live in external pharaoh workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mem_id": {"type": "string"},
                    "target_id": {"type": "string"},
                    "link_type": {"type": "string", "enum": [lt.value for lt in LinkType]},
                },
                "required": ["mem_id", "target_id", "link_type"],
            },
        ),
        Tool(
            name="memory_impact",
            description="BFS from need_id within depth hops; optionally filter by link_types.",
            inputSchema={
                "type": "object",
                "properties": {
                    "need_id": {"type": "string"},
                    "depth": {"type": "integer", "default": 3},
                    "link_types": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["need_id"],
            },
        ),
        Tool(
            name="memory_trace",
            description="Show one memory's direct links + supersession chain.",
            inputSchema={
                "type": "object",
                "properties": {"mem_id": {"type": "string"}},
                "required": ["mem_id"],
            },
        ),
    ]


def build_server(chain: WorkspaceChain, cfg: PapyrusConfig, base: Path | None = None) -> Server:
    """Construct an mcp.Server wired to the given chain."""
    papyrus = PapyrusServer(chain, cfg, base=base)
    mcp = Server("papyrus")

    @mcp.list_tools()
    async def list_tools() -> list[Tool]:
        return _build_tool_definitions()

    @mcp.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> CallToolResult:
        args = arguments or {}
        handler = _HANDLERS.get(name)
        if handler is None:
            return _error(f"unknown tool: {name}")
        try:
            return await handler(papyrus, args)
        except Exception as e:  # noqa: BLE001 - surface any handler failure to the client
            return _error(f"ERROR: {type(e).__name__}: {e}")

    return mcp


async def serve_stdio(cfg_path: Path) -> None:
    """Entry point for `papyrus mcp-serve`. Runs the server over stdio."""
    from mcp.server.stdio import stdio_server

    cfg = load_config(cfg_path)
    base = cfg_path.parent if cfg_path.is_file() else cfg_path
    chain = WorkspaceChain.from_config(cfg, base=base)
    chain.initialize_all()
    server = build_server(chain, cfg, base=base)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def _handle_recall(p: PapyrusServer, args: dict) -> CallToolResult:
    scoped = p.chain.resolve_read()
    all_needs = [sn.need for sn in scoped]
    scope_by_id = {sn.need.id: sn.scope for sn in scoped}
    type_arg = args.get("type")
    tags_arg = args.get("tags", [])
    if isinstance(tags_arg, str):
        tags_arg = [tags_arg]
    tags = list(tags_arg)
    fmt = QueryFormat(args.get("format", QueryFormat.BRIEF.value))
    annotations = scope_by_id if len(p.chain.list_scopes()) > 1 else None

    if args.get("semantic"):
        query = args.get("query") or ""
        if not query.strip():
            return _error("semantic=true requires a non-empty 'query'.")
        from papyrus import semantic as sem
        if not sem.semantic_available():
            return _error("semantic search requires: pip install papyrus[semantic]")
        narrowed = filter_needs(
            all_needs,
            tags=tags or None,
            type=NeedType(type_arg) if type_arg else None,
            query=None,
        )
        narrowed_ids = {n.id for n in narrowed}
        primary_backend = p.chain.backend_for(p.chain.list_scopes()[0])
        try:
            idx = sem.build_default_index(primary_backend.workspace)
        except ImportError as e:
            return _error(str(e))
        hits = idx.search(query, top_k=int(args.get("top_k", 10)), filter_ids=narrowed_ids)
        by_id = {n.id: n for n in all_needs}
        pairs = [(by_id[h.id], h.score) for h in hits if h.id in by_id]
        from papyrus.query import render_with_scores
        text = render_with_scores(
            pairs, fmt, scope_by_id=annotations, show_scores=bool(args.get("show_scores", False)),
        )
        return _ok([TextContent(type="text", text=text)])

    filtered = filter_needs(
        all_needs,
        tags=tags or None,
        type=NeedType(type_arg) if type_arg else None,
        query=args.get("query"),
    )
    return _ok([TextContent(type="text", text=render(filtered, fmt, scope_by_id=annotations))])


async def _handle_get(p: PapyrusServer, args: dict) -> CallToolResult:
    nid = args.get("id")
    if not nid:
        return _error("id is required")
    hit = p.chain.find_by_id(nid)
    if hit is None:
        return _error(f"{nid!r} not found")
    annotations = {hit.need.id: hit.scope} if len(p.chain.list_scopes()) > 1 else None
    return _ok([TextContent(type="text", text=render([hit.need], QueryFormat.FULL, scope_by_id=annotations))])


async def _handle_tags(p: PapyrusServer, args: dict) -> CallToolResult:
    counts: dict[str, int] = {}
    for sn in p.chain.resolve_read():
        for tag in sn.need.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return _ok([TextContent(type="text", text=json.dumps(counts, indent=2))])


async def _handle_stale(p: PapyrusServer, args: dict) -> CallToolResult:
    now = datetime.now(UTC)
    stale = []
    for sn in p.chain.resolve_read():
        ra = sn.need.review_after
        if ra is not None and ra < now:
            stale.append(sn.need)
    text = render(stale, QueryFormat.BRIEF) if stale else "(no stale needs)"
    return _ok([TextContent(type="text", text=text)])


async def _handle_add(p: PapyrusServer, args: dict) -> CallToolResult:
    scope = p.resolve_scope(args.get("workspace"))
    async with p.lock_for(scope):
        ntype = NeedType(args["type"])
        title = args["title"]
        nid = args.get("id") or _auto_id(ntype, title)
        tags = list(args.get("tags", []))
        now = datetime.now(UTC)
        need = Need(
            id=nid,
            type=ntype,
            title=title,
            body=args.get("body", ""),
            tags=tags,
            confidence=Confidence(args.get("confidence", Confidence.MEDIUM.value)),
            scope=scope,
            status=Status.ACTIVE,
            source=args.get("source", ""),
            created_at=now,
            updated_at=now,
            links=[Link(type=LinkType.RELATES, target=t) for t in args.get("relates", [])],
        )
        p.chain.backend_for(scope).append_need(need)
    return _ok([TextContent(type="text", text=f"Added {nid} to {scope.value}")])


async def _handle_update(p: PapyrusServer, args: dict) -> CallToolResult:
    nid = args["id"]
    hit = p.chain.find_by_id(nid)
    if hit is None:
        return _error(f"{nid!r} not found")
    async with p.lock_for(hit.scope):
        patch: dict[str, object] = {}
        for key in ("body", "title", "status", "confidence", "scope", "source", "tags"):
            if key in args:
                patch[key] = args[key]
        if "status" in patch:
            patch["status"] = Status(patch["status"])  # type: ignore[arg-type]
        if "confidence" in patch:
            patch["confidence"] = Confidence(patch["confidence"])  # type: ignore[arg-type]
        if "scope" in patch:
            patch["scope"] = Scope(patch["scope"])  # type: ignore[arg-type]
        p.chain.backend_for(hit.scope).update_need(nid, **patch)
    return _ok([TextContent(type="text", text=f"Updated {nid}")])


async def _handle_deprecate(p: PapyrusServer, args: dict) -> CallToolResult:
    nid = args["id"]
    by_id = args.get("by")
    hit = p.chain.find_by_id(nid)
    if hit is None:
        return _error(f"{nid!r} not found")
    async with p.lock_for(hit.scope):
        links = list(hit.need.links)
        if by_id:
            links = [lk for lk in links if not (lk.type == LinkType.SUPERSEDES and lk.target == by_id)]
            links.append(Link(type=LinkType.SUPERSEDES, target=by_id))
        p.chain.backend_for(hit.scope).update_need(nid, status=Status.DEPRECATED, links=links)
    msg = f"Deprecated {nid}" + (f" (superseded by {by_id})" if by_id else "")
    return _ok([TextContent(type="text", text=msg)])


async def _handle_rebuild(p: PapyrusServer, args: dict) -> CallToolResult:
    scope = p.resolve_scope(args.get("workspace"))
    async with p.lock_for(scope):
        count = p.chain.backend_for(scope).rebuild_index()
    return _ok([TextContent(type="text", text=f"Rebuilt index for {scope.value}: {count} needs")])


async def _handle_promote(p: PapyrusServer, args: dict) -> CallToolResult:
    nid = args["id"]
    target = Scope(args["to"])
    hit = p.chain.find_by_id(nid)
    if hit is None:
        return _error(f"{nid!r} not found")
    # Acquire locks deterministically (by scope value string) to avoid deadlock
    # under concurrent opposite-direction promotes.
    first, second = sorted([hit.scope, target], key=lambda s: s.value)
    async with p.lock_for(first), p.lock_for(second):
        try:
            result = promote_need(p.chain, nid, target_scope=target, promote_cfg=p.cfg.promote)
        except PromoteError as e:
            return _error(f"{e}")
    return _ok([TextContent(type="text", text=f"Promoted {result.need.id} to {result.scope.value}")])


async def _handle_link(p: PapyrusServer, args: dict) -> CallToolResult:
    from papyrus.external import ExternalLoadError, ExternalNeedsIndex

    mem_id = args["mem_id"]
    target_id = args["target_id"]
    lt = LinkType(args["link_type"])

    mem_hit = p.chain.find_by_id(mem_id)
    if mem_hit is None:
        return _error(f"{mem_id!r} not found")

    target_ok = p.chain.find_by_id(target_id) is not None
    if not target_ok and p.cfg.external is not None and p.base is not None:
        try:
            idx = ExternalNeedsIndex.from_needs_json(p.cfg.external.resolved_needs_json(p.base))
        except ExternalLoadError as e:
            return _error(f"{e}")
        target_ok = idx.has_id(target_id)
    if not target_ok:
        return _error(f"{target_id!r} not found")

    async with p.lock_for(mem_hit.scope):
        existing = list(mem_hit.need.links)
        if any(lk.type == lt and lk.target == target_id for lk in existing):
            return _ok([TextContent(type="text", text=f"Link {mem_id} -{lt.value}-> {target_id} already present (no-op)")])
        new_links = existing + [Link(type=lt, target=target_id)]
        p.chain.backend_for(mem_hit.scope).update_need(mem_id, links=new_links)

    return _ok([TextContent(type="text", text=f"Linked {mem_id} -{lt.value}-> {target_id}")])


def _server_graph(p: PapyrusServer) -> tuple[dict, str | None]:
    """Merge Papyrus chain with the external pharaoh index.

    Returns (nodes, warning). `warning` is None on success; on external
    load failure it holds a user-facing message and `nodes` contains only
    the Papyrus half. Tool handlers prepend the warning so clients notice
    the partial graph rather than reading missing impact as "no impact".
    """
    from papyrus.external import ExternalLoadError, ExternalNeedsIndex
    from papyrus.graph import Edge, Node

    nodes: dict[str, Node] = {}
    for sn in p.chain.resolve_read():
        edges = [Edge(type=lk.type.value, target=lk.target) for lk in sn.need.links]
        nodes[sn.need.id] = Node(id=sn.need.id, title=sn.need.title, kind="mem", edges=edges)

    if p.cfg.external is None or p.base is None:
        return nodes, None
    try:
        idx = ExternalNeedsIndex.from_needs_json(p.cfg.external.resolved_needs_json(p.base))
    except ExternalLoadError as e:
        return nodes, f"WARNING: external needs unavailable ({e}); results exclude pharaoh nodes."
    for node in idx.iter_nodes():
        if node.id not in nodes:
            nodes[node.id] = node
    return nodes, None


async def _handle_impact(p: PapyrusServer, args: dict) -> CallToolResult:
    from papyrus.graph import impact_walk

    need_id = args.get("need_id")
    if not need_id:
        return _error("need_id is required")
    depth = int(args.get("depth", 3))
    link_types = args.get("link_types") or None

    graph, warning = _server_graph(p)
    if need_id not in graph:
        return _error(f"{need_id!r} not found")

    hits = impact_walk(graph, start=need_id, depth=depth, link_types=link_types)
    lines = []
    if warning:
        lines.append(warning)
        lines.append("")
    for hit in hits:
        prefix = "*" if hit.distance == 0 else str(hit.distance)
        path = " / ".join(hit.path_edge_types) if hit.path_edge_types else ""
        kind = f" [{hit.node.kind}]" if hit.node.kind != "mem" else ""
        line = f"[{prefix}] {hit.node.id}{kind} — {hit.node.title}"
        if path:
            line += f"  ({path})"
        lines.append(line)
    return _ok([TextContent(type="text", text="\n".join(lines))])


async def _handle_trace(p: PapyrusServer, args: dict) -> CallToolResult:
    mem_id = args.get("mem_id")
    if not mem_id:
        return _error("mem_id is required")
    hit = p.chain.find_by_id(mem_id)
    if hit is None:
        return _error(f"{mem_id!r} not found")

    lines = [f"=== {hit.need.id} — {hit.need.title} ==="]
    if hit.need.links:
        lines.append("Direct links:")
        for lk in hit.need.links:
            lines.append(f"  -{lk.type.value}-> {lk.target}")

    chain_seen: list[str] = []
    cursor = hit.need
    while True:
        prev_ids = [lk.target for lk in cursor.links if lk.type == LinkType.SUPERSEDES]
        if not prev_ids:
            break
        prev = p.chain.find_by_id(prev_ids[0])
        if prev is None or prev.need.id in chain_seen:
            break
        chain_seen.append(prev.need.id)
        cursor = prev.need

    if chain_seen:
        lines.append("Supersession chain (newest → oldest):")
        lines.append(f"  {hit.need.id}")
        for nid in chain_seen:
            lines.append("    ↓ supersedes")
            lines.append(f"  {nid}")
    return _ok([TextContent(type="text", text="\n".join(lines))])


# Populated in Tasks 2-4; maps tool name -> async handler(papyrus, args) -> CallToolResult
_HANDLERS: dict[str, Any] = {
    "memory_recall": _handle_recall,
    "memory_get": _handle_get,
    "memory_tags": _handle_tags,
    "memory_stale": _handle_stale,
    "memory_add": _handle_add,
    "memory_update": _handle_update,
    "memory_deprecate": _handle_deprecate,
    "memory_rebuild": _handle_rebuild,
    "memory_promote": _handle_promote,
    "memory_link": _handle_link,
    "memory_impact": _handle_impact,
    "memory_trace": _handle_trace,
}
