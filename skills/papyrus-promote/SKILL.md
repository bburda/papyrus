---
name: papyrus-promote
description: Atomic — move a memory from its current scope to a higher scope
---

# papyrus-promote

Move one memory from its current workspace to a higher-scope workspace. Preserves links, validates confidence gating.

## Atomicity

- (a) Indivisible: append-to-target + delete-from-source (dual-locked)
- (b) Input: id + target_scope. Output: moved need or PromoteError
- (c) Objective reward: `target_workspace.find_by_id(id) is not None AND source_workspace.find_by_id(id) is None AND links preserved`
- (d) Reusable: any scope ladder step (local→program, program→org)
- (e) No interference: scope-sorted dual-lock prevents deadlock with concurrent reverse promotes

## Input / Output

```
input:
  id:      non-empty string
  to:      target scope (local|program|org)
output:
  side effect: memory moved between workspace RST files
  stdout: "Promoted <id> to <scope>"
  exit: 0 on success; non-zero on confidence rejection, unknown id, unconfigured target, or same-scope attempt
```

## Success criterion

```bash
papyrus --config papyrus.toml recall   # <id> shows [from: <target_scope>]
```

## Workflow

```bash
papyrus --config papyrus.toml promote <id> --to <scope>
```

MCP tool `memory_promote`:
```json
{"id": "FACT_x", "to": "program"}
```

## Composition examples

**Verified fact promotion**:
1. `papyrus-write` at local, confidence=medium
2. Independent verification
3. `papyrus-update-metadata` set confidence=high
4. `papyrus-promote --to program`

**Org-wide convention**:
1. Memory lives at `program` scope across several programs
2. Consensus reached; `papyrus-promote --to org` (requires human review flag typically)

## See also

- `shared/scopes-and-promote.md` — gating rules
- `papyrus-update-metadata` — elevate confidence before promote
