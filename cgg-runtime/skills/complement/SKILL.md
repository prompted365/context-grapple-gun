---
name: complement
description: |
  Closure inference and response-geometry disclosure — direction-agnostic, scope-aware detection of materially missing expressions around an active move.

  CENTROID:
  closure inference at the point of an active move

  IS:
  - post-landing closure check (detect non-local incompleteness after a move lands)
  - origin-shape detection (dual-ray structure at response formulation, before commit)
  - surface/defer/suppress decision routing via the structural-relevance gate

  IS NOT:
    collapse_zones:
      - follow-up helper (complement does not generate next-steps unprompted)
      - pattern mining lite (complement is local coherence, not statistical surface)
      - documentation helper (complement does not restructure existing content)
      - decorative expander (must willingly say "current focus is sufficient" more often than surface)
      - autonomous widener (origin-shape yields shaping choice to the user; never commits the geometry)
    sibling_overlaps:
      - /review (constitutional judgment at the pattern level)
      - /siren (persistent-condition signal emission)
      - pattern mining (statistical surface discovery)

  WHEN:
  - after a local closure event that may hide non-local incompleteness
  - at the point of formulating a response with apparent dual-ray structure
  - when an artifact lands and the caller suspects it is partial
  - on explicit operator invocation

  NOT WHEN:
  - after every trivial step (gates are narrow by design)
  - when the move is within a bounded scope already (compile fix, single-file edit)
  - when current focus must be protected (Mode C suppression is the most important mode)
  - when the candidate complement is decorative (no change to implementation, governance, proof, boundary, or sequencing)

  RELATES TO:
  - /review (constitutional judgment — review promotes lattice-gap findings; complement surfaces closure-geometry gaps)
  - /siren (signal emission — siren records persistent conditions; complement surfaces missing expressions in the active move)
  - pattern mining (statistical — pattern mining scans populations; complement operates on a single active move)

  ARGS:
    stance: lens
    off_envelope: proceed-with-note
    # off_envelope rationale: /complement has an established default (scan current
    # move, conversation-only context). Undeclared-arg most commonly means
    # "apply the default" rather than caller confusion — proceed-with-note
    # preserves the default while logging the invocation for calibration.
    core_dispatch_rays:
      - ""              → post-landing (scan current move)
      - "--origin"      → origin-shape (detect dual-ray before response commits)
      - "--governance"  → post-landing with governance context (signals + CogPRs)
      - "--full"        → post-landing with full context (+ pattern-mining briefing)
    secondary_modulation_axes:
      - emphasis: surface | defer | suppress
      - context_depth: conversation-only | governance | full
user-invocable: true
---

# /complement

Two modes of the same primitive:

- **Post-landing** (`/complement`) — after something lands, detect whether closure is partial
- **Origin-shape** (`/complement --origin`) — before committing to a response, detect latent dual-ray structure and yield the shaping choice

Both are local coherence operations, not follow-up helpers or pattern mining lite.

The origin-shape mode is the stronger primitive. It prevents the two failure modes rather than cleaning up after them:
- assistant stays too narrow and misses the complement
- assistant widens too early and steals the shaping decision

The correct pattern is: **surface the shape before committing to the answer shape**.

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

## Origin-Shape Mode

When invoked with `--origin` (or when the shape is detected at the point of formulating a response), the skill operates before the response commits to a geometry.

### Origin-Shape Runtime

```
1. DETECT that the incoming issue has centroid-complement structure
2. INFER the centroid
3. IDENTIFY the active ray (what the user is asking about)
4. EXPOSE the complementary ray (what is latent but not yet named)
5. YIELD the shaping choice to the user
```

### Origin-Shape Output

When the skill detects a dual-ray / centroid-complement situation at origin, emit:

```
ORIGIN SHAPE
  centroid:           [the governing concern]
  active ray:         [what is being asked about]
  complementary ray:  [what is latent but unnamed]
  unnamed tension:    [if any]
  suggested geometry: single-ray / paired-rays / full-centroid
```

Then yield with something like:

> This looks like a [shape description]. Active ray: X. Likely complement: Y. Respond single-ray, shape both, or respond from centroid?

The user then chooses:

1. **Single-ray** — answer the asked question only, hold the complement
2. **Shape both** — answer with both rays paired, showing the structure
3. **Respond from centroid** — answer from the governing concern outward, letting both rays emerge naturally from the center

Option 3 is the real upgrade. Instead of issue-then-fix-then-realize-complement, it becomes: issue appears, shape detected, centroid inferred, response geometry chosen, answer shaped accordingly.

