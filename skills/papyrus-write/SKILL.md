---
name: papyrus-write
description: Atomic — write a single new memory to a workspace
---

# papyrus-write

Persist one memory record. Single atomic append.

## Atomicity

- (a) Indivisible: one Need → one RST directive appended → filelocked
- (b) Input: type, title, body, tags, confidence, scope, links, source, id?. Output: created need (via backend.append_need) or ValueError on duplicate id
- (c) Objective reward: `backend.find_by_id(id) is not None AND need content matches input`
- (d) Reusable: every capture flow invokes this once per memory
- (e) No interference: filelock serialises writes; no shared in-memory state

## Input / Output

```
input:
  type:        NeedType enum value (mem|dec|fact|pref|risk|goal|q)
  title:       non-empty string
  body:        string (default "")
  tags:        list[str] (topic:X / scope:Y convention)
  confidence:  low|medium|high (default medium)
  scope:       local|program|org (default local)
  links:       list of {type: LinkType, target: need_id}
  source:      string (default "")
  id:          optional override; else auto from title
output:
  side effect: append directive to memory/<plural>.rst
  stdout: "Added <id> to <scope>"
  exit: 0 on success; non-zero on duplicate id or validation error
```

## Success criterion

```bash
papyrus get <id>   # exits 0 and prints the written content
```

## Workflow

```bash
papyrus add <type> "<title>" \
  --body "<body>" \
  --tags "topic:X,topic:Y" \
  --confidence <low|medium|high> \
  --scope <local|program|org> \
  --relates <other_id>
```

MCP tool `memory_add`:
```json
{"type": "dec", "title": "...", "body": "...", "tags": [...], "confidence": "high"}
```

## Composition examples

**Authored capture** (composition with `shared/when-to-capture.md` judgment):
1. Consult when-to-capture filter → pass/skip
2. If pass: `papyrus-write`

**Capture + link** (most common flow):
1. `papyrus-write` new DEC/RISK/FACT
2. `papyrus-link` from the new id to the requirement or parent decision it's about

**Capture + promote** (cross-skill composition):
1. `papyrus-write` at scope=local, confidence=medium
2. Verify fact
3. `papyrus-update-metadata` set confidence=high
4. `papyrus-promote --to program`

**Deprecate + replace**:
1. `papyrus-write` new version
2. `papyrus-deprecate` old version with `by=<new_id>`

## See also

- `shared/memory-types.md` — choosing type
- `shared/link-types.md` — choosing link types and when to link during capture
- `shared/when-to-capture.md` — subjective filter BEFORE invoking
- `papyrus-link` — atomic skill to add a link after writing
