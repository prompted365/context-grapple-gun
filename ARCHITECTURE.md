# Architecture & Design Rationale

Context Grapple Gun (CGG) is a **human-gated self-evolving agent operating system** that turns day-to-day development friction into durable improvements *without poisoning long-term memory with raw logs*.

It is best understood as three coupled systems:
1. **A token-aware session execution loop** (keeps the agent sharp and cheap)
2. **A promotion pipeline for knowledge** (keeps memory high-signal)
3. **A bidirectional projection mechanism** (lets abstract truths become concrete code again)

## 1. Core Objects (The Ephemeral vs. The Durable)

Most agent "memory" systems fail because they confuse *storage* with *knowledge*, and *recall* with *governance*. CGG prevents "global memory" from becoming a trash heap of specific incidents by enforcing a five-tier taxonomy.

### Tier 1: Local Observations (Raw Discoveries)
These are bottom-of-the-ladder artifacts:
- "This endpoint returns `null` sometimes."
- "This Rust trait bound keeps failing in this crate."
- "This UI bug only happens when feature flag X is on."

These are *true*, but they are **too contextual** to store globally.

### Tier 2: Session Knowledge (Contextual Patterns)
Within an active session, the agent accumulates temporary "working theories" about the repo structure, task constraints, and current failure modes. This is useful *now*, but dangerous to persist as-is.

### Tier 3: CogPRs (The Promotion Buffer)
A Cognitive Pull Request (CogPR) is the **unit of proposed evolution**. It is the moment where a raw observation becomes a candidate for durable memory. It strips variables (file paths, one-off IDs), extracts the invariant lesson, and proposes a target scope. This is the critical "signal hygiene" layer.

### Tier 4: Project Memory (Reusable Rules)
Lessons proven useful multiple times in one repository. They are tied to a specific stack (e.g., "In this Rust workspace, errors must implement `thiserror::Error`") but are not yet universal.

### Tier 5: Global Memory (Universal Invariants)
The slowest-changing layer. A global primitive stays true across projects, stacks, and sessions (e.g., "Defensive parsing at trust boundaries").

## 2. The 100k Token Cycle (Performance Physics)

Long agent sessions produce three predictable degradations:
1. **Instruction drift** (the agent starts contradicting earlier constraints)
2. **Recall failures** (earlier context becomes "soft")
3. **Cost blowups** (you pay more for worse behavior)

CGG treats the context window like a **resource that must be rotated**. You do not "power through" at 120k+ tokens. You **end the epoch on purpose**.

The `/grapple-cog-cycle-session` command is the **epoch boundary primitive**. It converts "session entropy" into "structured evolution candidates" by:
1. Stopping active work before degradation gets severe.
2. Bundling pending CogPR proposals.
3. Flushing the bloated session context.
4. Producing a clean handoff plan for the next session.
5. Kicking off the background evaluator.

## 3. Plan Mode Hijacking (The Governance Gate)

CGG relies heavily on repurposing existing agent UI patterns for novel architectural uses. Specifically, it hijacks "Plan Mode" (typically used for code implementation planning) to serve as a **constitutional governance gate**.

Plan mode appears at three different points in the CGG pipeline, doing three different jobs:
1. **The Handoff Writer:** At the epoch boundary, Plan Mode is hijacked to write the context-exit handoff payload.
2. **The Review Surface:** When running `/grapple`, Plan Mode is hijacked to present CogPR proposals to the human in a UI that supports native approve/reject/edit actions.
3. **The Scope Arbitrator:** It forces the human to decide if a lesson belongs at the Project or Global tier.

What the human approves are *laws*, not *tactics*. You approve new primitives, scope promotions, and behavioral constraints. You do not approve one-off code fixes. This turns the human into an **editor of the agent's constitution**, not a micromanager of its thoughts.

## 4. The Ripple Assessor (Asynchronous Evolution)

The assessor exists to keep the main session loop fast. Instead of asking the active agent to both do the work *and* deeply evaluate every improvement proposal against global invariants, CGG splits the responsibilities. The active session produces work and emits signals. The background Assessor evaluates those signals with more time, a clean context, and less noise.
