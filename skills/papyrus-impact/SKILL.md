---
name: papyrus-impact
description: Atomic — bidirectional graph walk from a starting need
---

# papyrus-impact

Traverse the rationale graph outward from a starting need, following typed edges in both directions up to a depth limit. Returns every reachable need with its distance and the path of edge types taken.

## Atomicity

- (a) Indivisible: one BFS over the merged internal + external graph, read-only
- (b) Input: need_id, depth, optional link_types filter. Output: ordered list of hits (id, distance, path)
- (c) Objective reward: on a fixture with known edges, returned id set equals expected set
- (d) Reusable: change-request review, decision drill-down, risk surface analysis
- (e) No interference: read-only, no shared state

## Input / Output

```
input:
  need_id:    starting need id (must exist in chain or external index)
  depth:      max hops from start (default 3)
  link_types: optional list filter (relates, supports, ...); empty = all types
              CLI: pass --link-type repeatedly (one per type)
output:
  stdout:  lines of "[<distance-or-*>] <id>[ [<kind>]] — <title>  (<edge/edge/...>)"
           ordered by BFS discovery
  exit:    0 on success; non-zero if start id not found
```

## Success criterion

Given fixture where `DEC_a --relates--> REQ_b --depends--> DEC_c`:
```bash
papyrus impact DEC_a --depth 2 | grep -c "^"
```
Returns 3 (DEC_a at distance 0, REQ_b at 1, DEC_c at 2).

## Workflow

CLI:
```bash
papyrus impact <need_id> --depth <N> [--link-type relates --link-type supports]
```

MCP tool `memory_impact`:
```json
{"need_id": "REQ_auth", "depth": 2}
```

If the configured external pharaoh workspace is unavailable, the CLI raises a ClickException; when it loads, external nodes are merged into the graph (local nodes win on id collision).

## Composition examples

**Change-request review**:
1. Change request touches REQ_x
2. `papyrus-impact REQ_x --depth 2` surfaces connected DECs and RISKs
3. Reviewer inspects each hit via `papyrus-drill`

**Decision drill-down**:
1. `papyrus-drill DEC_y` shows the decision itself
2. `papyrus-impact DEC_y --depth 1` shows direct requirements it relates to and risks it raised

**Risk surface**:
1. `papyrus-query --type risk` lists all risks
2. For each: `papyrus-impact RISK_z` shows what requirements it affects

## See also

- `shared/impact-analysis.md` — semantics of the bidirectional graph walk
- `papyrus-link` — primitive that builds the graph
- `papyrus-trace` — focused variant for supersession chains
- `papyrus-drill` — natural follow-up to inspect any hit