### What This Provides

Earlier structural legibility. The process becomes:

```
detect shape → show shape → let the user steer response geometry
```

The benefit is not better completion. It is the right to choose the form of the answer before the answer commits to a form.

## Trigger Conditions

**Post-landing mode** (`/complement`): invoke after a **local closure event that may still hide non-local incompleteness**. Not after every trivial step.

**Origin-shape mode** (`/complement --origin`): invoke when formulating a response to something that appears to carry centroid-complement structure. The operative signal is: the issue has more than one directional expression, and committing to one without exposing the other would hide load-bearing structure.

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

### Example 3: Origin-shape (biome trust wiring)

User asks about biome trust scores being stuck. Before responding:

```
ORIGIN SHAPE
  centroid:           visitor economy pipeline integrity
  active ray:         biome engine doesn't emit interaction records
  complementary ray:  cadence runner only recalculates trust at act boundaries
  unnamed tension:    visitor_id vs entity_id field mismatch in runner
  suggested geometry: paired-rays
```

> This is a paired-ray shape. Active: biome emission gap. Complement: cadence runner recalculation frequency + field name bug. Respond single-ray or shape both?

User says "shape both" — response addresses emission, recalculation, and the field bug together as aspects of one centroid rather than discovering the complement mid-implementation.

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

## Feedback Architecture (Layer 3)

The complement of a shape-detection skill is not another shape. It is the feedback architecture that keeps the skill from becoming stale.

Three layers govern this skill:

```
Layer 1: response content        — origin ray / complement ray
Layer 2: response-geometry skill  — origin mode / complement mode
Layer 3: skill governance         — author+invoke+classify / capture+evaluate+calibrate
```

Layers 1 and 2 are the skill's expressive geometry. Layer 3 is its epistemic feedback geometry — the lens-learning loop.

### Invocation Capture

After every `/complement` invocation, append a record to `audit-logs/complement/invocations.jsonl`:

```json
{
  "timestamp": "<iso>",
  "tic": "<current>",
  "mode": "post-landing | origin-shape",
  "decision": "surface | defer | suppress",
  "centroid": "<inferred centroid>",
  "active_ray": "<what was in focus>",
  "complement_candidate": "<what was found or null>",
  "scope": "<rung or layer>",
  "structural_criteria_met": ["<which of the 5>"],
  "user_response": null,
  "outcome": null
}
```

`user_response` and `outcome` are backfilled later:
- **user_response**: what the user chose (accepted / redirected / rejected / no response)
- **outcome**: did the surfaced complement land? did a suppressed complement later matter?

### What This Enables

1. **Suppress quality assessment** — if suppressed complements repeatedly surface later as real issues, the gate is too aggressive
2. **Surface quality assessment** — if surfaced complements are repeatedly rejected or ignored, the gate is too permissive
3. **Centroid inference calibration** — do inferred centroids match what the user actually cares about?
4. **Mode selection evidence** — when does origin-shape add value vs post-landing?

### Calibration Rule

Do not formalize heuristics from fewer than 10 invocations. The skill starts with per-invocation judgment guided by the five-criteria gate. Heuristic refinement comes only from accumulated evidence, not from speculation about what patterns might emerge.

### Meta-Complement Invariant

Every mode-creation process has its own complement: not just how the mode works, but how the mode learns whether it worked. This applies recursively — if someone later builds a feedback-evaluation layer on top of this capture, that layer also needs its own feedback architecture. The recursion terminates when the evaluation loop closes through human judgment (the user saying "that was right" or "you missed something").

### Correction Log

This section records cases where the skill's own gate produced a wrong decision, as calibration evidence:

**Tic 136, invocation 2 (post-landing on origin-shape output):**
Suppressed the feedback-capture complement as "decorative repetition" of the origin-shape finding. Wrong. The complement had been *named* by origin-shape but not *built*. Named is not landed. Two structural criteria were met (verification burden + sequencing). The gate failed to distinguish "this was already surfaced in a prior mode" from "this was surfaced but not yet materialized." Correction: the structural relevance test must evaluate against the state of the complement (built vs named vs unnamed), not just against whether it appeared in recent output.

## Constraints

- Manual invocation only. Do not auto-fire.
- Optional post-cadence step (wire later after suppress behavior is validated).
- Per-invocation judgment guided by the five-criteria gate. Do not over-heuristic.
- The skill has explicit permission not to be clever.
- Named is not landed. A complement that was surfaced but not built is still a valid complement.
