# Architecture

Papyrus stores AI-agent decisions, risks, facts, and open questions as
first-class sphinx-needs, links them to external pharaoh requirements,
and walks the resulting graph for impact analysis. This document
describes the pieces that make that work.

## Data model

A **Need** is the unit of memory. It has a stable ID, a type, a title,
an optional body, tags, a scope, a status, a creation/update timestamp,
and typed links. Needs live as reStructuredText blocks under
`<workspace>/memory/*.rst` — diffable, reviewable, and consumable by any
sphinx-needs toolchain.

**Types** (see `src/papyrus/models.py`):

| Type   | Purpose                                               |
|--------|-------------------------------------------------------|
| `dec`  | Decision with rationale and alternatives              |
| `risk` | Identified risk with mitigation                       |
| `fact` | Ground truth about the system (invariants, contracts) |
| `q`    | Open question awaiting resolution                     |
| `mem`  | Generic note that doesn't fit the other types         |

**Link types** (see `LinkType`): `satisfies`, `derives`, `extends`,
`supersedes`, `depends`, `supports`, `contradicts`, `relates`.

**Scope** gates where a memory is written and who reads it: `local`
(this workspace), `program` (a parent workspace shared across a team),
`global` (cross-program). Multiple workspaces chain together so reads
union across scopes while writes are scoped.

## Layers

```
  CLI                                MCP server
   │                                      │
   └──────────── WorkspaceChain ──────────┘
                       │
       ┌───────────────┼────────────────┐
       │               │                │
   RSTBackend     ExternalNeedsIndex    graph.impact_walk
   (write+read)   (pharaoh, read-only)  (BFS traversal)
```

- **`WorkspaceChain`** (`src/papyrus/workspace.py`) — merges multiple
  Papyrus workspaces for reads, routes writes to the scoped backend.
- **`RSTBackend`** (`src/papyrus/storage/rst.py`) — persists needs as
  RST blocks, parses them back, appends atomically.
- **`ExternalNeedsIndex`** (`src/papyrus/external.py`) — read-only
  loader over a pharaoh `needs.json`. Maps sphinx-needs' generic `links`
  field to `relates` edges and keeps typed edges (`satisfies`,
  `realizes`, `derived_from`, …) as their own types.
- **`impact_walk`** (`src/papyrus/graph.py`) — bidirectional BFS over
  the merged graph, depth-limited, optionally filtered by link type.
- **CLI** (`src/papyrus/cli.py`) — human-facing entry point. Commands
  include `init`, `add`, `recall`, `get`, `link`, `impact`, `trace`,
  `promote`.
- **MCP server** (`src/papyrus/mcp_server.py`) — same surface as the
  CLI, exposed over stdio for AI clients. See `docs/mcp-setup.md`.

## The impact walk

`impact <id>` starts from a node (Papyrus memory or pharaoh need) and
walks edges in both directions up to `--depth` hops. Forward edges
come from the node's own `links` list. Reverse edges are computed by
building an inverted index at query time. Each hit carries the path of
edge types traversed, so the caller can see *how* two nodes connect,
not just *that* they do.

Link-type filtering (`--link-type satisfies`) restricts traversal to
specific edge types, which is the main way to narrow a noisy result set
when a change only affects a particular kind of relationship.

## Configuration

A `papyrus.toml` at the workspace root (or any ancestor) defines:

- `[[papyrus.workspaces]]` — ordered workspace chain with scopes
- `[papyrus.external]` — binding to the pharaoh project whose
  `needs.json` Papyrus treats as the external requirement index
- `[papyrus.promote]` — rules for moving memories up the scope chain

See `src/papyrus/config.py` for the full schema.

## Storage format

Each scope has a single `memory.rst` (or multiple split files — backend
handles both) containing one sphinx-needs directive per memory:

```rst
.. dec:: DEC_use_mtls_with_cert_rotation
   :title: Use mutual TLS with CI-driven cert rotation
   :status: active
   :confidence: high
   :tags: topic:auth, topic:comms
   :satisfies: REQ_auth_mtls

   Rationale body. Alternatives considered. Non-obvious constraints.
```

Links are serialised as sphinx-needs option fields, keyed by link
type. An `ExternalNeedsIndex` load is symmetric: anything a pharaoh
project produces with sphinx-needs is consumable; anything Papyrus
writes is consumable by a pharaoh build without modification.

## Semantic search (optional)

Papyrus ships a sidecar vector index for similarity search. It is gated
by the `semantic` extra — install with `pip install papyrus[semantic]` —
and is **English-only**; the default model (`all-MiniLM-L6-v2`) is
trained on English corpora and gives poor recall on other languages.

The index lives in `<workspace>/.papyrus/vectors.npy` alongside a JSON
metadata file recording the model name, dimension, and per-need content
hash. On `papyrus rebuild-index` we re-embed only needs whose hash
changed and drop rows for needs that no longer exist.

Query flow (`papyrus recall --semantic -q "..."`):

1. Tag and type filters narrow the candidate pool using the existing
   lexical filter.
2. The query string is encoded with the same model and compared to
   candidate vectors by cosine similarity.
3. The top-K hits are rendered using the standard `brief / compact /
   full` formats. `--show-scores` prepends the similarity score
   (developer aid).

If `sentence-transformers` is not installed, `rebuild-index` silently
skips the vector step and `recall --semantic` reports a clean error
pointing at the extra.
