---
name: statusline
description: Configure the CGG acoustic statusline — a read-only conformation radar with soft-toggle modes (OFF/LITE/FULL).
user-invocable: true
---

# /statusline — CGG Acoustic Statusline

A live conformation radar for the current estate. Pure observability surface.

It shows:
- where you are (project, branch)
- how full the session is (cost, duration)
- what the estate's last known conformation looks like (from canonical snapshots)

It does NOT:
- decide or infer canon from raw ledgers
- mutate governance state (no signal emission, no audit entries, no mandates)
- run cadence machinery or participate in the promotion pipeline
- scan raw JSONL event stores for truth reconstruction

**Architecture invariant:** Statusline reads summaries. Governance produces summaries. Statusline never becomes governance.

## Modes

| Mode | Output | Performance |
|------|--------|-------------|
| OFF  | Nothing | Zero cost |
| LITE | `[Opus] operationTorque (main) \| tic 208` | ~5ms (cached) |
| FULL | Line 1: same as LITE | ~10ms cached |
|      | Line 2: `conformation: clean \| sig 0 \| wrn 0 \| cpr 2 \| $0.47 \| 12m` | |

## Fallback Ladder

The statusline degrades gracefully based on what canonical surfaces exist:

1. **Conformation snapshot exists** — show full conformation counts (sig/wrn/cpr) + status
2. **Only tic counter exists** — show tic count, skip conformation fields
3. **Neither exists** — show model + project + branch only

The statusline never compensates for missing summaries by scanning raw ledgers.

## Sub-commands

### `/statusline install`

Install into the current project's `.claude/settings.local.json` (project-scoped).

**Steps:**
1. Read `.claude/settings.local.json` (create if absent)
2. Set the `statusLine` key:
   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "bash \"$CLAUDE_PROJECT_DIR\"/vendor/context-grapple-gun/cgg-runtime/scripts/cgg-statusline.sh"
     }
   }
   ```
3. If `~/.claude/settings.json` has a `statusLine` key, warn:
   "Global statusLine in ~/.claude/settings.json will be overridden by project-local setting."
4. Confirm installation.

**Do NOT modify `~/.claude/settings.json` unless `--global` is explicitly passed.**

### `/statusline install --global`

Install to `~/.claude/settings.json` instead of project-local. Warn that this affects all projects.

### `/statusline uninstall`

Remove the `statusLine` key from `.claude/settings.local.json`. If `--global`, remove from `~/.claude/settings.json`.

### `/statusline mode <OFF|LITE|FULL>`

Toggle the display mode:
1. Compute the project hash: first 8 chars of `md5(workspace.project_dir)`
2. Write the mode string to `/tmp/cgg-sl-<hash>-mode`
3. Confirm: "Status line mode set to FULL. Takes effect on next refresh."

Default mode (no flag file) is LITE.

### `/statusline clear`

Delete all cache files for the current project:
- `/tmp/cgg-sl-<hash>-{mode,git,tic,conf}`

### `/statusline` (no args)

Show current configuration:
1. Check if statusLine is configured in `.claude/settings.local.json` or `~/.claude/settings.json`
2. Show current mode (read flag file or "LITE (default)")
3. Show cache file locations and ages

## Data Sources

### Allowed (observability layer)

| Metric | Source | Method |
|--------|--------|--------|
| Model name | Claude Code stdin JSON | Direct read |
| Cost | `cost.total_cost_usd` from stdin JSON | Direct read |
| Duration | `cost.total_duration_ms` from stdin JSON | ms to formatted |
| Tic count | `~/.claude/cgg-tic-counter.json` | Scalar read from canonical counter |
| Conformation counts | `audit-logs/conformations/tic-N.json` | Read `.counts` from latest snapshot |
| Git branch/dirty | `git symbolic-ref` / `git diff --quiet` | Cached 5s |

### Disallowed (governance runtime — never touch)

| Source | Why |
|--------|-----|
| `audit-logs/signals/*.jsonl` | Raw event ledger. Truth reconstruction is governance work. |
| `audit-logs/cprs/queue.jsonl` | Raw queue ledger. Latest-per-ID resolution is governance work. |
| Inline `<!-- -->` blocks | Not authoritative. Scanning them conflates observation with inference. |
| `audit-logs/tics/*.jsonl` | Raw tic ledger. Use the canonical counter scalar instead. |

## Cache Strategy

All caches are namespaced per project via hash of `workspace.project_dir`:

| Cache | TTL | Key |
|-------|-----|-----|
| Git branch + dirty | 5s | `/tmp/cgg-sl-<hash>-git` |
| Tic count | 30s | `/tmp/cgg-sl-<hash>-tic` |
| Conformation summary | 30s | `/tmp/cgg-sl-<hash>-conf` |

## Script Location

Canonical: `vendor/context-grapple-gun/cgg-runtime/scripts/cgg-statusline.sh`

Referenced in-place from the submodule — not copied to `.claude/`. This avoids drift between canonical and installed copies.

## Separation of Concerns

| Layer | Responsibility | Statusline's role |
|-------|---------------|-------------------|
| **Observability** | Display conformation state | This layer. Read-only radar. |
| **Governance runtime** | Produce conformations, advance signals, mint warrants | Not this layer. Never. |
| **Review / promotion** | Adjudicate CogPRs, promote lessons to law | Not this layer. Never. |

## Safety

- No writes to `audit-logs/`, no signal emission, no state mutation
- No cadence participation, no mandate creation
- Cache writes go to `/tmp/` only (ephemeral, OS-managed)
- Mode toggle is per-project namespaced — one project cannot toggle another
- If canonical summary surfaces are missing, degrades to smaller display — never compensates
