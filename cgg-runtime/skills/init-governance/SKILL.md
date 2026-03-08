---
name: init-governance
description: Bootstrap or repair CGG governance surfaces in a project. Creates .ticzone, audit directories, installs runtime (skills, agents, hooks), validates sync.
user-invocable: true
---

# /init-governance

Single bootstrap command for CGG governance surface creation, repair, and sync validation.

## Modes

- **`/init-governance`** (no args) — fresh install or repair. Creates missing surfaces, syncs drifted ones. Default scope: **user/global**.
- **`/init-governance --scope user`** — install runtime surfaces to `~/.claude/` (default).
- **`/init-governance --scope project`** — install runtime surfaces to `$ZONE_ROOT/.claude/` (project-local).
- **`/init-governance --dry-run`** — report what would be created/synced without modifying anything.
- **`/init-governance --tic`** — after install, emit an initial tic.
- **`/init-governance --rung domain|estate|federation`** — after install, create the specified rung marker at zone root.

## Install Scope Policy

**Default install scope is user/global (`~/.claude`).** Use project scope only when explicitly requested.

```
Install scope selection:

- Default: user/global (~/.claude/...)
- Override: project ($ZONE_ROOT/.claude/...) only if --scope project is passed
- Enterprise: not a normal install target; detect managed policy and respect it

If no explicit scope is provided, install to user/global scope.
```

**Why user/global is the default**: CGG governance validation is cross-project by design. Installing to user/global ensures runtime surfaces are available across all projects without per-project reinstallation. Project scope creates a local embodiment — appropriate only when the user explicitly wants project-isolated governance.

**Scope determines where runtime surfaces land:**

| Surface | user/global | project |
|---------|-------------|---------|
| Skills | `~/.claude/skills/` | `$ZONE_ROOT/.claude/skills/` |
| Agents | `~/.claude/agents/` | `$ZONE_ROOT/.claude/agents/` |
| Hooks config | `~/.claude/settings.json` | `$ZONE_ROOT/.claude/settings.local.json` |
| `.ticzone` | Always `$ZONE_ROOT/` | Always `$ZONE_ROOT/` |
| `.ticignore` | Always `$ZONE_ROOT/` | Always `$ZONE_ROOT/` |
| `audit-logs/` | Always `$ZONE_ROOT/` | Always `$ZONE_ROOT/` |
| Convention block | Always `$ZONE_ROOT/CLAUDE.md` | Always `$ZONE_ROOT/CLAUDE.md` |

Zone configuration, audit data, and convention blocks are always project-local regardless of scope — they are per-zone artifacts by nature.

**Enterprise managed policy**: Enterprise is a managed policy layer with highest precedence. It is administered by IT/DevOps and cannot be overridden by user or project settings. If enterprise managed policy is detected:
- Report what policy constraints exist
- Do not attempt to install around or override enterprise settings
- Continue with non-conflicting surfaces only
- Never offer enterprise as an install destination

### Scope invariant

Install scope controls **runtime surface placement only**.

It does **not** change the location of the project's governance zone surfaces.

Always keep these at the zone root:
- `.ticzone`
- `.ticignore`
- `audit-logs/`
- project governance files (`CLAUDE.md`, `MEMORY.md`)

So:

- `--scope user` installs runtime surfaces to `~/.claude/...`
- `--scope project` installs runtime surfaces to `$ZONE_ROOT/.claude/...`

But both scopes still use the same project zone root for governance scanning, tic emission, and audit history.

Runtime scope and governance scope are different things.
Default runtime scope is user/global.
Default governance scope remains project-local unless promoted through the ladder.

## Ownership Model

This skill owns **installed runtime copies** only. Install root is scope-dependent:
- **user scope**: `$INSTALL_ROOT = ~/.claude`
- **project scope**: `$INSTALL_ROOT = $ZONE_ROOT/.claude`

It may freely create or overwrite:
- `$INSTALL_ROOT/skills/{cadence,review,siren,init-governance}/SKILL.md`
- `$INSTALL_ROOT/agents/{mogul,ripple-assessor,pattern-curator,ladder-auditor}.md`
- `$INSTALL_ROOT/hooks/{session-restore-patch,cgg-gate,posttool-microscan}.sh`
- `$ZONE_ROOT/.ticzone` (only if it does not already exist)
- `$ZONE_ROOT/.ticignore` (only if it does not already exist)
- `$ZONE_ROOT/audit-logs/` subdirectories (create only, never delete)

