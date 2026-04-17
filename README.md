# Papyrus

**Rationale-as-code layer for [sphinx-needs](https://sphinx-needs.readthedocs.io/) and [Pharaoh](https://github.com/useblocks/pharaoh).**

Papyrus stores AI-agent decisions, risks, facts, and open questions as
first-class sphinx-needs, linked to your requirements via the same link
types Pharaoh already uses (`satisfies`, `derives`, `extends`,
`supersedes`). The differentiator: `papyrus impact <req-id>` walks the
memory↔requirement graph and returns the full chain of decisions and
risks affected by a change request.

## Install

```bash
git clone https://github.com/useblocks/papyrus.git
cd papyrus
uv venv
uv pip install -e .
source .venv/bin/activate
```

Verify:

```bash
papyrus --version
```

## Quick start

```bash
papyrus init /tmp/memory-ws
papyrus --workspace /tmp/memory-ws add dec "Use bcrypt for password hashing" --confidence high
papyrus --workspace /tmp/memory-ws recall --format brief
```

The full flow — linking to an external pharaoh requirement, running
impact analysis, tracing a decision's history — is walked through in
[`docs/tutorial.md`](docs/tutorial.md).

## AI agent integration

Papyrus ships an MCP server with 12 tools (recall, add, link, impact,
trace, …). Wire it into your client:

**Claude Code:**

```bash
claude mcp add papyrus -- papyrus mcp-serve
```

**GitHub Copilot (VS Code)** — add to `.vscode/mcp.json`:

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

Both are detailed in [`docs/mcp-setup.md`](docs/mcp-setup.md) with
verification steps and troubleshooting.

## Design

- **Rationale linked to requirements, not free-floating memory.** A
  decision without a linked requirement is an unmotivated opinion.
- **Impact analysis as the primary query.** `papyrus impact <req-id>`
  traverses the memory↔requirement graph in both directions — one
  command replaces a lot of grepping.
- **Sidecar, not invasion.** Papyrus workspaces live beside source
  repos. Linking goes through canonical sphinx-needs IDs; source repos
  are never modified.
- **Selective capture.** Store what would NOT be re-derived by a fresh
  agent: arbitrary choices, historical gotchas, project-specific
  conventions. Skip the rest.

## Docs

- [`docs/tutorial.md`](docs/tutorial.md) — hands-on 10-minute walkthrough
- [`docs/mcp-setup.md`](docs/mcp-setup.md) — Claude Code + Copilot integration
- [`docs/architecture.md`](docs/architecture.md) — module layout and data model

## Development

```bash
uv pip install -e ".[dev]"
pytest -v
ruff check src tests
pyright
```

All three must pass on Python 3.10, 3.11, 3.12 (CI enforces). See
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT — see [`LICENSE`](LICENSE).
