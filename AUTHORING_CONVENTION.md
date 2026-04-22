---
title: "CGG Skill Frontmatter — Authoring Convention"
version: "2.1"
authority: "amendment_v2_1.md Edit 3 (verbatim schema), tic 164"
schema_status: "first-pass — frozen: tier structure, slot names, nesting; open: declaration richness, optional fields"
---

# CGG Skill Frontmatter Authoring Convention (v2.1)

## Schema Block

All CGG skill frontmatter descriptions use this canonical YAML shape.
Fill every placeholder before authoring any rationale or body content.

```yaml
description: |
  <lead sentence — what the skill is in system-level language>

  CENTROID:
  <invariant semantic identity — the thing that does not move across modes, args, or revisions>

  IS:
  - <mode/ray 1>
  - <mode/ray 2>

  IS NOT:
    collapse_zones:
      - <identity failure mode 1 — role this skill must never drift into>
      - <identity failure mode 2>
    sibling_overlaps:
      - <adjacent surface 1 — nearby skill with overlapping scope>
      - <adjacent surface 2>

  WHEN:
  - <coarse cue 1 — lifecycle/state/posture condition>
  - <coarse cue 2>

  NOT WHEN:
  - <coarse anti-cue 1 — past correction or obvious wrong context>

  RELATES TO:
  - <neighbor 1 — named sibling skill and role distinction>
  - <neighbor 2>

  ARGS:
    stance: <dispatch | payload | lens | mixed>
    off_envelope: <ask | proceed-with-note | refuse>
    core_dispatch_rays:
      - <ray string> → <body dispatch target>
    secondary_modulation_axes:
      - <axis name>: <value set>
```

---

## Three-Tier Stratification

Each field belongs to exactly one tier. Tier assignment is doctrine, not convention. Moving a field between tiers requires `/review` — the same gate as modifying constitutional fields.

| Layer | Fields | Authority | Iteration cadence |
|---|---|---|---|
| **Constitutional** | `CENTROID`, `IS`, `IS NOT` → `collapse_zones` | Author drafts; `/review` validates on significant change. Human-gated. | Rare, deliberate |
| **Semi-constitutional** | `core_dispatch_rays`, `off_envelope` (for load-bearing skills) | Author drafts; `/review` notified (no block); ladder-auditor verifies coherence with centroid before next cycle settles the change. | Occasional, identity-adjacent |
| **Tunable** | `WHEN`, `NOT WHEN`, `RELATES TO`, `IS NOT` → `sibling_overlaps`, `secondary_modulation_axes` | Author owns. No gate at authoring time. | Free iteration |

**Note on ARGS nesting:** `core_dispatch_rays` is semi-constitutional even though it appears nested inside `ARGS`. `secondary_modulation_axes` is tunable. These two sub-fields carry different authority levels within the same parent key. Adding a new entry to `core_dispatch_rays` (for example, adding `"half-time"` to `/cadence`) is a semi-constitutional change and requires ladder-auditor coherence verification. Adding a new axis to `secondary_modulation_axes` does not.

**Authoring warning — IS NOT → WHEN transition:** After writing `collapse_zones` and `sibling_overlaps`, the author must shift register entirely. `WHEN` entries must be activation-positive lifecycle conditions. Proximity-negative statements ("not when another skill is in scope") belong in `NOT WHEN` or `sibling_overlaps`, not in `WHEN`.

**Authoring warning — RELATES TO → ARGS transition:** `RELATES TO` is tunable. `core_dispatch_rays` inside `ARGS` is semi-constitutional. This transition crosses a tier boundary without an in-file structural marker. Authors must consult this convention doc to identify the tier boundary — the YAML provides no in-file signal.

---

## Worked Example: `/cadence`

The following is the v2.1 pilot frontmatter for `/cadence`, labeled by tier.

```yaml
description: |
  Session epoch boundary event — emits canonical tic, captures lessons, writes handoff.

  CENTROID:
  session epoch boundary event

  IS:
  - the ONE place the handoff is written; the clock of the governance system

  IS NOT:
    collapse_zones:
      - memory write
      - signal emitter
      - CogPR extractor
      - Mogul spawner
      - inline governance mutation
    sibling_overlaps:
      - /review worker
      - /siren ticker
      - chore executor

  WHEN:
  - once per tic at session end
  - on mid-session epoch boundaries when posture shifts materially

  NOT WHEN:
  - during chores (chores are appetizer, real work happens alongside)
  - after single-step edits
  - when the active plan already covers the thread

  RELATES TO:
  - /review (governance judgment — not a /review worker; /cadence is the clock, /review is the judge)
  - /siren (signal ops — not a /siren ticker; /cadence writes, /siren classifies)
  - Mogul mandate (cadence writes, Mogul consumes)

  ARGS:
    stance: dispatch
    off_envelope: ask
    # off_envelope rationale: /cadence is load-bearing; an undeclared arg may indicate
    # a caller who is confused about skill identity — ask prevents silent misfires.
    core_dispatch_rays:
      - ""           → downbeat (full session hygiene)
      - "double-time" → syncopate (≤5% context emergency variant)
    secondary_modulation_axes:
      - detail: normal | high
      - emphasis: governance | production | projection
```

