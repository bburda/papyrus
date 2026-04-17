---
name: papyrus-query
description: Atomic — search memories by filter, return brief list
---

# papyrus-query

Filter memories across the workspace chain and return a compact list. Lockless.

## Atomicity

- (a) Indivisible: single filter pass over chain.resolve_read()
- (b) Input: tags + type + query + format. Output: list of needs in chosen format (string)
- (c) Objective reward: result count and content match filter spec against known corpus fixture
- (d) Reusable: every recall flow invokes this
- (e) No interference: read-only, no state mutation

## Input / Output

```
input:
  tags:    list[str] (AND semantics)
  type:    NeedType enum value or None
  query:   substring against title/body or None
  format:  brief|compact|full (default brief)
output:
  stdout: rendered needs (format-dependent)
  exit: 0
  in multi-workspace chain: [from: <scope>] annotation per need
```

## Success criterion

With a known corpus fixture, result matches expected id set for a given filter. E.g. given 3 needs with tags `[topic:x]`, `[topic:y]`, `[topic:x, topic:y]`, query `--tag topic:x --tag topic:y` returns exactly 1.

## Workflow

```bash
papyrus recall --tag topic:<domain> --type dec --format brief
```

MCP tool `memory_recall`:
```json
{"tags": ["topic:x"], "type": "dec", "format": "brief"}
```

## Composition examples

**Peek-then-drill** (composition with `papyrus-drill`):
1. `papyrus-query --format brief` — scan
2. If hit: `papyrus-drill <id>` — full content

**Trigger-based recall** (composition with `shared/when-to-recall.md`):
1. Detect trigger (before grep, before decision, etc.)
2. `papyrus-query` with narrow filter
3. Decide drill or move on

## See also

- `papyrus-drill` — composition partner
- `shared/when-to-recall.md` — judgment pattern for invocation triggers
