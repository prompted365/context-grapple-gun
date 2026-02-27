---
name: cadence-downbeat
description: Session epoch boundary — emits canonical tic, captures lessons, writes handoff. The downbeat of the CGG cadence.
user-invocable: true
---

# /cadence-downbeat

When the user invokes this command, execute the System Shutdown & Hygiene Sequence. All steps are sequential — do not queue them.

## Phase 1: ENG/DIRECT — Operational Writes (Steps 0–2)

All operational mutation happens here. These are the writes that MUST complete before the handoff.

### Step 0: Reconcile Native Plan State
Locate the active plan file in `~/.claude/plans/`. Evaluate its status based on the spirit of the original goal. Explicitly mark it 100% 'Completed', 'Superseded', or leave it 'Active' only if the exact thread must resume.

### Step 0.5: Emit Tic
Record the canonical downbeat timestamp.
- Read project tic count from `audit-logs/tics/*.jsonl` (count entries where `type=tic`)
- Read global tic count from `~/.claude/cgg-tic-counter.json` (create if absent, start at 0)
- Increment both counters
- Append tic record to `audit-logs/tics/YYYY-MM-DD.jsonl`:
  `{"type": "tic", "tic": "<ISO-8601 now>", "tic_zone": "<name from .ticzone>", "cadence_position": "downbeat", "scope": "project", "tic_count_project": N, "tic_count_global": M}`
- Update `~/.claude/cgg-tic-counter.json` with new count and `last_tic`
- Report: `Tic #N (project) / #M (global) at YYYY-MM-DDTHH:MM:SSZ`

### Step 1: Signal Manifold Hygiene
Execute `/siren tick`. Ensure volume has accrued, TTLs are cleared, and thresholds are checked.

### Step 1.5: Snapshot Conformation
Execute `/siren conformation` to capture the system's total state at this tic boundary.

### Step 2: Extract Lessons (CogPRs)
Did we establish a new rule or optimize a workflow? If yes, IMMEDIATELY write the `<!-- --agnostic-candidate -->` block into the nearest CLAUDE.md or MEMORY.md. Use the COGNITIVE band.

## Phase 2: PLAN MODE — The Handoff (Steps 3–4)

### Step 3: Enter Plan Mode
Use the `EnterPlanMode` tool to switch to Claude Code's native plan mode. This is mandatory and mechanical — call the tool, do not just declare the shift.

### Step 4: Write the Handoff as the Plan
Generate a NEW native plan. The plan content IS the handoff — this is the ONE AND ONLY place the handoff gets written. Claude Code auto-saves the plan to `~/.claude/plans/` when approved, and references it in the next session.

The plan must include:
- `<!-- cgg-handoff -->` block with handoff_id, project_dir, trigger_version, generated_at
- User Intent, Agent Interpretation, Interpretation Concerns
- Working State (citation-laden, file:line references)
- Session Learning & ROI with Time Saved Estimates
- Friction (Signals): any new `<!-- --signal -->` blocks for unresolved technical debt
- Next Actions (concrete, numbered)
- Conformation summary
- `<!-- cgg-evaluate -->` trigger block at the very bottom — `pending_cprs_expected` must match the exact number of CogPRs from Step 2

The user sees this plan in Claude Code's native plan UI with approve/edit/reject/clear options. When approved and context cleared, the plan persists and becomes the active state for the next session.

The session does NOT end until the human acts on the plan. The human may:
- **Approve + clear context** → plan persists, next session picks it up via `implement_plan`
- **Edit** → modify the handoff before approving
- **Continue working** → exit plan mode and keep going

The ripple-assessor runs HEADLESS on next session start (background, non-blocking via cgg-gate.sh hook). It writes proposals to `~/.claude/grapple-proposals/latest.md` — keeping its ~10k tokens OUT of the runtime context window. The completion notification is informational only ('proposals ready for /grapple when ready') — it does NOT demand immediate attention. Proposals are consumed when the user invokes `/grapple`, not before.
