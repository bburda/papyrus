---
name: papyrus-init
description: Atomic — create a Papyrus workspace at a given path
---

# papyrus-init

Initialize one Papyrus workspace at a filesystem path. Idempotent.

## Atomicity

- (a) Indivisible: single operation (create dir + conf.py + memory/*.rst skeletons)
- (b) Input: `path: Path`. Output: workspace directory exists with expected files
- (c) Objective reward: `(path / "conf.py").is_file() and (path / "memory" / "facts.rst").is_file()`
- (d) Reusable: invoked per workspace in a chain (`silos` = 1×, `program` = 2×, `enterprise` = 3×)
- (e) No interference: operates on a single path; multi-workspace setup is composition

## Input / Output

```
input:  path (filesystem path, absolute or relative)
output: side effect — workspace scaffold at path
        stdout: "Initialized Papyrus workspace at <path>"
        exit: 0
```

## Success criterion

After invocation:
```bash
test -f <path>/conf.py && test -f <path>/memory/facts.rst
```
Exit code 0 = success.

## Workflow

```bash
papyrus init .papyrus
```

For multi-workspace (composition):
```bash
papyrus init .papyrus
papyrus init ../program-papyrus
# Then write papyrus.toml to declare the chain.
```

## Composition examples

- **Setup silos project**: `papyrus-init` × 1
- **Setup program project**: `papyrus-init` × 2 (local + program)
- **Setup enterprise**: `papyrus-init` × 3 (local + program + org)

## See also

- `shared/scopes-and-promote.md` — presets that dictate how many times to invoke
- `papyrus-write` — first write after init
