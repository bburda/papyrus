---
name: papyrus-validate-links
description: Atomic — verify every link target exists in the corpus
---

# papyrus-validate-links

Scan all memories and ensure every link's target exists in the corpus. Raises on first broken link.

## Atomicity

- (a) Indivisible: one pass over corpus, set membership check
- (b) Input: corpus (list[Need]). Output: None on OK, UnknownTargetError on broken
- (c) Objective reward: return without exception iff all targets are known ids
- (d) Reusable: verify flows, CI
- (e) No interference: read-only

## Input / Output

```
input:
  (from chain.resolve_read())
output:
  return: None on success
  raise: UnknownTargetError("<src_id> -> <link_type> -> <missing_target_id>") on broken
```

## Success criterion

```python
from papyrus.links import validate_links
validate_links(needs)  # returns None
```

## Workflow

Currently Python-only (future: `papyrus verify --links` CLI).

```python
from papyrus.config import load_config
from papyrus.workspace import WorkspaceChain
from papyrus.links import validate_links, UnknownTargetError

cfg = load_config(".")
chain = WorkspaceChain.from_config(cfg, base=".")
needs = [sn.need for sn in chain.resolve_read()]
try:
    validate_links(needs)
    print("OK")
except UnknownTargetError as e:
    print(f"broken: {e}")
```

## Composition examples

**Pre-commit**:
1. `papyrus-rebuild-index`
2. `papyrus-validate-links` — fail commit if broken

**Post-merge**:
1. Resolve RST conflicts
2. `papyrus-rebuild-index`
3. `papyrus-validate-links`

## See also

- `papyrus-rebuild-index` — typical predecessor
- `shared/link-types.md` — what constitutes a valid target