This skill may **append** to (never overwrite):
- `$ZONE_ROOT/CLAUDE.md` — convention block only (appended if Session Learning Protocol section is absent)
- Hook registrations — merged into `~/.claude/settings.json` (user scope) or `$ZONE_ROOT/.claude/settings.local.json` (project scope), never replacing existing entries

This skill must NEVER overwrite:
- User-authored `CLAUDE.md` or `MEMORY.md` content at any rung
- Existing `.ticzone` (report it, do not replace — user may have customized it)
- Existing `audit-logs/*.jsonl` files (append-only history)
- Any file outside both the zone root and `~/.claude/`
- Enterprise managed policy settings

**Overwrite refusal rule**: If an installed surface has been locally modified (content hash differs from both canonical AND the last known synced hash), report the conflict and ask the user whether to overwrite or keep the local version. Do not silently overwrite user customizations.

## Dry-Run Reporting Format

In `--dry-run` mode, report each action that WOULD be taken:
```
[would create]  .ticzone (from template)
[would create]  audit-logs/tics/
[would install] .claude/skills/cadence/SKILL.md
[would resync]  .claude/agents/mogul.md (canonical != installed)
[exists]        .claude/skills/review/SKILL.md (in sync)
[CONFLICT]      .claude/agents/ripple-assessor.md (locally modified)
```

Exit without modifying anything. Exit code 0.

## Execution Steps

### Step 1: Resolve Roots and Install Scope

Determine three anchors:
- **Zone root**: walk up from cwd to find `.ticzone`, fall back to git root, fall back to cwd
- **CGG plugin root**: the CGG submodule directory (typically `vendor/context-grapple-gun/`)
- **Install root**: scope-dependent target for runtime surfaces

```bash
# Zone root
ZONE_ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
while [ "$ZONE_ROOT" != "/" ] && [ ! -f "$ZONE_ROOT/.ticzone" ]; do ZONE_ROOT=$(dirname "$ZONE_ROOT"); done

# Plugin root — search common locations
for candidate in \
  "$ZONE_ROOT/vendor/context-grapple-gun" \
  "$ZONE_ROOT/.claude/cgg" \
  "$HOME/.claude/cgg"; do
  [ -d "$candidate/cgg-runtime" ] && CGG_PLUGIN_ROOT="$candidate" && break
done

# Install scope (default: user/global)
SCOPE="${SCOPE:-user}"  # from --scope flag
if [ "$SCOPE" = "user" ]; then
  INSTALL_ROOT="$HOME/.claude"
  SETTINGS_FILE="$HOME/.claude/settings.json"
else
  INSTALL_ROOT="$ZONE_ROOT/.claude"
  SETTINGS_FILE="$ZONE_ROOT/.claude/settings.local.json"
fi
```

If CGG plugin root is not found, report error and exit.

**Enterprise policy detection**: Before proceeding, check for enterprise managed policy:
```bash
# Enterprise managed policy is at ~/.claude/settings.enterprise.json or
# deployed via MDM. If present, it has highest precedence.
ENTERPRISE_POLICY=""
for ep in "$HOME/.claude/settings.enterprise.json" "/etc/claude/settings.json"; do
  [ -f "$ep" ] && ENTERPRISE_POLICY="$ep" && break
done
```

If enterprise managed policy is detected:
1. Report: `[ENTERPRISE] Managed policy detected at <path>`
2. Parse the policy for any `hooks`, `allowedTools`, or `disabledTools` constraints
3. Report which constraints are in force
4. Continue with non-conflicting surfaces only — do not attempt to override
5. If enterprise policy blocks hook registration, report: `[ENTERPRISE BLOCK] Hook registration blocked by managed policy — hooks must be registered by your administrator`

### Step 2: Zone Configuration

Check for existing `.ticzone` at zone root.

