---
name: papyrus-update-metadata
description: Atomic — patch mutable fields of an existing memory
---

# papyrus-update-metadata

Patch one memory's mutable fields (body, title, tags, confidence, scope, status, source, links). Immutable fields (id, type, created_at) rejected.

## Atomicity

- (a) Indivisible: single update_need call, filelocked
- (b) Input: id + patch dict. Output: updated Need or KeyError/ValueError
- (c) Objective reward: reload by id, check patched fields match input
- (d) Reusable: invoked whenever metadata needs change (confidence elevation, review_after refresh, tag reorganisation)
- (e) No interference: operates on one memory under filelock

## Input / Output

```
input:
  id:     non-empty string
  patch:  dict with any subset of {body, title, tags, confidence, scope, status, source, links}
output:
  side effect: rewrites memory/<plural>.rst with patched need; updated_at refreshed
  stdout: "Updated <id>"
  exit: 0 on success; non-zero on unknown id or immutable-field attempt
```

## Success criterion

```bash
papyrus get <id>   # exits 0 and shows patched fields
```

## Workflow

MCP tool `memory_update`:
```json
{"id": "FACT_x", "body": "corrected", "confidence": "high"}
```

## Composition examples

**Elevate confidence after verification**:
1. `papyrus-query` + `papyrus-drill` — confirm memory holds
2. Verify independently (code inspection, test run)
3. `papyrus-update-metadata` set confidence=high
4. Optionally: `papyrus-promote` to higher scope

**Extend review window**:
1. `papyrus-detect-stale` returns overdue `fact` X
2. Verify X still true
3. `papyrus-update-metadata` reset `review_after` to `now + 180 days`

## See also

- `papyrus-deprecate` — for retirement (distinct operation)
- `shared/apply-memory.md` — when conflict justifies update vs supersede
