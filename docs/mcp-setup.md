# MCP Setup — Claude Code & GitHub Copilot

Papyrus ships an MCP (Model Context Protocol) server that exposes 12
tools: read (recall, get, tags, stale), write (add, update, deprecate,
promote, rebuild), and rationale-layer (link, impact, trace). This doc
shows how to wire it into Claude Code and GitHub Copilot so your agent
uses Papyrus without dropping to a shell.

Prerequisites: Papyrus installed and on `$PATH` (`which papyrus` should
resolve), and your project has either `papyrus.toml` at the workspace
root, or a Papyrus workspace you can point at via `PAPYRUS_WORKSPACE`.

The MCP server launches with:

```bash
papyrus [--workspace PATH | --config PATH] mcp-serve
```

Over stdio. Both flags are optional; defaults follow the CLI's own
rules (`$PAPYRUS_WORKSPACE` → CWD's `papyrus.toml` → CWD itself).

---

## Claude Code

Claude Code ships `claude mcp` for managing MCP servers. Pick one of the
three patterns below depending on how you want Papyrus scoped.

### Pattern 1 — per-project (recommended)

From your project root (where `papyrus.toml` lives):

```bash
claude mcp add papyrus -- papyrus mcp-serve
```

The server inherits the CWD of your Claude Code session; any Papyrus
command it runs resolves the workspace from `papyrus.toml` in that
directory. If you move projects, the config follows because each
project owns its own `papyrus.toml`.

### Pattern 2 — global with env-var workspace

When you want one Papyrus workspace across all sessions:

```bash
claude mcp add papyrus \
  --env PAPYRUS_WORKSPACE=/absolute/path/to/memory-ws \
  -- papyrus mcp-serve
```

### Pattern 3 — global with explicit config

When you prefer routing through a config file (e.g. for the
`[papyrus.external]` pharaoh binding):

```bash
claude mcp add papyrus -- papyrus --config /absolute/path/to/papyrus.toml mcp-serve
```

### Verification

Restart Claude Code, then:

```
/mcp
```

You should see `papyrus` listed with 12 tools. Ask the agent:

> "Use papyrus to add a decision: 'Use bcrypt for password hashing',
> confidence high, tagged topic:auth."

The agent should call `memory_add` and report back the generated ID.

---

## GitHub Copilot (VS Code)

Copilot Chat in VS Code supports MCP via workspace- or user-level
config. Use the workspace-level file so the binding travels with the
repo.

### Workspace config — `.vscode/mcp.json`

```json
{
  "servers": {
    "papyrus": {
      "command": "papyrus",
      "args": ["mcp-serve"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

If you need an explicit config file:

```json
{
  "servers": {
    "papyrus": {
      "command": "papyrus",
      "args": ["--config", "${workspaceFolder}/papyrus.toml", "mcp-serve"]
    }
  }
}
```

Reload VS Code. The Copilot Chat sidebar should show Papyrus tools
available; they surface in `@workspace` queries and on explicit
agent invocations.

### Verification

In a Copilot Chat session:

> "@workspace Use the papyrus tool to recall memories tagged
> topic:auth."

Copilot should call `memory_recall` and return the matching memories.

---

## Tools exposed over MCP

| Tool              | What it does                                               |
|-------------------|------------------------------------------------------------|
| `memory_recall`   | Search memories by tag/type/query, brief/compact/full      |
| `memory_get`      | Fetch one memory by id, full body + links                  |
| `memory_tags`     | Aggregate tag counts across all workspaces                 |
| `memory_stale`    | List memories whose `review_after` has passed              |
| `memory_add`      | Append a new memory (dec/fact/mem/pref/risk/goal/q)        |
| `memory_update`   | Update mutable fields (body, status, confidence, tags, …)  |
| `memory_deprecate`| Mark deprecated; optionally link supersedes via `by`       |
| `memory_promote`  | Move a memory to a higher scope (local → program → org)    |
| `memory_rebuild`  | Rebuild the workspace's `.papyrus/index.json`              |
| `memory_link`     | Attach typed edge (memory → memory or memory → pharaoh)    |
| `memory_impact`   | BFS over memory↔requirement graph from a given id          |
| `memory_trace`    | Show one memory's direct links + supersession chain        |

All write operations are serialized per workspace via asyncio locks
(safe for concurrent agents).

---

## Troubleshooting

**Server exits immediately.** Run `papyrus mcp-serve` manually in a
shell with the same env the agent sees — it'll print the actual error.
Most common: Papyrus workspace path resolves to something unexpected.
Add `--workspace /abs/path` to the MCP args to be explicit.

**`memory_link` / `memory_impact` don't see pharaoh requirements.**
The server must load with a `--config papyrus.toml` that has
`[papyrus.external]` set. Pattern 1 handles this automatically when
the toml lives at the workspace root; Patterns 2-3 need the config
flag.

**Tool calls return empty.** Check `papyrus --workspace <path> recall
--format brief` from the same shell. If that's empty, the workspace
itself is empty — the agent is fine, there's just nothing there yet.

---

## See also

- [Tutorial](tutorial.md) — CLI flow that the MCP tools mirror.
- [Architecture](architecture.md) — module layout and data model.
