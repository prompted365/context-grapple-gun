---
name: cadence-downbeat
description: Session epoch boundary — emits canonical tic, captures lessons, writes handoff. The downbeat of the CGG cadence.
user-invocable: true
---

# /cadence-downbeat

When the user invokes this command, output the following exact text to initiate the session handoff protocol:

"We are wrapping up this session. Initiate the System Shutdown & Hygiene Sequence. Execute the following steps sequentially in ENG/DIRECT mode, and do not queue them:

0. Reconcile Native Plan State: Locate the active plan file in ~/.claude/plans/. Evaluate its status based on the spirit of the original goal. Explicitly mark it 100% 'Completed', 'Superseded', or leave it 'Active' only if the exact thread must resume.

0.5. Emit Tic: Record the canonical downbeat timestamp.
   - Read project tic count from audit-logs/tics/*.jsonl (count entries where type=tic)
   - Read global tic count from ~/.claude/cgg-tic-counter.json (create if absent, start at 0)
   - Increment both counters
   - Append tic record to audit-logs/tics/YYYY-MM-DD.jsonl:
     {"type": "tic", "tic": "<ISO-8601 now>", "tic_zone": "<name from .ticzone>", "cadence_position": "downbeat", "scope": "project", "tic_count_project": N, "tic_count_global": M}
   - Update ~/.claude/cgg-tic-counter.json with new count and last_tic
   - Report: 'Tic #N (project) / #M (global) at YYYY-MM-DDTHH:MM:SSZ'

1. Signal Manifold Hygiene: Execute `/siren tick`. Ensure volume has accrued, TTLs are cleared, and thresholds are checked.

1.5. Snapshot Conformation: Execute `/siren conformation` to capture the system's total state at this tic boundary. This snapshot enables future diffing between epochs.

2. Extract Lessons (CogPRs): Did we establish a new rule or optimize a workflow? If yes, IMMEDIATELY write the `<!-- --agnostic-candidate -->` block into the nearest CLAUDE.md or MEMORY.md. Use the COGNITIVE band.

3. SHIFT POSTURE TO NATIVE PLAN MODE: You must now explicitly exit ENG mode and transition to your native PLAN mode.

4. Generate the Handoff Plan: Using your native planning capability, generate a NEW plan for the next session. This ensures Claude Code registers it as the active state.

4.5. Save Handoff to Disk: After generating the plan, save it as a standalone markdown file so the trigger pipeline can discover it on next session start.
   - Compute PROJECT_KEY by replacing '/' with '-' in the project directory path
   - Generate a filename from the handoff_id (replace colons with dashes, spaces with dashes)
   - Write the plan content to: ~/.claude/projects/$PROJECT_KEY/<filename>.md
   - The file MUST contain the `<!-- cgg-handoff -->` and `<!-- cgg-evaluate -->` blocks from the plan
   - This enables session-restore.sh to discover the plan, extract triggers, and spawn the ripple-assessor automatically
   - Without this file, the trigger pipeline is dead — the ripple-assessor never fires

5. Populate the Native Plan: Inside this new plan, you must include:
   - Session Learning & ROI: List the specific lessons captured today and provide a Time Saved Estimate (e.g., 'Saves 45 mins of future debugging').
   - Friction (Signals): Drop any new `<!-- --signal -->` blocks directly into the 'Working State' section for unresolved technical debt.
   - Wire the Trigger: At the very bottom, compile the exact `<!-- cgg-evaluate -->` HTML trigger block. Ensure pending_cprs_expected matches the exact number of CogPRs you created in Step 2."
