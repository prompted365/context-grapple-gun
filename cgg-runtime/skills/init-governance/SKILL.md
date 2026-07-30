---
name: init-governance
description: |
  Bootstrap or repair the project-local CGG governance zone after the Claude Code plugin is installed. Creates missing .ticzone/.ticignore/audit paths, appends the governed Session Learning Protocol, verifies the loaded plugin inventory, and leaves a receipt. It does not copy plugin components or rewrite Claude settings; the Claude plugin manager and npm installer own distribution.

  CENTROID:
  project governance-zone bootstrap and repair

  IS:
  - project-zone creation and repair
  - non-destructive .ticzone/.ticignore initialization
  - audit directory creation
  - idempotent convention append
  - loaded-plugin and zone verification
  - optional rung marker and initial tic creation

  IS NOT:
    collapse_zones:
      - Claude plugin installer or updater
      - npm package publisher
      - settings.json editor
      - canonical-to-installed runtime copier
      - governance judgment or lesson promotion
      - cadence owner except for an explicitly requested bootstrap tic
      - user-authored governance overwriter

  WHEN:
  - after a direct GitHub marketplace installation
  - when npm installation completed but project zone surfaces are missing
  - when a zone needs a non-destructive repair and verification pass
  - when a rung marker or initial bootstrap tic is explicitly requested

  NOT WHEN:
  - before the CGG plugin is installed and visible to Claude Code
  - when the user is asking to update or publish the npm package
  - when existing zone files require semantic modification rather than missing-surface repair
  - when enterprise policy blocks the applicable operation

  ARGS:
    stance: dispatch
    off_envelope: ask
    core_dispatch_rays:
      - ""                                 → bootstrap/repair and verify
      - "--dry-run"                        → report intended changes only
      - "--tic"                            → append one bootstrap tic after verification
      - "--rung domain|estate|federation"  → create one explicit rung marker
user-invocable: true
---

# /init-governance

Bootstrap or repair the **project-local governance zone** for an already installed CGG plugin.

## Distribution boundary

The plugin manager owns plugin components and enabled scope:

```text
npm package or Git source
  -> Claude marketplace
  -> installed plugin
  -> loaded component inventory
```

This skill begins after that chain. It does not copy skills, agents, hooks, or scripts into `~/.claude`, and it does not edit Claude settings. Use the npm installer or Claude plugin commands for distribution.

## Invariants

1. Existing `.ticzone`, `.ticignore`, `CLAUDE.md`, `MEMORY.md`, and audit history are never overwritten.
2. Missing project surfaces may be created.
3. The Session Learning Protocol is appended once, identified by `<!-- cgg-session-learning-protocol:v5 -->`.
4. `PRESTIGE` is governance-blocked and never enters the active zone band list.
5. Plugin scope and governance jurisdiction remain separate.
6. Verification precedes any success claim.
7. A bootstrap tic is emitted only when `--tic` is explicit.
8. Rung markers are created only when `--rung` is explicit.

## Step 1 — Resolve the zone root

Resolve in this order:

1. Walk upward from `${CLAUDE_PROJECT_DIR:-$PWD}` to the nearest `.ticzone`.
2. Otherwise use `git rev-parse --show-toplevel` when available.
3. Otherwise use `${CLAUDE_PROJECT_DIR:-$PWD}`.

Report the resolved path before mutation.

## Step 2 — Verify the loaded plugin

Run:

```bash
claude plugin list --json
claude plugin details context-grapple-gun@cgg
```

Required:

- `context-grapple-gun` appears in the installed list;
- at least one skill is loaded;
- when the installed manifest is full mode, agents and hooks are non-zero.

If the plugin is absent or the inventory is empty, stop and route to [INSTALL.md](../../../INSTALL.md). Do not create a successful zone receipt around an unverified runtime.

## Step 3 — Plan non-destructive changes

Inspect:

- `.ticzone`
- `.ticignore`
- `audit-logs/`
- `CLAUDE.md`
- optional rung markers

For `--dry-run`, report every action as one of:

```text
[would create]
[exists]
[held — semantic conflict]
[blocked — policy]
```

Then stop without writing.

## Step 4 — Create missing zone files

### `.ticzone`

Create only when absent:

```json
{
  "name": "<directory-name>-zone",
  "tz": "UTC",
  "include": ["."],
  "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL"],
  "muffling_per_hop": 5,
  "signal_governance": {
    "hearing_threshold": 40,
    "decay_rate_per_tic": 2,
    "warrant_eligible_kinds": ["BEACON", "TENSION"],
    "primitive_audibility_mode": "threshold_floor",
    "zombie_guard_mode": "clamp_and_warn"
  }
}
```

If `.ticzone` exists, read and report its name, timezone, and bands. Never replace it automatically. If it contains `PRESTIGE`, report a governance conflict for human repair; do not silently rewrite an existing constitutional file.

### `.ticignore`

Create only when absent:

```text
node_modules/
dist/
target/
.git/
__pycache__/
*.pyc
vendor/
.claude/skills/
stage/
```

Do not add `MEMORY.md`; it is a live born-truth surface.

## Step 5 — Create missing audit paths

Create directories only:

```text
audit-logs/tics/
audit-logs/signals/
audit-logs/cprs/
audit-logs/conformations/
audit-logs/economy/
audit-logs/provenance/
audit-logs/reviews/
```

Never delete or truncate audit content.

## Step 6 — Append the current convention once

Read:

```text
${CLAUDE_PLUGIN_ROOT}/cgg-runtime/config/session-learning-protocol.md
```

If `CLAUDE.md` does not contain `<!-- cgg-session-learning-protocol:v5 -->`, append the file exactly. If it already contains the marker, leave it unchanged. If an older unmarked Session Learning Protocol exists, report a semantic conflict and ask before adding a second version.

## Step 7 — Optional rung marker

Only when explicit:

| Argument | Marker |
|---|---|
| `--rung domain` | `.domain-root` |
| `--rung estate` | `.estate-root` |
| `--rung federation` | `.federation-root` |

Create the marker only when absent. Never infer a rung from directory depth or organization name.

## Step 8 — Validate the zone

Verify:

- `.ticzone` parses as JSON;
- active bands exclude `PRESTIGE` for newly created zones;
- `.ticignore` exists;
- all required audit directories exist;
- `CLAUDE.md` contains the v5 protocol marker;
- `cgg-runtime/scripts/cgg-doctor.sh` succeeds when executed from the zone root;
- the loaded plugin inventory remains non-empty.

## Step 9 — Optional bootstrap tic

Only for `--tic`, append one canonical bootstrap record to the current date's tic ledger after all validation passes. Count from the latest canonical `domain_counter_after` or equivalent current counter contract; do not use raw row count when the ledger exposes an authoritative counter.

The record must identify `init-governance` as the bootstrap source and reference the verification receipt.

## Step 10 — Receipt

Write a receipt under:

```text
audit-logs/provenance/init-governance-<UTC timestamp>.json
```

Minimum shape:

```json
{
  "operation": "init-governance",
  "zone_root": "...",
  "plugin": "context-grapple-gun@cgg",
  "loaded_inventory_verified": true,
  "created": [],
  "existing": [],
  "held_conflicts": [],
  "rung_marker": null,
  "bootstrap_tic": null,
  "verified_at": "..."
}
```

Completion requires the receipt and a truthful current state. A partial bootstrap is reported as partial; it is never promoted to success by wording.
