---
name: grapple-cog-cycle-session
description: Expands the standard System Shutdown & Hygiene Sequence for CGG v3.
user-invocable: true
---

# /grapple-cog-cycle-session

When the user invokes this command, output the following exact text to initiate the session handoff protocol:

"We are wrapping up this session. Initiate the System Shutdown & Hygiene Sequence. Execute the following steps sequentially in ENG/DIRECT mode, and do not queue them:

0. Reconcile Native Plan State: Locate the active plan file in ~/.claude/plans/. Evaluate its status based on the spirit of the original goal. Explicitly mark it 100% 'Completed', 'Superseded', or leave it 'Active' only if the exact thread must resume.

1. Signal Manifold Hygiene: Execute `/siren tick`. Ensure volume has accrued, TTLs are cleared, and thresholds are checked.

2. Extract Lessons (CogPRs): Did we establish a new rule or optimize a workflow? If yes, IMMEDIATELY write the `<!-- --agnostic-candidate -->` block into the nearest CLAUDE.md or MEMORY.md. Use the COGNITIVE band.

3. SHIFT POSTURE TO NATIVE PLAN MODE: You must now explicitly exit ENG mode and transition to your native PLAN mode.

4. Generate the Handoff Plan: Using your native planning capability, generate a NEW plan for the next session. This ensures Claude Code registers it as the active state.

5. Populate the Native Plan: Inside this new plan, you must include:
   - Session Learning & ROI: List the specific lessons captured today and provide a Time Saved Estimate (e.g., 'Saves 45 mins of future debugging').
   - Friction (Signals): Drop any new `<!-- --signal -->` blocks directly into the 'Working State' section for unresolved technical debt.
   - Wire the Trigger: At the very bottom, compile the exact `<!-- cgg-evaluate -->` HTML trigger block. Ensure pending_cprs_expected matches the exact number of CogPRs you created in Step 2."