**Tier labels for the worked example:**

- Constitutional: `CENTROID`, `IS`, `IS NOT.collapse_zones`
- Semi-constitutional: `core_dispatch_rays`, `off_envelope` (set to `ask`)
- Tunable: `WHEN`, `NOT WHEN`, `RELATES TO`, `IS NOT.sibling_overlaps`, `secondary_modulation_axes`

**`off_envelope_default` rationale:** `/cadence` is a load-bearing session governance skill; an undeclared argument most likely signals caller confusion about skill identity, so `ask` is required to prevent silent misfires.

---

## Field Definitions

Each definition states what belongs in the slot and what does not. Authors must read both before filling a field.

### CENTROID (constitutional)

CENTROID is the invariant semantic identity of the skill. It is the thing that does not change across modes, arguments, or revisions.

What belongs: a brief noun phrase or sentence naming the irreducible function of the skill at the system level — the role it holds that no other skill holds. For `/cadence`, this is "session epoch boundary event." For `/review`, this is the constitutional judgment surface for CogPRs and warrants.

What does not belong: a capability summary ("this skill does X and Y"), a WHEN condition ("fires at session end"), or a description of output. If the text would also describe a different skill with a small word change, it is not a centroid — it is a capability description. A capability description belongs in the lead sentence, not in CENTROID.

Changes to CENTROID require `/review`. An empty CENTROID is invalid — it is the structural equivalent of a council record with no `core_truth`.

### IS (constitutional)

IS declares the admissible variation space: the modes, rays, and surfaces the skill can legitimately operate across. These are the rays radiating from the centroid.

What belongs: named modes or rays that the skill explicitly covers. For `/cadence`, this is "the ONE place the handoff is written; the clock of the governance system."

What does not belong: capabilities the skill might incidentally produce, aspirational futures, or descriptions of tunable outputs. IS is not a feature list — it is a bounded declaration of what falls inside the centroid's surface.

Changes to IS require `/review` if they add new functional territory. Narrowing IS (removing a ray) also requires `/review` because it changes what the skill commits to.

### IS NOT — collapse_zones (constitutional)

`collapse_zones` lists identity failure modes: roles the skill must never drift into, because drifting there would cause the skill to lose its centroid.

What belongs: named roles or behaviors that would constitute an identity violation for this skill. For `/cadence`, "memory write" and "inline governance mutation" are collapse zones — if `/cadence` starts writing to MEMORY.md or mutating the queue directly, it has ceased being a boundary event and has become a different kind of agent.

What does not belong: tunable preferences, capability boundaries, or descriptions of what the skill is bad at. An entry that describes "this skill is not good at X" is not a collapse zone — it is a capability limitation. An entry that describes a neighboring skill's territory ("not a /review surface") belongs in `sibling_overlaps`, not `collapse_zones`.

An empty `collapse_zones` list is invalid. Every centroid has negative contour. A skill without collapse zones has an unmeasurable identity.

Collapse zone drift is the highest-severity audit finding. The ladder auditor must escalate immediately if a collapse zone entry is removed without a corresponding centroid change.

### IS NOT — sibling_overlaps (tunable)

`sibling_overlaps` lists adjacent skills whose scope overlaps with this skill's scope, creating routing ambiguity that authors must explicitly declare.

What belongs: named, currently-existing skills that compete for the same task shape. For `/cadence`, `/review worker`, `/siren ticker`, and `chore executor` are sibling overlaps — these are the roles callers might mistakenly assign to `/cadence`.

What does not belong: collapse-zone-level identity failures. If an entry describes a behavior that would make the skill lose its centroid (not just a routing confusion), it belongs in `collapse_zones`, not `sibling_overlaps`. Misclassifying a collapse zone as a sibling overlap is the conflation pattern this two-field structure was designed to prevent.

Sibling overlap entries that reference non-existent or renamed skills trigger a `strained` classification in ladder audit. Sibling overlap rot is a scheduled maintenance issue, not a constitutional violation.

