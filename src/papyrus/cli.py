"""Papyrus CLI entry point."""
from __future__ import annotations

import asyncio as _asyncio
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import click

from papyrus import __version__
from papyrus.config import PapyrusConfig, load_config
from papyrus.graph import Node
from papyrus.models import Confidence, Link, LinkType, Need, NeedType, Scope, Status
from papyrus.promote import PromoteError
from papyrus.promote import promote as promote_need
from papyrus.query import QueryFormat, filter_needs, render, render_with_scores
from papyrus.storage.rst import RSTBackend
from papyrus.workspace import WorkspaceChain


@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="papyrus")
@click.option("--workspace", "-w", type=click.Path(path_type=Path), default=None,
              help="Path to Papyrus workspace. Default: $PAPYRUS_WORKSPACE or CWD.")
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=None,
              help="Path to papyrus.toml. Default: papyrus.toml in workspace or CWD.")
@click.pass_context
def cli(ctx: click.Context, workspace: Path | None, config_path: Path | None) -> None:
    """Papyrus — rationale-as-code layer for sphinx-needs."""
    ctx.ensure_object(dict)
    ctx.obj["workspace"] = workspace
    ctx.obj["config_path"] = config_path
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.argument("path", type=click.Path(path_type=Path))
def init(path: Path) -> None:
    """Scaffold a new Papyrus workspace at PATH."""
    RSTBackend(path).init_workspace(path)
    click.echo(f"Initialized Papyrus workspace at {path}")


def _resolve_workspace(ctx: click.Context) -> Path:
    ws = ctx.obj.get("workspace")
    if ws is None:
        env = os.environ.get("PAPYRUS_WORKSPACE")
        ws = Path(env) if env else Path.cwd()
    return ws


_ID_SANITIZER = re.compile(r"[^A-Za-z0-9]+")


def _load_chain_from_ctx(ctx: click.Context) -> tuple[WorkspaceChain, PapyrusConfig, Path]:
    """Resolve (chain, config, base) from CLI context.

    `base` is the directory against which relative paths in the config
    (workspaces, external needs_json) are resolved.
    """
    cfg_path = ctx.obj.get("config_path")
    if cfg_path is not None:
        cfg = load_config(cfg_path)
        base = cfg_path.parent if cfg_path.is_file() else cfg_path
    else:
        base = _resolve_workspace(ctx)
        cfg = load_config(base)
    chain = WorkspaceChain.from_config(cfg, base=base)
    return chain, cfg, base


def _auto_id(ntype: NeedType, title: str) -> str:
    slug = _ID_SANITIZER.sub("_", title.strip()).strip("_").lower()
    slug = slug[:60] or "entry"
    return f"{ntype.prefix}{slug}"


@cli.command()
@click.argument("type", type=click.Choice([t.value for t in NeedType]))
@click.argument("title")
@click.option("--body", default="", help="Long-form body text.")
@click.option("--tags", default="", help="Comma-separated tags.")
@click.option("--confidence", type=click.Choice([c.value for c in Confidence]), default="medium")
@click.option("--scope", type=click.Choice([s.value for s in Scope]), default="local")
@click.option("--relates", default="", help="Comma-separated related IDs.")
@click.option("--source", default="")
@click.option("--id", "id_", default=None, help="Override auto-generated id.")
@click.pass_context
def add(
    ctx: click.Context,
    type: str,
    title: str,
    body: str,
    tags: str,
    confidence: str,
    scope: str,
    relates: str,
    source: str,
    id_: str | None,
) -> None:
    """Append a new memory record to the workspace."""
    ws = _resolve_workspace(ctx)
    backend = RSTBackend(ws)
    if not (ws / "conf.py").is_file():
        raise click.UsageError(f"{ws} is not a Papyrus workspace (run `papyrus init` first)")

    ntype = NeedType(type)
    now = datetime.now(UTC)
    nid = id_ or _auto_id(ntype, title)
    need = Need(
        id=nid,
        type=ntype,
        title=title,
        body=body,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        confidence=Confidence(confidence),
        scope=Scope(scope),
        status=Status.ACTIVE,
        source=source,
        created_at=now,
        updated_at=now,
        links=[
            Link(type=LinkType.RELATES, target=t.strip())
            for t in relates.split(",")
            if t.strip()
        ],
    )
    try:
        backend.append_need(need)
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Added {need.id}")


