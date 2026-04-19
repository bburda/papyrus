---
name: papyrus-query
description: Atomic — search memories by filter (lexical or semantic), return ranked list
---

# papyrus-query

Filter memories across the workspace chain and return a compact list. Lockless.

Two modes:
- **Lexical (default):** substring against title/body combined with tag/type filters.
- **Semantic (opt-in, `--semantic`):** vector similarity over titles/bodies/tags. Requires `papyrus[semantic]` extra and a prior `papyrus-rebuild-index` to populate vectors.

## Atomicity

- (a) Indivisible: single filter pass over chain.resolve_read(), optionally followed by cosine rerank against `.papyrus/vectors.npy`
- (b) Input: tags + type + query + format + semantic? + top_k + show_scores. Output: list of needs in chosen format (string), ordered by similarity when semantic
- (c) Objective reward: result count and content match filter spec against known corpus fixture; in semantic mode, expected ids rank above unrelated ones
- (d) Reusable: every recall flow invokes this
- (e) No interference: read-only, no state mutation

## Input / Output

```
input:
  tags:        list[str] (AND semantics)
  type:        NeedType enum value or None
  query:       substring against title/body (lexical) OR query string (semantic)
  format:      brief|compact|full (default brief)
  semantic:    bool (default False) — switch to vector-similarity search
  top_k:       int (default 10) — max hits in semantic mode
  show_scores: bool (default False) — prepend cosine score per line (dev aid)
output:
  stdout: rendered needs (format-dependent); in semantic mode ordered by similarity
  exit: 0 on success; non-zero if --semantic without -q, or extra not installed
  in multi-workspace chain: [from: <scope>] annotation per need
```

## Success criterion

**Lexical:** with a known corpus fixture, result matches expected id set for a given filter. E.g. given 3 needs with tags `[topic:x]`, `[topic:y]`, `[topic:x, topic:y]`, query `--tag topic:x --tag topic:y` returns exactly 1.

**Semantic:** a query expressing a concept returns needs that relate by meaning even when they share no surface tokens. E.g. `-q temperature` ranks needs mentioning "celsius", "hot", "fahrenheit" above unrelated ones.

## Workflow

**Lexical:**
```bash
papyrus recall --tag topic:<domain> --type dec --format brief
```

**Semantic:**
```bash
papyrus recall --semantic -q "temperature" --top-k 5
papyrus recall --semantic -q "auth" --top-k 5 --show-scores   # dev: inspect cosine scores
```

Tag/type filters compose with `--semantic` (they narrow the candidate pool before cosine rerank).

MCP tool `memory_recall`:
```json
{"tags": ["topic:x"], "type": "dec", "format": "brief"}
```
```json
{"semantic": true, "query": "temperature", "top_k": 5}
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
- `papyrus-rebuild-index` — must run first before `--semantic` to populate vectors
- `shared/when-to-recall.md` — judgment pattern for invocation triggers
