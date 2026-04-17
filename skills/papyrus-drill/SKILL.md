---
name: papyrus-drill
description: Atomic — fetch a single memory in full by id
---

# papyrus-drill

Return the full rendering of one memory. Opposite of `papyrus-query` peek.

## Atomicity

- (a) Indivisible: chain.find_by_id
- (b) Input: id. Output: rendered full Need or not-found error
- (c) Objective reward: rendered text contains id, type, title, body, all links
- (d) Reusable: every drill-down step
- (e) No interference: read-only

## Input / Output

```
input:
  id: non-empty string
output:
  stdout: full render (id, type, status, confidence, scope, title, tags, timestamps, links, body)
  exit: 0 on hit; non-zero with "not found" on miss
```

## Success criterion

```bash
papyrus get <id>   # exits 0, includes <id>, "Title:", and body (if non-empty)
```

## Workflow

```bash
papyrus get <id>
```

MCP tool `memory_get`:
```json
{"id": "FACT_x"}
```

## Composition examples

- Always preceded by `papyrus-query` in recall flows
- Can be fed to `shared/apply-memory.md` judgment for next action

## See also

- `papyrus-query` — composition partner
- `shared/apply-memory.md` — what to do with drill results
