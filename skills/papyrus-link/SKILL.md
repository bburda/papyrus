---
name: papyrus-link
description: Atomic — add one typed edge between two needs
---

# papyrus-link

Create one typed directed edge from a source need to a target need. The target may live in the same Papyrus workspace or in a configured external pharaoh workspace.

## Atomicity

- (a) Indivisible: one edge appended to the source need's RST, filelocked
- (b) Input: mem_id, target_id, link_type. Output: updated source need with the new edge, or ClickException on unknown source / unknown target / invalid link_type
- (c) Objective reward: `papyrus get <mem_id>` shows `<link_type>: <target_id>` in the rendered output
- (d) Reusable: every capture-and-link flow, cross-scope connection, post-hoc graph enrichment
- (e) No interference: filelock on the source workspace serialises writes; target read is lockless

## Input / Output

```
input:
  mem_id:     existing need id in current workspace chain
  target_id:  existing id in the chain OR in a configured external pharaoh workspace
  link_type:  one of: relates, supports, depends, supersedes, contradicts, extends, derives, satisfies
output:
  side effect: append edge to source need's RST directive (no-op if triple already present)
  stdout: "Linked <mem_id> -<link_type>-> <target_id>"
  exit:   0 on success; non-zero on unknown id or invalid link_type
```

## Success criterion

After invocation:
```bash
papyrus get <mem_id> | grep ":<link_type>:" | grep "<target_id>"
```
Exits 0 = success.

## Workflow

CLI:
```bash
papyrus link <mem_id> <target_id> --as <link_type>
```

MCP tool `memory_link`:
```json
{"mem_id": "DEC_foo", "target_id": "REQ_bar", "link_type": "satisfies"}
```

## Composition examples

**Capture-and-link** (most common flow):
1. `papyrus-write` new DEC/RISK
2. `papyrus-link` to the requirement or parent decision it's about

**Cross-scope link** (after promote):
1. `papyrus-promote --to program` elevates the need
2. `papyrus-link` from the promoted need to a program-scope requirement

**Retrofit graph** (hygiene flow):
1. `papyrus-query` to find orphan needs (no outgoing links)
2. For each: inspect, then `papyrus-link` to appropriate target

## See also

- `shared/link-types.md` — semantics of each link_type
- `papyrus-write` — typical predecessor
- `papyrus-impact` — consumer of the graph built by link
- `papyrus-trace` — consumer for supersession chains
