# Impact analysis — graph semantics

Reference for how Papyrus treats the rationale-and-requirement graph. Not an atomic skill — see `papyrus-link`, `papyrus-impact`, `papyrus-trace` for the operational primitives wrapping the `papyrus link`, `papyrus impact`, and `papyrus trace` CLI commands.

## Node kinds

- **Papyrus needs** (`mem`, `dec`, `fact`, `pref`, `risk`, `goal`, `q`) — rationale nodes authored by agents and humans.
- **External pharaoh needs** (`REQ_*`, typically) — requirements loaded read-only from the configured `needs.json`. Papyrus never writes to external nodes.

## Edge types

Papyrus uses sphinx-needs-compatible typed links. Each has a direction and a semantic:

| Type | Direction | Semantic |
|------|-----------|----------|
| `relates` | loose | generic association |
| `supports` | a → b | a provides evidence for b |
| `depends` | a → b | a cannot be acted on without b |
| `supersedes` | new → old | new replaces old (chain-forming) |
| `contradicts` | a ↔ b | a and b cannot both hold |
| `extends` | child → parent | child refines parent |
| `derives` | child → parent | child is logically implied by parent |
| `satisfies` | rationale → requirement | rationale justifies the requirement |

## Bidirectional walk

`papyrus impact <id>` walks outgoing AND incoming edges of every node visited. "Impact" is symmetric: a change to a requirement affects linked decisions, and inspecting a decision needs the requirements it satisfies.

The walk's depth parameter bounds the radius; the default depth matches the CLI default and is enough to surface directly-linked items plus one level of indirection.

## External-pharaoh merging

When `papyrus.toml` declares `[papyrus.external]`, Papyrus loads the pharaoh `needs.json` and merges its needs as external nodes in the graph. This lets `papyrus impact REQ_x` reach Papyrus-authored DECs and RISKs that link to `REQ_x` without requiring pharaoh to know about Papyrus.

If the external file is missing or malformed, impact and trace handle it gracefully — the CLI surfaces an error, while the MCP server returns a WARNING line and proceeds with the internal-only graph.

## Supersession chains

`supersedes` edges form a chain: `v3 → v2 → v1`. `papyrus trace <id>` follows this chain and, when a link points to an external pharaoh id, surfaces a marker that the chain continues externally.