### WHEN (tunable)

WHEN declares the coarse lifecycle or posture conditions under which invoking this skill is correct.

What belongs: observable, activation-positive conditions. For `/cadence`, "once per tic at session end" and "on mid-session epoch boundaries when posture shifts materially" are WHEN conditions. They describe a system state, not a capability.

What does not belong: proximity-negative statements ("when no other skill is applicable"), capability descriptions ("when the session needs a summary"), or negations of WHEN entries. WHEN entries must answer "when is this skill correct?" — not "when is it not wrong?"

Author owns tunable fields. WHEN entries may be iterated freely without `/review`.

### NOT WHEN (tunable)

NOT WHEN declares the anti-conditions: past corrections and obvious wrong contexts that the model would otherwise miss.

What belongs: operator-validated corrections from real session experience. For `/cadence`, "during chores" and "after single-step edits" are corrections from operator feedback (`feedback_chores-not-session.md`). NOT WHEN encodes learning the model cannot infer from WHEN alone.

What does not belong: the negation of every WHEN entry ("not when the session is not at epoch boundary" — this adds no information). NOT WHEN is for non-obvious anti-conditions, not logical complements of WHEN.

### RELATES TO (tunable)

RELATES TO names sibling skills and states their role distinction from this skill.

What belongs: named sibling skills plus a brief disambiguation clause. For `/cadence`, "/review (governance judgment — not a /review worker; /cadence is the clock, /review is the judge)" names the sibling and distinguishes roles in one clause.

What does not belong: skills that are not currently active in the skill set, vague relationship descriptions ("related to session management"), or routing rules that belong in `sibling_overlaps`.

### ARGS (mixed: semi-constitutional + tunable)

ARGS holds two sub-fields at different authority levels. Treat them separately.

What does not belong in ARGS: capability descriptions, output descriptions, or free-form prose about what the skill produces. ARGS is a dispatch contract, not a documentation field. Free-form prose belongs in the lead sentence or body. Putting invocation logic into `secondary_modulation_axes` that belongs in `core_dispatch_rays` mis-tiers the content (treating a dispatch decision as a tunable preference).