@cli.command()
@click.option("--tag", "tags", multiple=True, help="Filter by tag (repeatable; AND).")
@click.option("--type", "type_", type=click.Choice([t.value for t in NeedType]), default=None)
@click.option("--query", "-q", default=None, help="Substring match (or semantic query with --semantic).")
@click.option("--semantic", "semantic", is_flag=True, default=False,
              help="Use vector similarity instead of substring match (requires papyrus[semantic]).")
@click.option("--top-k", "top_k", type=int, default=10, help="Max semantic hits to return.")
@click.option("--show-scores", "show_scores", is_flag=True, default=False,
              help="Developer aid: prefix each result with the similarity score.")
@click.option(
    "--format", "fmt",
    type=click.Choice([f.value for f in QueryFormat]),
    default=QueryFormat.BRIEF.value,
    help="Output detail level.",
)
@click.pass_context
def recall(
    ctx: click.Context,
    tags: tuple[str, ...],
    type_: str | None,
    query: str | None,
    semantic: bool,
    top_k: int,
    show_scores: bool,
    fmt: str,
) -> None:
    """Search memories (brief by default; drill down with --format)."""
    chain, _, _ = _load_chain_from_ctx(ctx)
    scoped = chain.resolve_read()
    needs = [sn.need for sn in scoped]
    scope_by_id = {sn.need.id: sn.scope for sn in scoped}
    annotations = scope_by_id if len(chain.list_scopes()) > 1 else None

    if semantic:
        if not query:
            raise click.ClickException("--semantic requires -q/--query.")
        from papyrus import semantic as sem
        if not sem.semantic_available():
            raise click.ClickException(
                "semantic search requires: pip install papyrus[semantic]"
            )

        narrowed = filter_needs(
            needs,
            tags=list(tags) or None,
            type=NeedType(type_) if type_ else None,
            query=None,
        )
        narrowed_ids = {n.id for n in narrowed}

        primary_backend = chain.backend_for(chain.list_scopes()[0])
        try:
            idx = sem.build_default_index(primary_backend.workspace)
        except ImportError as e:
            raise click.ClickException(str(e)) from e
        hits = idx.search(query, top_k=top_k, filter_ids=narrowed_ids)

        by_id = {n.id: n for n in needs}
        pairs = [(by_id[h.id], h.score) for h in hits if h.id in by_id]
        click.echo(render_with_scores(pairs, QueryFormat(fmt),
                                      scope_by_id=annotations, show_scores=show_scores))
        return

    filtered = filter_needs(
        needs,
        tags=list(tags) or None,
        type=NeedType(type_) if type_ else None,
        query=query,
    )
    click.echo(render(filtered, QueryFormat(fmt), scope_by_id=annotations))


@cli.command(name="rebuild-index")
@click.pass_context
def rebuild_index(ctx: click.Context) -> None:
    """Rebuild .papyrus/index.json (and semantic vectors if extra is installed)."""
    from papyrus.storage.rst import RSTBackend

    chain, _, _ = _load_chain_from_ctx(ctx)
    total = 0
    for scope in chain.list_scopes():
        backend = chain.backend_for(scope)
        if isinstance(backend, RSTBackend):
            count = backend.rebuild_index()
            total += count
    click.echo(f"Rebuilt index: {total} need(s) indexed.")


@cli.command()
@click.argument("need_id")
@click.pass_context
def get(ctx: click.Context, need_id: str) -> None:
    """Show a single memory in full."""
    chain, _, _ = _load_chain_from_ctx(ctx)
    hit = chain.find_by_id(need_id)
    if hit is None:
        raise click.ClickException(f"{need_id!r} not found")
    annotations = {hit.need.id: hit.scope} if len(chain.list_scopes()) > 1 else None
    click.echo(render([hit.need], QueryFormat.FULL, scope_by_id=annotations))


