---
name: papyrus-detect-stale
description: Atomic — list memories whose review_after has passed
---

# papyrus-detect-stale

Scan corpus, return memories with `review_after < now()`.

## Atomicity

- (a) Indivisible: filter by time comparison
- (b) Input: corpus. Output: list of stale needs (rendered brief)
- (c) Objective reward: returned list = {need | need.review_after is not None AND need.review_after < now}
- (d) Reusable: review cycles, hygiene flows
- (e) No interference: read-only, no state

## Input / Output

```
input:
  (from chain.resolve_read())
  now: current UTC datetime
output:
  stdout: brief render of stale needs, or "(no stale needs)"
  exit: 0
```

## Success criterion

Given fixture with one need where `review_after = now - 1 day` and one without, result contains exactly the first.

## Workflow

MCP tool `memory_stale`:
```json
{}
```

## Composition examples

**Weekly review cycle**:
1. `papyrus-detect-stale`
2. For each stale: `papyrus-drill`, verify, then `papyrus-update-metadata` refresh review_after OR `papyrus-deprecate`

**Monthly audit**:
1. `papyrus-detect-stale`
2. Elevate high-value stale `mem` → `fact` via `papyrus-update-metadata`

## See also

- `papyrus-update-metadata` — refresh review_after after verification
- `papyrus-deprecate` — retire stale that no longer applies
- `shared/memory-types.md` — lifecycle expectations
