---
name: complement
description: Post-landing closure inference — direction-agnostic, scope-aware detection of materially missing expressions around an active move.
user-invocable: true
---

# /complement

Post-landing closure inference. Detects whether an active move is partial, identifies the missing complementary expression, and surfaces it only when it materially improves closure.

This is a local coherence operation, not a follow-up helper or pattern mining lite.

## Definitions

These three terms must stay distinct. Conflating them degrades the skill into adjacent thought generation.

- **Centroid**: the governing concern that organizes the active move
- **Ray**: the current directional expression of that concern (the work just done)
- **Complement**: an additional directional expression that would materially improve closure

"Complement" is direction-agnostic. It is not always an opposite. It may be:
- inverse
- adjacent missing expression
- upstream prerequisite
- downstream proof obligation
- governance counterpart
- scope correction
- time-horizon complement
- actor-lane complement
- substrate complement

"Complement" is also scope-agnostic. The same pattern can appear at sentence level, artifact level, workflow level, governance level, system architecture level, or federation level. Scope agnostic does not mean scope blind — the skill must detect the right scope of the complement.

## Trigger Condition

Invoke `/complement` after a **local closure event that may still hide non-local incompleteness**.

Not after every trivial step. The operative condition is: something landed, and there is a reasonable chance the closure is partial in a way that matters.

## Six-Step Runtime

```
1. DETECT the active target (explicit + implicit)
2. INFER the centroid (the governing concern organizing this move)
3. IDENTIFY the active ray (what aspect is currently in focus)
4. LOCATE the missing complement or unnamed tension
4.5 TEST structural relevance — is the complement structural or decorative?
5. DECIDE: surface (A), defer (B), or suppress (C)
```

### Step 4.5: Structural Relevance Test

A complement is structural if it changes at least one of:
- **Implementation path** — different code, different wiring
- **Governance posture** — different authority, different registration
- **Verification / proof burden** — different test, different validation gate
- **Boundary definition** — where the boundary actually is shifts
- **Sequencing of next action** — what must happen next changes

If the complement changes none of these five, it is decorative. Suppress it.

### Step 5: Decision Modes

**A. Surface the complement** — the missing expression is structural and load-bearing. State what it is, at what scope, and why it matters.

**B. Defer** — the complement is real but premature. Note it for later without widening current focus.

**C. Suppress widening** — current ray is sufficient for this boundary. Additional complement would reduce closure density or create premature expansion. Actively protect focus.

Mode C is the most important mode. Without it, the skill becomes a sophisticated distraction engine. The skill must be willing to say "current focus is sufficient" more often than it surfaces complements.

## Probe Template

When running the skill, work through this probe internally:

```
TARGET:      What is being moved?
CENTROID:    What larger concern organizes that move?
PARTIALITY:  In what way is the current move incomplete,
             asymmetrical, or mis-scoped?
COMPLEMENT:  What additional directional expression would
             materially improve closure?
SCOPE:       At what rung or layer does that complement belong?
RISK:        Does surfacing this now improve closure,
             or dilute execution focus?
DECISION:    Surface, defer, or suppress.
```

## Examples

### Example 1: Surface (hook case)

```
centroid    = consequential boundary preservation
active ray  = runtime trace preservation (hook fixed)
complement  = semantic/memory preservation (already implicated but unnamed)
scope       = same rung (implementation)
decision    = SURFACE — changes implementation path (memory write needed)
```

The process detected that ray 1 was in focus, the complement was unnamed but implicated, and surfaced it because it changes the implementation.

### Example 2: Suppress (compile fix)

```
centroid    = compile integrity
active ray  = fix invalid import
candidate   = update architectural doc to reflect new dependency
scope       = one rung up (documentation)
decision    = SUPPRESS — doc update does not change current proof
              standard and would dilute execution focus
```

This example teaches restraint. The candidate complement is real but decorative relative to the active boundary. Surfacing it would reduce closure density by pulling attention away from the compile fix into documentation maintenance.

## Context Modes

The skill accepts one of three context depths:

1. **Conversation-only** (default) — works from recent turns, completions, and current artifact. No external reads.
2. **Conversation + local governance surfaces** — also reads active signals, pending CogPRs, routing decisions. Use when the move has governance implications.
3. **Conversation + pattern-mining-context briefing** — also consumes `pattern-mining-context.py` output for statistical surface awareness. Use when the move spans multiple surfaces.

Specify with: `/complement`, `/complement --governance`, `/complement --full`

## Execution

When invoked:

1. Read the last significant completion or landing in this session (recent turns, last commit, last artifact written).
2. Run the six-step runtime internally.
3. Output one of:
   - **Surface**: a concise finding (2-4 sentences) stating the complement, its scope, and why it is structural.
   - **Defer**: a one-line note for later, no action now.
   - **Suppress**: a one-line confirmation that current focus is sufficient. Do not explain what was considered — that would defeat the purpose.

Output must be concise. A finding, not an essay. If the skill produces more than a short paragraph, it has over-widened.

## Constraints

- Manual invocation only. Do not auto-fire.
- Optional post-cadence step (wire later after suppress behavior is validated).
- Per-invocation judgment guided by the five-criteria gate. Do not over-heuristic.
- The skill has explicit permission not to be clever.