@cli.command()
@click.argument("need_id")
@click.option("--to", "target", type=click.Choice([s.value for s in Scope]), required=True,
              help="Target scope for promotion.")
@click.pass_context
def promote(ctx: click.Context, need_id: str, target: str) -> None:
    """Move a memory from its current scope to a higher one."""
    chain, cfg, base = _load_chain_from_ctx(ctx)
    try:
        result = promote_need(chain, need_id, target_scope=Scope(target), promote_cfg=cfg.promote)
    except PromoteError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Promoted {result.need.id} to {result.scope.value}")


@cli.command(name="link")
@click.argument("mem_id")
@click.argument("target_id")
@click.option("--as", "link_type", type=click.Choice([lt.value for lt in LinkType]), required=True,
              help="Link type (sphinx-needs compatible).")
@click.pass_context
def link_cmd(ctx: click.Context, mem_id: str, target_id: str, link_type: str) -> None:
    """Attach a typed link from MEM_ID to TARGET_ID.

    TARGET_ID may live in the Papyrus workspace or in an external pharaoh index
    declared under [papyrus.external] (pass --config papyrus.toml for the latter).
    Idempotent: re-running with the same triple is a no-op.
    """
    chain, cfg, base = _load_chain_from_ctx(ctx)
    mem_hit = chain.find_by_id(mem_id)
    if mem_hit is None:
        raise click.ClickException(f"{mem_id!r} not found in any workspace")

    # Target may live in Papyrus chain OR external pharaoh index.
    target_ok = chain.find_by_id(target_id) is not None
    if not target_ok and cfg.external is not None:
        from papyrus.external import ExternalLoadError, ExternalNeedsIndex
        try:
            idx = ExternalNeedsIndex.from_needs_json(cfg.external.resolved_needs_json(base))
        except ExternalLoadError as e:
            raise click.ClickException(f"failed to load external needs: {e}") from e
        target_ok = idx.has_id(target_id)
    if not target_ok:
        raise click.ClickException(f"{target_id!r} not found in any workspace")

    lt = LinkType(link_type)
    existing = list(mem_hit.need.links)
    if any(lk.type == lt and lk.target == target_id for lk in existing):
        click.echo(f"Link {mem_id} -{lt.value}-> {target_id} already present (no-op)")
        return
    new_links = existing + [Link(type=lt, target=target_id)]
    chain.backend_for(mem_hit.scope).update_need(mem_id, links=new_links)
    click.echo(f"Linked {mem_id} -{lt.value}-> {target_id}")


def _chain_to_graph(
    chain: WorkspaceChain,
    cfg: PapyrusConfig | None = None,
    base: Path | None = None,
) -> dict[str, Node]:
    """Convert Papyrus chain (+ optional external pharaoh index) into a merged Node dict."""
    from papyrus.external import ExternalLoadError, ExternalNeedsIndex
    from papyrus.graph import Edge

    nodes: dict[str, Node] = {}
    for sn in chain.resolve_read():
        edges = [Edge(type=lk.type.value, target=lk.target) for lk in sn.need.links]
        nodes[sn.need.id] = Node(id=sn.need.id, title=sn.need.title, kind="mem", edges=edges)

    if cfg is not None and cfg.external is not None and base is not None:
        needs_path = cfg.external.resolved_needs_json(base)
        try:
            idx = ExternalNeedsIndex.from_needs_json(needs_path)
        except ExternalLoadError as e:
            raise click.ClickException(f"failed to load external needs: {e}") from e
        for node in idx.iter_nodes():
            if node.id not in nodes:  # local papyrus node wins on id collision
                nodes[node.id] = node

    return nodes


@cli.command(name="impact")
@click.argument("need_id")
@click.option("--depth", type=int, default=3, help="Max BFS hops (default: 3).")
@click.option("--link-type", "link_types", multiple=True,
              help="Restrict traversal to these link types (repeatable).")
