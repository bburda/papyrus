# Contributing to Papyrus

## Dev setup

```bash
git clone https://github.com/useblocks/papyrus.git
cd papyrus
uv venv
uv pip install -e ".[dev]"
source .venv/bin/activate
```

## Checks before PR

```bash
ruff check src tests       # lint
pyright                    # type-check
pytest -v                  # tests
```

All three must pass on Python 3.10, 3.11, 3.12 (CI enforces).

## Pull requests

- Small, focused PRs preferred.
- Include tests for any new functionality.
- For changes to MCP tool surfaces or CLI commands, update the relevant
  docs in `docs/` in the same PR.

## Commit style

- Prefix with `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`
  as applicable.
- Reference the module you touched (e.g. `src/papyrus/graph.py`) in the
  commit body when it helps reviewers orient.

## Reporting bugs

Open a GitHub issue. If the problem is with MCP integration, include:

- Your client (Claude Code, Copilot, other)
- Output of `papyrus --version`
- Output of `papyrus mcp-serve` invoked manually (it should start and
  wait on stdin)
- The MCP client-side error log
