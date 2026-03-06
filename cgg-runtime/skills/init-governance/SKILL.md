---
name: init-governance
description: Bootstrap or repair CGG governance surfaces in a project. Creates .ticzone, audit directories, installs runtime (skills, agents, hooks), validates sync.
user-invocable: true
---

# /init-governance

Single bootstrap command for CGG governance surface creation, repair, and sync validation.

## Modes

- **`/init-governance`** (no args) — fresh install or repair. Creates missing surfaces, syncs drifted ones.
- **`/init-governance --dry-run`** — report what would be created/synced without modifying anything.
- **`/init-governance --tic`** — after install, emit an initial tic.

## Execution Steps

### Step 1: Resolve Roots

Determine two anchors:
- **Zone root**: walk up from cwd to find `.ticzone`, fall back to git root, fall back to cwd
- **CGG plugin root**: the CGG submodule directory (typically `vendor/context-grapple-gun/`)

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
```

If CGG plugin root is not found, report error and exit.

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
```

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

Copy from CGG plugin root canonical sources to installed locations.

**Skills** (source: `$CGG_PLUGIN_ROOT/cgg-runtime/skills/` -> target: `$ZONE_ROOT/.claude/skills/`):
- `cadence/SKILL.md`
- `review/SKILL.md`
- `siren/SKILL.md`
- `init-governance/SKILL.md`

**Agents** (source: `$CGG_PLUGIN_ROOT/cgg-runtime/agents/` -> target: `$ZONE_ROOT/.claude/agents/`):
- `mogul.md`
- `ripple-assessor.md`
- `pattern-curator.md`
- `ladder-auditor.md`

**Hooks** (source: `$CGG_PLUGIN_ROOT/cgg-runtime/hooks/` -> target as configured by user):
- `session-restore-patch.sh`
- `cgg-gate.sh`

For each surface:
1. Check if installed copy exists
2. If missing: copy from canonical, report `[installed]`
3. If exists: compare content hash with canonical
   - If identical: report `[synced]`
   - If different: report `[DRIFTED]` and show brief diff summary. Copy canonical to installed, report `[resynced]`

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
Mode:       fresh install | repair/resync | dry-run

Surfaces:
  .ticzone          [created|exists]
  .ticignore        [created|exists]
  audit-logs/       [created|exists] (6 subdirs)

Runtime:
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

Drift:      0 surfaces drifted (or N surfaces resynced)
Initial tic: emitted | skipped (use --tic)
```

## Nested Surface Support

For estate root installs: install to `$ZONE_ROOT/.claude/`.
For nested site/domain surfaces: the user may specify `--target <subdir>` to install governance surfaces into a subdirectory's `.claude/` instead. The `.ticzone` at zone root still governs the acoustic space.

## Runtime Truth Invariant

This skill copies canonical to installed. After sync, installed IS runtime truth.
Canonical source is intent until this skill completes sync + verify.