@click.pass_context
def impact_cmd(ctx: click.Context, need_id: str, depth: int, link_types: tuple[str, ...]) -> None:
    """Show all needs reachable from NEED_ID within --depth hops."""
    from papyrus.graph import impact_walk

    chain, cfg, base = _load_chain_from_ctx(ctx)
    graph = _chain_to_graph(chain, cfg=cfg, base=base)
    if need_id not in graph:
        raise click.ClickException(f"{need_id!r} not found")

    allowed = list(link_types) if link_types else None
    hits = impact_walk(graph, start=need_id, depth=depth, link_types=allowed)

    for hit in hits:
        prefix = "*" if hit.distance == 0 else f"{hit.distance}"
        path = " / ".join(hit.path_edge_types) if hit.path_edge_types else ""
        kind = f" [{hit.node.kind}]" if hit.node.kind != "mem" else ""
        line = f"[{prefix}] {hit.node.id}{kind} — {hit.node.title}"
        if path:
            line += f"  ({path})"
        click.echo(line)


@cli.command(name="trace")
@click.argument("need_id")
@click.pass_context
def trace_cmd(ctx: click.Context, need_id: str) -> None:
    """Show a memory's supersession chain and direct links."""
    chain, cfg, base = _load_chain_from_ctx(ctx)
    hit = chain.find_by_id(need_id)
    if hit is None:
        raise click.ClickException(f"{need_id!r} not found")

    # Optionally load external pharaoh index so the chain walker can mark
    # continuations into an external workspace instead of silently truncating.
    ext_index = None
    if cfg.external is not None:
        from papyrus.external import ExternalLoadError, ExternalNeedsIndex
        try:
            ext_index = ExternalNeedsIndex.from_needs_json(
                cfg.external.resolved_needs_json(base)
            )
        except ExternalLoadError:
            ext_index = None

    click.echo(f"=== {hit.need.id} — {hit.need.title} ===")
    click.echo(f"type={hit.need.type.value} status={hit.need.status.value} "
               f"created={hit.need.created_at.isoformat()} updated={hit.need.updated_at.isoformat()}")

    if hit.need.links:
        click.echo("\nDirect links:")
        for lk in hit.need.links:
            click.echo(f"  -{lk.type.value}-> {lk.target}")

    # Walk supersedes chain transitively.
    chain_seen: list[str] = []
    external_tail: tuple[str, str] | None = None  # (id, title) when chain crosses into pharaoh
    cursor = hit.need
    while True:
        prev_ids = [lk.target for lk in cursor.links if lk.type == LinkType.SUPERSEDES]
        if not prev_ids:
            break
        prev = chain.find_by_id(prev_ids[0])
        if prev is None:
            if ext_index is not None:
                ext_node = ext_index.get(prev_ids[0])
                if ext_node is not None:
                    external_tail = (ext_node.id, ext_node.title)
            break
        if prev.need.id in chain_seen:
            break
        chain_seen.append(prev.need.id)
        cursor = prev.need

    if chain_seen or external_tail is not None:
        click.echo("\nSupersession chain (newest → oldest):")
        click.echo(f"  {hit.need.id}")
        for nid in chain_seen:
            click.echo("    ↓ supersedes")
            click.echo(f"  {nid}")
        if external_tail is not None:
            click.echo("    ↓ supersedes")
            click.echo(
                f"  (chain continues into external pharaoh: "
                f"{external_tail[0]} — {external_tail[1]})"
            )


@cli.command(name="mcp-serve")
@click.pass_context
def mcp_serve(ctx: click.Context) -> None:
    """Run the Papyrus MCP server over stdio."""
    from papyrus.mcp_server import serve_stdio

    cfg_path = ctx.obj.get("config_path")
    if cfg_path is None:
        cfg_path = _resolve_workspace(ctx)
    _asyncio.run(serve_stdio(cfg_path))


if __name__ == "__main__":
    cli()
