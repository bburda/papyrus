# How to apply recalled memory (judgment pattern)

**Subjective judgment pattern, not an atomic skill.** Agents consult it after `papyrus-drill` returns relevant content.

## Respect hierarchy

When memory applies to current work:

1. **Decisions (`dec`)** — follow them. They were made with context you may not have.
2. **Facts (`fact`)** — use the specific values (error codes, names, limits).
3. **Preferences (`pref`)** — match the convention.
4. **Risks (`risk`)** — do NOT re-introduce the problem. Design around.
5. **Open questions (`q`)** — factor into work or answer them if possible.
6. **Observations (`mem`)** — treat as hints, verify before acting.

## When memory conflicts with your instinct

**Default: prefer memory.** Prior session had context you may lack.

**Exception:** if you have **new information** that invalidates the prior decision:
1. Don't ignore memory silently.
2. Use `papyrus-update-metadata` to demote confidence, or
3. Use `papyrus-deprecate` with `--by <new_decision>` to supersede.

## Staleness check

If memory has `review_after` in the past OR `status=review`:
- Treat as hint, verify before acting.
- Consider running `papyrus-update-metadata` with new `review_after` after verifying.

## Applies to which atomic skills

- After `papyrus-query` + `papyrus-drill`: use this doc to decide how to integrate findings.
- Drives invocation of `papyrus-update-metadata`, `papyrus-deprecate`, or `papyrus-write` (for new context).