`stance` (tunable): the dispatch posture of the skill — `dispatch` (arg routes to body handler), `payload` (arg is content for the skill to process), `lens` (arg colors the skill's perspective), or `mixed`. Author owns.

`off_envelope` (semi-constitutional for load-bearing skills): what the skill does when invoked with an undeclared argument. Values: `ask` (pause and confirm), `proceed-with-note` (execute with a logged note), `refuse` (halt and explain). For load-bearing skills, `off_envelope` is identity-adjacent — drifting from `ask` to `proceed-with-note` for convenience changes the skill's contract with its callers. Changes to `off_envelope` for load-bearing skills require `/review` notification and ladder-auditor coherence verification.

`core_dispatch_rays` (semi-constitutional): the declared named rays the skill body handles. An empty string (`""`) is the default ray (no argument supplied). Named strings are explicit arg values. Adding a new ray is a semi-constitutional change — it extends the skill's dispatch contract. Removing a ray is also semi-constitutional — it changes what callers can invoke.

`secondary_modulation_axes` (tunable): named axes that modulate how the skill executes within a ray. For `/cadence`, `detail: normal | high` and `emphasis: governance | production | projection` are modulation axes. Author owns. No gate at authoring time.

---

## Authority Path

Changes to `CENTROID`, `IS`, or `IS NOT.collapse_zones` require `/review`. Changes to `core_dispatch_rays` or `off_envelope` (for load-bearing skills) require notifying `/review` and require ladder-auditor coherence verification before the next cycle settles the change. Changes to `WHEN`, `NOT WHEN`, `RELATES TO`, `IS NOT.sibling_overlaps`, and `secondary_modulation_axes` do not require `/review` or notification — author owns.

Tier assignment itself is constitutional. Moving a field from one tier to another requires `/review`.

---

## Known Failure Modes

The drift audit identifies three common silent-miss patterns. Each has a fix.

**Invocation-when gap:** The skill description states what the skill does but not when invoking it is correct. The model cannot infer WHEN from capability descriptions. Fix: fill `WHEN` with observable lifecycle conditions, not feature descriptions.

**Anti-invocation gap:** The skill has no NOT WHEN entries. The model over-invokes or routes to the wrong neighbor when there is no stated anti-condition. Fix: fill `NOT WHEN` with operator-validated corrections from real session experience — not logical complements of WHEN entries.

**Sibling-disambiguation gap:** The skill names a sibling in `RELATES TO` but does not state the routing criterion. The model cannot distinguish which skill applies when two seem equivalent. Fix: every `RELATES TO` entry must include a disambiguation clause. State why this skill and not the named sibling.

---

## Rollback — Constitutional-Tier Fields

This section applies when a CENTROID, IS, or IS NOT.collapse_zones change must be reverted.

**Pre-condition:** the change has been committed to the canonical repo. If the change is only staged or only in working tree, discard it directly.

**Steps:**
1. Run `git diff HEAD -- <path/to/SKILL.md>` to identify the exact frontmatter change.
2. Run `git checkout HEAD -- <path/to/SKILL.md>` to restore the pre-change state.
3. Sync the installed copy: `cp <canonical-path>/SKILL.md ~/.claude/cgg-runtime/skills/<skill-name>/SKILL.md`
4. Verify: `diff <canonical-path>/SKILL.md ~/.claude/cgg-runtime/skills/<skill-name>/SKILL.md` — expected output: empty.
5. Commit the rollback with a message referencing the defect and the tic.
6. Notify ladder-auditor: the constitutional change is reverted. The audit classification (`strained`, `demotion_pressure`) must also be cleared or updated in the relevant audit surface.

**What rollback does not cover:** if live sessions were relying on the changed centroid for skill disambiguation at selection time, those sessions carry a stale map until they reload the installed skill. This is an expected consequence of constitutional revert — it does not require additional remediation unless operator observes active misfires.

---

## Substrate Render Deferral

Skill declarations are NOT currently registered entities in `autonomous_kernel/actor-registry.json` or any equivalent entity registry. They are capability surface contracts, not federation entities.

Skills therefore carry no substrate render obligation in the Anchorage 3D scene. This deferral is conditional — it lifts if any of the following occur:
1. Skill declarations are assigned entity IDs in the actor-registry or equivalent.
2. A decision is made to make skill centroids visible in substrate scene overlays (for example, as a "capability surface" rung layer).

**Re-evaluation tic:** tic 167 (three tics post-rollout). Review whether the `/cadence` pilot generated any substrate-visibility requests from citizens or operators.

**Why this must be stated here:** the councils-skills isomorphism invites a transitive inference: councils are registered substrate entities; skills are their rung-isomorph; therefore skills must also register. Without an explicit deferral in this convention doc, a future engineer may act on that inference without flagging it. This doc must carry the deferral because it is visible at the point of action.

---

## Schema Status — Frozen vs Open

**Frozen (do not modify without `/review`):**
- The three-tier stratification (constitutional / semi-constitutional / tunable)
- All slot names: `CENTROID`, `IS`, `IS NOT`, `collapse_zones`, `sibling_overlaps`, `WHEN`, `NOT WHEN`, `RELATES TO`, `ARGS`, `stance`, `off_envelope`, `core_dispatch_rays`, `secondary_modulation_axes`
- The nesting structure (collapse_zones and sibling_overlaps as nested keys inside IS NOT)
- The tier assignment of each field (see Three-Tier Stratification table)

**Open (author controls):**
- How rich each author makes their declarations (minimal acceptable: non-empty CENTROID, at least one IS entry, at least one collapse_zone, at least one WHEN entry)
- Optional fields not in this schema (for example, `deprecated: true`) — must be marked provisional until reviewed
- Pole structure for dialectical skills (for example, Complement C10 skills) — consult current convention doc version before adding

Adding any field beyond this canonical schema to a normative frontmatter requires human review before the field enters convention. Adding it as provisional with an explicit annotation is permitted.

---

## Audit Phase Declaration

The ladder auditor applies this convention in three phases. Authors must know the current phase to understand which findings are active.

| Phase | Condition | Audit scope |
|---|---|---|
| **Bootstrap** | Before `/cadence` pilot lands | Constitutional-tier fields only. Tunable field rot is not auditable — convention not yet established. |
| **Steady-state** | After `/cadence` pilot, before batch rewrite | All three tiers for pilot skills only (`/cadence`, then `/review`). Non-pilot skills are out of scope. |
| **Mature** | After batch rewrite of top drifters | Full cross-skill audit. Sibling_overlap stale-name detection across the entire skill set. |

Auditing non-migrated skills against this schema during Bootstrap or Steady-state produces false positives that mask genuine constitutional violations.

---

*Authority: amendment_v2_1.md Edit 3 (verbatim schema), oa54_review.md (translation-discipline warning), spec.md §4–§7 (tone-audit rules, three-tier stratification, substrate deferral). Authored: tic 164, Run 2, Agent α.*
