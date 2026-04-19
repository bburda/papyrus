---
name: papyrus-rebuild-index
description: Atomic — regenerate .papyrus/index.json and (optionally) semantic vectors for a workspace
---

# papyrus-rebuild-index

Rebuild the JSON index for one workspace. Picks up external edits to RST files. When the optional `papyrus[semantic]` extra is installed, also re-embeds needs whose content hash changed into `<workspace>/.papyrus/vectors.npy` (and drops vectors for needs that no longer exist). Semantic reindex failures are swallowed so the base JSON rebuild never breaks.

## Atomicity

- (a) Indivisible: load_needs → write index.json → (if extra installed) incremental vector reindex, all under one filelock
- (b) Input: scope (which workspace). Output: count of needs written
- (c) Objective reward: `<workspace>/.papyrus/index.json` exists and contains exactly `count` needs; when extra is installed, `vectors.npy` exists with one row per current need
- (d) Reusable: after bulk edits, merge conflicts, verify flows
- (e) No interference: single workspace, filelocked

## Input / Output

```
input:
  workspace: scope name (local|program|org); defaults to default_write
output:
  side effect: <workspace>/.papyrus/index.json rewritten
                <workspace>/.papyrus/vectors.npy + vectors_meta.json rewritten if papyrus[semantic] installed
  stdout: "Rebuilt index for <scope>: <N> needs"
  exit: 0
```

## Success criterion

After invocation:
```bash
test -f <workspace>/.papyrus/index.json
# plus, when papyrus[semantic] is installed:
test -f <workspace>/.papyrus/vectors.npy
```
And parsed JSON has `"needs": [...]` list of length N.

## Workflow

MCP tool `memory_rebuild`:
```json
{"workspace": "local"}
```

## Composition examples

**After manual RST edit**:
1. Edit RST file by hand (fix parse issue)
2. `papyrus-rebuild-index` to refresh `.papyrus/index.json`
3. `papyrus-validate-links` to check integrity

**Pre-commit hygiene**:
1. `papyrus-rebuild-index` for each workspace
2. `papyrus-validate-links`
3. Commit with rebuilt index

## See also

- `papyrus-validate-links` — often chained after rebuild
- `papyrus-query` — `--semantic` mode depends on a prior rebuild to populate vectors
