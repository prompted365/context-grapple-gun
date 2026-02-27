---
name: cadence-syncopate
description: Emergency session turnaround — minimal tic + handoff in ≤5% context window. The off-beat escape hatch.
user-invocable: true
---

# /cadence-syncopate

Emergency session boundary for low-context situations. Produces a valid handoff in minimal turns. No tick, no conformation, no assessor — just tic + plan + save.

When the user invokes this command, execute the following steps in ENG/DIRECT mode. Every step is mandatory but minimal:

## Step 1: Raise Autocompact Ceiling

If `CLAUDE_ENV_FILE` is available, temporarily push the autocompact boundary higher to prevent compaction mid-syncopate:

```
echo 'export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=95' >> "$CLAUDE_ENV_FILE"
```

This buys headroom. The next session's SessionStart hook will reset it to 80%.

## Step 2: Emit Tic (lightweight)

- Read project tic count from `audit-logs/tics/*.jsonl` (count entries where `type=tic`)
- Read global tic count from `~/.claude/cgg-tic-counter.json` (create if absent, start at 0)
- Increment both counters
- Append tic record to `audit-logs/tics/YYYY-MM-DD.jsonl`:
  `{"type": "tic", "tic": "<ISO-8601 now>", "tic_zone": "<name from .ticzone>", "cadence_position": "syncopate", "scope": "project", "tic_count_project": N, "tic_count_global": M}`
- Update `~/.claude/cgg-tic-counter.json` with new count and `last_tic`
- Report: `Tic #N (project) / #M (global) at YYYY-MM-DDTHH:MM:SSZ [syncopate]`

Note: `cadence_position` is `"syncopate"`, not `"downbeat"`. This distinguishes emergency exits from planned epoch boundaries.

## Step 3: Write Minimal Handoff Plan

Generate a handoff plan with ONLY these sections (keep each section to 5 lines max):

```markdown
# [YYYY-MM-DDTHH:MM] syncopate-<topic>

<!-- cgg-handoff
  handoff_id: "YYYY-MM-DDTHH:MM:SSZ-syncopate-<topic>"
  project_dir: "/absolute/path/to/project"
  trigger_version: 1
  generated_at: "ISO-8601 timestamp"
-->

## Status: Active

## Working State (compact)
<What was being worked on — files touched, decisions made, blockers hit. Max 5 lines.>

## Next Actions
<Concrete next steps. Max 5 items.>

## Carried Signals
<List active signal IDs + volumes from memory. If unknown, write "See /siren status".>
```

Do NOT include: User Intent, Agent Interpretation, Interpretation Concerns, Lessons, Friction, Verification, or cgg-evaluate trigger blocks. Those are downbeat luxuries.

## Step 4: Save Handoff to Disk

- Compute `PROJECT_KEY` by replacing `/` with `-` in the project directory path
- Generate filename from the `handoff_id` (replace colons with dashes, spaces with dashes)
- Write the plan content to: `~/.claude/projects/$PROJECT_KEY/<filename>.md`
- The file MUST contain the `<!-- cgg-handoff -->` block (no `cgg-evaluate` — no CPRs to process)

## Step 5: Update MEMORY.md Active Session State

Overwrite the `## Active Session State` section in MEMORY.md with:
- Branch name
- List of modified files (from `git status`)
- Pointer to the handoff plan file
- Current tic number

This is the crash-recovery breadcrumb. If the handoff plan is lost, MEMORY.md still has the trail.

## What Syncopate Skips (and why)

| Skipped | Why | Recovery path |
|---------|-----|---------------|
| Signal tick (`/siren tick`) | Too expensive at 5% | Next downbeat or manual `/siren tick` |
| Conformation snapshot | Depends on tick | Next downbeat |
| CPR extraction (Step 2 of downbeat) | Requires reading full context | Lessons stay inline, picked up next `/grapple` |
| Ripple assessor (Step 6 of downbeat) | Subagent too expensive | Next downbeat fires it |
| Plan Mode transition | UI overhead | Direct write instead |

The syncopate is a valid handoff — the next session gets Next Actions via session-restore.sh and can run a full downbeat when context is fresh.
