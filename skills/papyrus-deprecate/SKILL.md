---
name: papyrus-deprecate
description: Atomic — mark a memory deprecated, optionally with supersedes link
---

# papyrus-deprecate

Retire a memory. One operation: set status=deprecated. Optional `by` adds a `supersedes` link to the replacement.

## Atomicity

- (a) Indivisible: status change (+ optional single link append)
- (b) Input: id + optional by. Output: deprecated need with link or unchanged if id missing
- (c) Objective reward: `backend.find_by_id(id).status == Status.DEPRECATED AND (by absent OR any link is supersedes→by)`
- (d) Reusable: every retirement flow
- (e) No interference: one memory, filelocked

## Input / Output

```
input:
  id:   non-empty string
  by:   optional replacement id
output:
  side effect: status=deprecated; if by given, links gets one SUPERSEDES link
  stdout: "Deprecated <id>" (+ " (superseded by <by>)" if by given)
  exit: 0 on success
```

## Success criterion

```bash
papyrus get <id>   # shows Status: deprecated; if by given, shows link supersedes → <by>
```

## Workflow

MCP tool `memory_deprecate`:
```json
{"id": "DEC_old", "by": "DEC_new"}
```

## Composition examples

**Supersession chain**:
1. `papyrus-write` new DEC_v3 (the replacement)
2. `papyrus-deprecate` DEC_v2 with `by=DEC_v3`
3. Chain: `DEC_v1 ← DEC_v2 ← DEC_v3 (active)`

**Pure retirement** (no replacement):
1. `papyrus-deprecate` DEC_old (no `by`)
2. Readers see status=deprecated, no pointer to successor.

## See also

- `papyrus-write` — create replacement before deprecating
- `shared/link-types.md` — supersedes semantics
