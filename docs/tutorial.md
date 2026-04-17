# Papyrus Tutorial — Hands-on in 10 minutes

This walks you through Papyrus's core flow — init, capture a decision,
link it to a requirement, traverse the impact graph — using real output
captured from a working install. If you follow the steps in order you
should see the same output on your machine.

Prerequisites: Papyrus installed (`uv pip install -e .` from the repo
root), and a shell.

---

## 1. Set up a scratch workspace

We'll simulate a tiny pharaoh project next to a Papyrus workspace. In a
real project, your pharaoh workspace already exists — you just point
Papyrus at it.

```bash
mkdir -p /tmp/papyrus-tutorial && cd /tmp/papyrus-tutorial

# mock pharaoh project with two requirements
mkdir -p pharaoh-mock
cat > pharaoh-mock/needs.json <<'EOF'
{
  "versions": {
    "1.0": {
      "needs": {
        "REQ_auth_mtls": {
          "id": "REQ_auth_mtls",
          "type": "req",
          "title": "ECU-to-ECU auth uses mTLS",
          "links": [],
          "satisfies": []
        },
        "REQ_log_retention": {
          "id": "REQ_log_retention",
          "type": "req",
          "title": "Diagnostic logs retained 90 days",
          "links": [],
          "satisfies": []
        }
      }
    }
  }
}
EOF

# papyrus config binding the two together
cat > papyrus.toml <<'EOF'
[papyrus]
preset = "silos"
default_write = "local"

[[papyrus.workspaces]]
path = "memory-ws"
scope = "local"

[papyrus.external]
pharaoh_workspace = "pharaoh-mock"
EOF
```

The `[papyrus.external]` section tells Papyrus where to find the
pharaoh `needs.json`. Papyrus will only read it — never write.

## 2. Initialise the Papyrus workspace

```bash
papyrus --workspace memory-ws init memory-ws
```

```
Initialized Papyrus workspace at memory-ws
```

This creates `memory-ws/conf.py`, `memory-ws/memory/`, and
`memory-ws/index.rst` — a minimal sphinx-needs sidecar.

## 3. Capture a decision

```bash
papyrus --workspace memory-ws add dec \
  "Use mutual TLS with certificate rotation via CI" \
  --body "Alternatives: TLS/PSK (rejected: key distribution pain), mTLS (chosen), DTLS (rejected: over-UDP not needed)." \
  --tags "topic:comms,safety" \
  --confidence high
```

```
Added DEC_use_mutual_tls_with_certificate_rotation_via_ci
```

Papyrus auto-generates the ID from the title. You can override with
`--id MY_ID`.

## 4. Capture a related risk

```bash
papyrus --workspace memory-ws add risk \
  "Cert rotation failure locks out ECUs" \
  --body "If CI pipeline breaks mid-rotation, half the fleet has old certs and half have new — no common trust anchor." \
  --tags "topic:comms,ops"
```

```
Added RISK_cert_rotation_failure_locks_out_ecus
```

## 5. Link the decision to the external requirement

This is the moment where Papyrus stops being "just another memory
system". The decision is about how we satisfy a specific requirement —
we say so explicitly:

```bash
papyrus --config papyrus.toml link \
  DEC_use_mutual_tls_with_certificate_rotation_via_ci \
  REQ_auth_mtls \
  --as satisfies
```

```
Linked DEC_use_mutual_tls_with_certificate_rotation_via_ci -satisfies-> REQ_auth_mtls
```

Now link the risk to the decision it's about:

```bash
papyrus --workspace memory-ws link \
  RISK_cert_rotation_failure_locks_out_ecus \
  DEC_use_mutual_tls_with_certificate_rotation_via_ci \
  --as relates
```

```
Linked RISK_cert_rotation_failure_locks_out_ecus -relates-> DEC_use_mutual_tls_with_certificate_rotation_via_ci
```

Note: when linking to an **external** pharaoh need (`REQ_auth_mtls`), we
need `--config papyrus.toml` so Papyrus knows where pharaoh lives. When
linking between two papyrus needs, `--workspace` is enough.

## 6. Recall everything you've captured

```bash
papyrus --workspace memory-ws recall --format brief
```

