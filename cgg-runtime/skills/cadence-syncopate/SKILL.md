---
name: cadence-syncopate
description: Emergency session turnaround — minimal tic + handoff in ≤5% context window. The off-beat escape hatch.
user-invocable: true
---

# /cadence-syncopate

Emergency session boundary for low-context situations. Produces a valid handoff in minimal turns. No tick, no conformation, no assessor — just tic + plan.

When the user invokes this command, execute the following steps. Every step is mandatory but minimal.

## Phase 1: ENG/DIRECT — Operational Writes (Steps 1–3)

All operational mutation happens here. These are the writes that MUST complete before the handoff.

### Step 1: Raise Autocompact Ceiling

If `CLAUDE_ENV_FILE` is available, temporarily push the autocompact boundary higher to prevent compaction mid-syncopate:

```
echo 'export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=95' >> "$CLAUDE_ENV_FILE"
```

This buys headroom. The next session's SessionStart hook will reset it to 80%.

### Step 2: Emit Tic (lightweight)

- Read project tic count from `audit-logs/tics/*.jsonl` (count entries where `type=tic`)
- Read global tic count from `~/.claude/cgg-tic-counter.json` (create if absent, start at 0)
- Increment both counters
- Append tic record to `audit-logs/tics/YYYY-MM-DD.jsonl`:
  `{"type": "tic", "tic": "<ISO-8601 now>", "tic_zone": "<name from .ticzone>", "cadence_position": "syncopate", "scope": "project", "tic_count_project": N, "tic_count_global": M}`
- Update `~/.claude/cgg-tic-counter.json` with new count and `last_tic`
- Report: `Tic #N (project) / #M (global) at YYYY-MM-DDTHH:MM:SSZ [syncopate]`

Note: `cadence_position` is `"syncopate"`, not `"downbeat"`. This distinguishes emergency exits from planned epoch boundaries.

### Step 3: Update MEMORY.md Active Session State

Overwrite the `## Active Session State` section in MEMORY.md with:
- Branch name
- List of modified files (from `git status`)
- Current tic number

This is the crash-recovery breadcrumb. If the plan is lost, MEMORY.md still has the trail.

## Phase 2: PLAN MODE — The Handoff (Steps 4–5)

### Step 4: Enter Plan Mode

Use the `EnterPlanMode` tool to switch to Claude Code's native plan mode. This is mandatory and mechanical — call the tool, do not just declare the shift.

### Step 5: Write the Handoff as the Plan

Generate a NEW native plan. The plan content IS the handoff — this is the ONE AND ONLY place the handoff gets written. Claude Code auto-saves the plan to `~/.claude/plans/` when approved, and references it in the next session.

Keep it COMPACT (each section 5 lines max):

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

The user sees this plan in Claude Code's native plan UI with approve/edit/reject/clear options. When approved and context cleared, the plan persists and becomes the active state for the next session.

The session does NOT end until the human acts on the plan. The human may:
- **Approve + clear context** → plan persists, next session picks it up via `implement_plan`
- **Edit** → modify the handoff before approving
- **Continue working** → exit plan mode and keep going

This is the constitutional gate — no context clear without human sign-off via the native plan UI.

## What Syncopate Skips (and why)

| Skipped | Why | Recovery path |
|---------|-----|---------------|
| Signal tick (`/siren tick`) | Too expensive at 5% | Next downbeat or manual `/siren tick` |
| Conformation snapshot | Depends on tick | Next downbeat |
| CPR extraction (Step 2 of downbeat) | Requires reading full context | Lessons stay inline, picked up next `/grapple` |
| Ripple assessor | Runs headless on next session start | cgg-gate.sh triggers it |

The syncopate is a valid handoff — the next session gets Next Actions via the plan and can run a full downbeat when context is fresh.
