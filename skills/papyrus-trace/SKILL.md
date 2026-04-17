---
name: papyrus-trace
description: Atomic — follow supersession chain and direct links of one need
---

# papyrus-trace

Print the supersession chain (what this need supersedes, recursively) and direct typed links of one need. Focused variant of impact for historical walks.

## Atomicity

- (a) Indivisible: one read over the chain + direct edge enumeration, read-only
- (b) Input: mem_id. Output: header + direct links + supersession chain (newest → oldest)
- (c) Objective reward: fixture with chain of length N produces N lines in chain output
- (d) Reusable: audit flows, decision history, deprecation review
- (e) No interference: read-only

## Input / Output

```
input:
  mem_id:  starting need id
output:
  stdout:  "=== <id> — <title> ===" header with type/status/created/updated line
           "Direct links:" section (when any) grouped by link type
           "Supersession chain (newest → oldest):" section (when any), one id per line
  exit:    0 on success; non-zero if id not found
```

When the chain crosses into an external pharaoh workspace, a marker line is printed: `(chain continues into external pharaoh: <id> — <title>)`.

## Success criterion

Given fixture where `DEC_v3 supersedes DEC_v2 supersedes DEC_v1`:
```bash
papyrus trace DEC_v3
```
Output includes all three ids on separate lines in the supersession chain section.

## Workflow

CLI:
```bash
papyrus trace <mem_id>
```

MCP tool `memory_trace`:
```json
{"mem_id": "DEC_current"}
```

## Composition examples

**Deprecation audit**:
1. `papyrus-query --status deprecated` lists deprecated needs
2. For each: `papyrus-trace` shows what replaced it

**Decision history**:
1. Before writing a new DEC, `papyrus-trace` on the related topic finds prior versions
2. New DEC uses a `supersedes` link to continue the chain

**Change-request context**:
1. Change request touches a need
2. `papyrus-trace` on that need shows whether it's the latest version or already superseded

## See also

- `papyrus-impact` — broader bidirectional graph walk
- `papyrus-deprecate` — common producer of supersession chains
- `shared/impact-analysis.md` — graph semantics