```
DEC_use_mutual_tls_with_certificate_rotation_via_ci [dec] Use mutual TLS with certificate rotation via CI
RISK_cert_rotation_failure_locks_out_ecus [risk] Cert rotation failure locks out ECUs
```

## 7. Drill into one memory

```bash
papyrus --workspace memory-ws get DEC_use_mutual_tls_with_certificate_rotation_via_ci
```

```
# DEC_use_mutual_tls_with_certificate_rotation_via_ci
Type: dec   Status: active   Confidence: high   Scope: local
Title: Use mutual TLS with certificate rotation via CI
Tags: topic:comms, safety
Created: 2026-04-16T10:26:41+00:00   Updated: 2026-04-16T10:26:42+00:00
Links:
  - satisfies -> REQ_auth_mtls

Alternatives: TLS/PSK (rejected: key distribution pain), mTLS (chosen), DTLS (rejected: over-UDP not needed).
```

## 8. Run an impact analysis

This is the differentiator. Someone wants to change `REQ_auth_mtls`.
What decisions, risks, or open questions are affected?

```bash
papyrus --config papyrus.toml impact REQ_auth_mtls --depth 3
```

```
[*] REQ_auth_mtls [external] — ECU-to-ECU auth uses mTLS
[1] DEC_use_mutual_tls_with_certificate_rotation_via_ci — Use mutual TLS with certificate rotation via CI  (satisfies)
[2] RISK_cert_rotation_failure_locks_out_ecus — Cert rotation failure locks out ECUs  (satisfies / relates)
```

Read it like this:

- `[*]` is the start node. `[external]` tells you it lives in pharaoh,
  not Papyrus.
- `[1]` at distance 1: our decision, reached via a `satisfies` edge.
- `[2]` at distance 2: the risk, reached via `satisfies` → `relates`.

Without Papyrus, finding this chain means grepping pharaoh,
grepping ADRs, asking the person who wrote the decision last month,
and hoping you caught everything. With Papyrus it's one command.

## 9. Reverse direction — what does our decision touch?

Impact is symmetric. Start from the decision and see everything it
connects to:

```bash
papyrus --config papyrus.toml impact DEC_use_mutual_tls_with_certificate_rotation_via_ci --depth 3
```

```
[*] DEC_use_mutual_tls_with_certificate_rotation_via_ci — Use mutual TLS with certificate rotation via CI
[1] REQ_auth_mtls [external] — ECU-to-ECU auth uses mTLS  (satisfies)
[1] RISK_cert_rotation_failure_locks_out_ecus — Cert rotation failure locks out ECUs  (relates)
```

## 10. Filter by link type

When a change is narrowly scoped, follow only certain edge types:

```bash
papyrus --config papyrus.toml impact REQ_auth_mtls --depth 3 --link-type satisfies
```

```
[*] REQ_auth_mtls [external] — ECU-to-ECU auth uses mTLS
[1] DEC_use_mutual_tls_with_certificate_rotation_via_ci — Use mutual TLS with certificate rotation via CI  (satisfies)
```

The risk doesn't show up — it's connected via `relates`, not `satisfies`.

## 11. Trace a single decision's history

```bash
papyrus --workspace memory-ws trace DEC_use_mutual_tls_with_certificate_rotation_via_ci
```

```
=== DEC_use_mutual_tls_with_certificate_rotation_via_ci — Use mutual TLS with certificate rotation via CI ===
type=dec status=active created=2026-04-16T10:26:41+00:00 updated=2026-04-16T10:26:42+00:00

Direct links:
  -satisfies-> REQ_auth_mtls
```

If the decision had superseded a previous one, `trace` would also print
the supersession chain (newest → oldest).

---

## What you just saw

- Memories are first-class sphinx-needs (same ID namespace, same link
  types, same storage).
- Links cross the boundary between Papyrus memories and pharaoh
  requirements via `[papyrus.external]`.
- `impact` traverses the graph in both directions — so one command
  replaces a lot of grepping.
- Everything is in git (`memory-ws/memory/*.rst` is diffable, reviewable
  in PRs).

## What's next

- [MCP setup for Claude Code and Copilot](mcp-setup.md) — let your AI
  agent call these same commands without dropping to a shell.
- [Architecture](architecture.md) — module layout and data model.
