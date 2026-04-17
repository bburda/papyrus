# Papyrus link types (taxonomy)

7 link types between memories.

| Link | Meaning | Reverse |
|---|---|---|
| `relates` | loose connection | `related_by` |
| `supports` | A is evidence for B | `supported_by` |
| `depends` | A needs B to hold | `depended_by` |
| `supersedes` | A replaces B | `superseded_by` |
| `contradicts` | A incompatible with B | `contradicted_by` |
| `extends` | A adds to B | `extended_by` |
| `derives` | A derived from B | `derived_by` |

## Decision tree

- Both valid, touch same topic? → `relates` (loose) or `extends` (additive)
- A provides reason B is true? → `supports`
- Need B true before A makes sense? → `depends`
- New replaces old? → `supersedes` (old becomes deprecated)
- Two conflicting, neither authoritative? → `contradicts`
- A inferred from B's data? → `derives`

## Chains

### Supersession (evolving decision)
```
DEC_v1 ← superseded_by ← DEC_v2 ← superseded_by ← DEC_v3 (active)
```

### Support
```
FACT_x → supports → DEC_y → depends → DEC_z
```

### Contradicts (unresolved)
```
DEC_a ← contradicts → DEC_b
```
Resolution: promote one, deprecate the other.

## When to link during capture

Most decisions, risks, and open questions exist in response to a requirement. Capturing them without linking leaves the rationale graph disconnected — and makes `papyrus impact` less useful.

Rule of thumb:

- Capturing a `dec` or `risk` about how to satisfy REQ-X? Use `satisfies`.
- Capturing a `dec` that refines or constrains a parent decision? Use `derives` or `extends`.
- Capturing a `dec` that replaces a previous one? Use `supersedes` on the old id.
- Capturing free-floating `mem` observations? Linking is optional — but if the observation is about a specific requirement, link it.

Target ids may live in the Papyrus workspace or in a configured external pharaoh workspace (see `papyrus.toml`'s `[papyrus.external]` section). Linking is performed by the `papyrus-link` atomic skill after `papyrus-write`.
