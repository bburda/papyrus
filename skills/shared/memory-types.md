# Papyrus memory types (taxonomy)

Papyrus has 7 memory types. Each is a different *kind* of knowledge with different lifecycle expectations.

## Decision tree — which type?

| Question | Type | Prefix |
|---|---|---|
| Decision after weighing alternatives? | `dec` | `DEC_` |
| Verified fact (observed, reproducible)? | `fact` | `FACT_` |
| Raw observation / note to review later? | `mem` | `MEM_` |
| Team convention or preference? | `pref` | `PREF_` |
| Risk / open concern / assumption? | `risk` | `RISK_` |
| Goal or objective? | `goal` | `GOAL_` |
| Open question awaiting answer? | `q` | `Q_` |

## Lifecycles

| Type | Expiry | Typical confidence |
|---|---|---|
| `dec` | never auto-expires; superseded | high |
| `fact` | `review_after` ~180 days | high after verification |
| `mem` | `review_after` ~30 days | medium (auto-capture default) |
| `pref` | `review_after` ~365 days | high |
| `risk` | when retired/materialised | medium |
| `goal` | when achieved/cancelled | high |
| `q` | when answered | low |

## Confidence

- `low` — speculative, not verified
- `medium` — evidence present, could be wrong (default for auto-capture)
- `high` — verified, reproducible (promote-ready)

## Related

- `shared/link-types.md` — how memories connect
- `shared/scopes-and-promote.md` — scope ladder + promote gating
- `shared/when-to-capture.md` — subjective filter before writing
