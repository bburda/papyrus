---
name: memory-curator
description: GitHub Copilot agent indexing Papyrus atomic skills + judgment patterns
---

# memory-curator

Thin entry point for Copilot to discover Papyrus atomic skills and judgment patterns.

## Atomic skills (10)

Each skill is a single operation with objective success criterion:

**Write operations:**
- `papyrus-init` — create workspace
- `papyrus-write` — write one memory
- `papyrus-update-metadata` — patch fields
- `papyrus-deprecate` — mark deprecated (optionally with supersedes link)
- `papyrus-promote` — move to higher scope

**Read operations:**
- `papyrus-query` — filter + brief list
- `papyrus-drill` — full by id

**Meta operations:**
- `papyrus-rebuild-index` — regen .papyrus/index.json
- `papyrus-validate-links` — cross-ref check
- `papyrus-detect-stale` — overdue list

## Judgment patterns (subjective, reference only)

- `shared/when-to-capture.md` — before `papyrus-write`, apply the filter (Phase 0 LLM convergence)
- `shared/when-to-recall.md` — recall at decision points, not session start (Phase 0 H4)
- `shared/apply-memory.md` — how to respect / supersede / augment recalled memory

## Taxonomies (reference)

- `shared/memory-types.md` — 7 types + lifecycles
- `shared/link-types.md` — 7 link types + decision tree
- `shared/scopes-and-promote.md` — 3 scopes + presets + gating

## Typical composition flows

### Trigger-based authored capture
```
when-to-capture.md (judgment) → decision → papyrus-write (atomic)
```

### Peek-then-drill recall
```
when-to-recall.md (judgment) → trigger → papyrus-query (atomic) → papyrus-drill (atomic) → apply-memory.md (judgment)
```

### Verified promotion
```
papyrus-write (medium) → verify externally → papyrus-update-metadata (high) → papyrus-promote
```

### Supersession
```
papyrus-write (new) → papyrus-deprecate (old, by=new)
```

### Hygiene
```
papyrus-rebuild-index → papyrus-validate-links → papyrus-detect-stale
```

## Claude Code equivalents

Same atomic skills are available as Claude Code skills in `skills/`. Copilot and Claude share a single source of truth (shared/).
