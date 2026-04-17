# Scopes and promote (taxonomy)

## Three scopes

| Scope | Visibility | Content |
|---|---|---|
| `local` | this repo only | observations, draft decisions, per-repo facts |
| `program` | all repos in a program | shared decisions, cross-module facts, preferences |
| `org` | across programs | org-wide conventions, long-term gotchas |

## Presets (papyrus.toml)

- `silos` — only `.papyrus` per repo
- `program` — local + sibling aggregator (most common)
- `oss-friendly` — aggregator only (source repos untouched)
- `enterprise` — all 3 layers with RBAC mapping

## Promote gating (defaults)

| Target | Required confidence | Human review |
|---|---|---|
| `program` | `high` | optional |
| `org` | `high` | required |

Override in `papyrus.toml`:
```toml
[papyrus.promote]
to_program_requires_confidence = "high"
to_org_requires_confidence = "high"
to_org_requires_human_review = true
```

## Promote flow

1. Validate confidence ≥ required
2. Append to target workspace
3. Delete from source workspace
4. Preserve links (cross-workspace refs OK)

Promote errors: same-scope, unknown id, target not configured, confidence too low.