**If missing**: create from template:
```json
{
  "name": "<directory-name>-zone",
  "tz": "America/Chicago",
  "bands": ["PRIMITIVE", "COGNITIVE", "SOCIAL", "PRESTIGE"],
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

Prompt the user for `name` and `tz` if interactive. Use defaults if headless.

**If exists**: report "Zone config found: <name>" and continue.

Check for `.ticignore`. Create default if missing:
```
node_modules/
.git/
__pycache__/
*.pyc
vendor/*/node_modules/

# Stage artifacts — ticignored (no tics/signals/warrants) but learning-eligible.
# Arena templates are readable reference material for pattern mining and retrieval.
stage/
```

### Step 2.5: Rung Marker (optional)

If `--rung domain|estate|federation` was **explicitly passed**, create the appropriate marker at zone root.

Rung markers are independent of governance zones. A marker can exist without `.ticzone` and vice versa. This step never runs implicitly — site bootstrap is the unchanged default.

| Flag | Marker created |
|------|---------------|
| `--rung domain` | `.domain-root` |
| `--rung estate` | `.estate-root` |
| `--rung federation` | `.federation-root` |

**If marker already exists**: report `[exists] .domain-root` and continue.

**If created**: report `[created] .domain-root (topology: domain)`.

**Never create rung markers implicitly.** Rung declaration is strictly opt-in.

### Step 3: Create Audit Directory Tree

Create the following directories under zone root if they don't exist:
```
audit-logs/
  tics/
  signals/
  cprs/
  conformations/
  economy/
  provenance/
```

Report each: `[created]` or `[exists]`.

### Step 4: Install Runtime Surfaces

Copy from CGG plugin root canonical sources to `$INSTALL_ROOT` (scope-dependent).

**Skills** (source: `$CGG_PLUGIN_ROOT/cgg-runtime/skills/` -> target: `$INSTALL_ROOT/skills/`):
- `cadence/SKILL.md`
- `review/SKILL.md`
- `siren/SKILL.md`
- `init-governance/SKILL.md`

**Agents** (source: `$CGG_PLUGIN_ROOT/cgg-runtime/agents/` -> target: `$INSTALL_ROOT/agents/`):
- `mogul.md`
- `ripple-assessor.md`
- `pattern-curator.md`
- `ladder-auditor.md`

**Hooks** (source: `$CGG_PLUGIN_ROOT/cgg-runtime/hooks/` -> target: `$INSTALL_ROOT/hooks/`):
- `session-restore-patch.sh`
- `cgg-gate.sh`

For each surface:
1. If enterprise policy blocks the surface category, report `[ENTERPRISE BLOCK]` and skip
2. Check if installed copy exists at `$INSTALL_ROOT`
3. If missing: copy from canonical, report `[installed]` with scope annotation
4. If exists: compare content hash with canonical
   - If identical: report `[synced]`
   - If different: report `[DRIFTED]` and show brief diff summary. Copy canonical to installed, report `[resynced]`

### Step 4.5: Convention Block (CLAUDE.md)

Check if the project's `CLAUDE.md` contains the CGG Session Learning Protocol block.

**Detection**: Search for `## Session Learning Protocol` in `$ZONE_ROOT/CLAUDE.md`.

**If missing**: Read the canonical convention block from `$CGG_PLUGIN_ROOT/convention-block.md`. Append it to the end of `$ZONE_ROOT/CLAUDE.md` (create the file if it doesn't exist). Report `[installed] convention block in CLAUDE.md`.

**If present**: Report `[exists] convention block in CLAUDE.md` and do not modify.

**Safety**: This step appends only. It never overwrites existing CLAUDE.md content. If the block exists but differs from canonical, report `[drifted] convention block — manual review recommended` but do not overwrite.

### Step 4.6: Settings Registration

Register hooks in the scope-appropriate settings file:
- **user scope**: `~/.claude/settings.json`
- **project scope**: `$ZONE_ROOT/.claude/settings.local.json`

**Pre-check**: If enterprise managed policy is detected and constrains hook registration, report the constraint and skip this step entirely.

**Detection**: Read `$SETTINGS_FILE` (or create it if missing). Check whether `hooks` entries exist for:
- `SessionStart` → hook path to session-restore-patch.sh
- `UserPromptSubmit` → hook path to cgg-gate.sh

Hook command paths are scope-dependent:
- **user scope**: absolute paths (`~/.claude/hooks/session-restore-patch.sh`)
- **project scope**: relative paths (`.claude/hooks/session-restore-patch.sh`)

**If missing entries**: Add the missing hook registrations to the `hooks` object. Preserve all existing settings — merge, do not replace.

**Expected format for user scope** (merged into `~/.claude/settings.json`):
```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "~/.claude/hooks/session-restore-patch.sh"
      }
    ],
    "UserPromptSubmit": [
      {
        "type": "command",
        "command": "~/.claude/hooks/cgg-gate.sh"
      }
    ]
  }
}
```

**Expected format for project scope** (merged into `$ZONE_ROOT/.claude/settings.local.json`):
```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": ".claude/hooks/session-restore-patch.sh"
      }
    ],
    "UserPromptSubmit": [
      {
        "type": "command",
        "command": ".claude/hooks/cgg-gate.sh"
      }
    ]
  }
}
```

**If already registered**: Report `[exists] hooks in $SETTINGS_FILE` and do not modify.

**Safety**: This step merges into existing JSON. It never deletes existing settings entries. It never touches enterprise managed policy files.

### Step 5: Validate

After install/sync:
1. Run content hash comparison on all installed vs canonical surfaces
2. Report final status for each surface: `synced` / `drifted` / `missing_canonical` / `missing_installed`
3. If any drift remains after sync: emit a TENSION signal to `audit-logs/signals/YYYY-MM-DD.jsonl`

### Step 6: Initial Tic (optional, `--tic` flag only)

If `--tic` was specified:
1. Count existing tics physically from `audit-logs/tics/*.jsonl`
2. Append initial tic record:
   ```json
   {"type": "tic", "tic": "<ISO-8601 now>", "tic_zone": "<name>", "cadence_position": "downbeat", "domain_counter": 1, "global_counter": 1}
   ```
3. Report: `Initial tic #1 emitted`

### Step 7: Report

Output a summary:

```
/init-governance complete

Zone:       <name> at <zone_root>
Scope:      user/global (~/.claude) | project ($ZONE_ROOT/.claude)
Mode:       fresh install | repair/resync | dry-run
Enterprise: not detected | detected at <path> (N constraints in force)

Surfaces (zone-local):
  .ticzone          [created|exists]
  .ticignore        [created|exists]
  audit-logs/       [created|exists] (6 subdirs)

Runtime (at $INSTALL_ROOT):
  skills/cadence    [installed|synced|resynced]
  skills/review     [installed|synced|resynced]
  skills/siren      [installed|synced|resynced]
  skills/init-gov   [installed|synced|resynced]
  agents/mogul      [installed|synced|resynced]
  agents/ripple     [installed|synced|resynced]
  agents/pattern    [installed|synced|resynced]
  agents/ladder     [installed|synced|resynced]
  hooks/restore     [installed|synced|resynced]
  hooks/gate        [installed|synced|resynced]

Convention: [installed|exists|drifted] (at $ZONE_ROOT/CLAUDE.md)
Settings:   [installed|exists] (hooks in $SETTINGS_FILE)
Drift:      0 surfaces drifted (or N surfaces resynced)
Initial tic: emitted | skipped (use --tic)
Rung:       site (default) | domain | estate | federation
Topology:   site only | domain > site | estate > domain > site | ...
```

## Nested Surface Support

Scope selection (`--scope`) determines the install root for runtime surfaces.
For nested site/domain surfaces: the user may specify `--target <subdir>` to install governance surfaces into a subdirectory's `.claude/` instead. The `.ticzone` at zone root still governs the acoustic space.

`--target` overrides `--scope` for runtime surface placement only. Zone-local surfaces (`.ticzone`, `audit-logs/`, convention block) always resolve from the zone root.

## Runtime Truth Invariant

This skill copies canonical to installed. After sync, installed IS runtime truth.
Canonical source is intent until this skill completes sync + verify.

### Federation install note

In canonical federation workflows, the default install policy is `--scope user`.

Reason:
- `canonical/` is doctrine, not runtime
- `canonical_user/` is validation, not runtime host
- user/global scope is the preferred embodiment for federation-level validation

Project scope is allowed only as an explicit override.
