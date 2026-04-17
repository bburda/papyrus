# When to recall memory (judgment pattern)

**Subjective judgment pattern, not an atomic skill.** Agents consult it before invoking `papyrus-query`.

## The golden rule — encoded from Phase 0 learning

> Recall at **decision points**, NOT at session start.

Phase 0 H4 showed dump-all-at-start gives zero boost over cold session — LLM priors converge. Targeted recall at decision points captures the real value.

## Recall triggers

Before you:
- **grep / find for something you might have seen** → `papyrus-query` with relevant tag/query
- **decide between alternatives** → `papyrus-query --type dec --tag topic:<domain>`
- **author a requirement / spec** → `papyrus-query --type fact --tag topic:<module>`
- **pick a specific value** (error code, naming, threshold) → `papyrus-query --query "<concept>"`
- **resume work** across sessions on a known topic → `papyrus-query --tag topic:<project>`

## Anti-patterns

### Session-start memory dump
```
# DON'T:
papyrus query --format full   # floods context with everything
```

Why bad: LLM priors + floods tokens = zero signal-to-noise improvement (Phase 0 data).

### Broad untyped recall
```
# DON'T:
papyrus query --query "error"   # matches too many things
```

Why bad: recall works when narrow. Always filter by tag or type.

### Ignoring confidence
```
# DON'T:
papyrus query --format brief   # acts on `low` confidence memories as gospel
```

Why bad: memory can be stale/speculative. Inspect `confidence` (via `compact` format or `drill`) before acting.

## Pattern

```
1. Frame: "what am I about to do?"
2. Narrow: tag + type + optional query
3. Peek: `papyrus-query --format brief`
4. Decide: drill down or move on
5. If drill: `papyrus-drill <id>` → act on content
```

## Applies to which atomic skills

- `papyrus-query` — consult BEFORE forming query
- `papyrus-drill` — after promising brief hit
