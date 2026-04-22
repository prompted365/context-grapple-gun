---
name: stage
description: |
  Orchestrate governed reasoning arenas. Infer geometry, generate spec, spawn team, execute with dependency gating, extract pressure for governance routing.

  CENTROID:
  governed reasoning arena orchestration

  IS:
  - arena geometry inference (dyadic, triangulation, tournament-lattice, CRX, VPL, OA-VPL-T)
  - show spec generation (YAML: agents, positions, capture policy, pressure path)
  - team spawning with dependency-gated phase execution
  - pressure extraction and routing to governance surfaces

  IS NOT:
    collapse_zones:
      - doctrine judgment (arenas produce CogPRs and signals; /review judges them — stage does not promote)
      - deliverable orchestrator (stage spawns reasoning agents; /swarm spawns deliverable agents)
      - ambient signal emitter (stage emits arena-scoped pressure; /siren emits ambient signals)
      - human-gated review surface (arenas produce governance input; the human gate is /review)
      - autonomous arena closer (arenas close on phase completion, not author discretion)
    sibling_overlaps:
      - /swarm (parallel orchestration)
      - /review (constitutional judgment)
      - pattern mining (cross-surface analysis)

  WHEN:
  - when a decision has ≥2 distinct positions requiring adversarial examination
  - when ambient reasoning is insufficient and governance input requires structured pressure
  - when arena geometry is known or can be inferred from decision space
  - on explicit operator invocation

  NOT WHEN:
  - for parallel deliverable work (use /swarm — adversarial vs coordinated orchestration)
  - for decisions with <2 distinct positions (no pressure to extract)
  - for work already committed to a single approach (arena would be theater)
  - mid-implementation when the arena's pressure cannot be routed back to an open surface

  RELATES TO:
  - /swarm (orchestration — swarm is parallel deliverable; stage is adversarial reasoning)
  - /review (constitutional judgment — stage produces CogPRs and signals; review promotes them)
  - pattern mining (cross-surface — pattern mining scans populations; stage produces per-arena pressure)

  ARGS:
    stance: mixed
    off_envelope: ask
    # off_envelope rationale: /stage has ray ambiguity (interactive vs --decision
    # vs --spec resume vs --template vs --mode). Undeclared-arg may indicate
    # caller confused between /stage (reasoning arena) and /swarm (parallel
    # delivery) — ask prevents silent misroutes into the wrong orchestration.
    core_dispatch_rays:
      - ""            → interactive (ask decision + positions, infer geometry)
      - "--decision"  → direct mode (skip interactive prompt)
      - "--spec"      → resume or inspect existing show spec
      - "--template"  → override geometry inference
      - "--mode"      → arena mode (operational | experimental)
      - "--dry-run"   → generate spec without spawning team
    secondary_modulation_axes:
      - template: tri | lattice | crx | vpl | oa-vpl-t
      - mode: operational | experimental
      - positions: 2 | 3 | 4 | 5 | 6 | 7
user-invocable: true
---

# /stage — Governed Reasoning Arena Launcher

Orchestrate adversarial reasoning through governed arenas. Arenas produce high-confidence governance inputs (signals, lessons, CogPRs) through structured opposition.

## Invocation

- **`/stage`** — interactive mode. Ask what the user is deciding, infer arena geometry.
- **`/stage --decision "<statement>"`** — direct mode. Skip interactive prompt.
- **`/stage --spec <path>`** — resume or inspect an existing show spec.
- **`/stage --template tri|lattice|crx|vpl|oa-vpl-t|evidence-rebuttal|harpoon`** — override geometry inference.
- **`/stage --mode operational|experimental`** — set arena mode (default: operational).
- **`/stage --dry-run`** — generate spec without spawning team.

## Arena Geometry Selection

Geometry selection is **question-type-driven and role/office-driven**, not position-count-driven. Constitutional actors fill roles; positions materialize from their jurisdictional mandates, values, priorities, and evidence bases — not from assigned stance labels. Labels-only geometry produces theater (advocates checklist-optimize against assigned criteria); role-driven geometry produces authentic, resilient, honestly adversarial pressure.

### Geometry selection by question type

| Question type | Geometry | Template | Actors |
|---|---|---|---|
| Operational decision (bounded scope, clear tradeoffs) | Governed Triangulation | `governed-triangulation` | Offices with stake in the decision (3 actors typical; 2 agents for dyadic) |
| Constitutional question (federation shape, rights, obligations, authority) | Value-Position Lattice | `value-lattice` | Constitutional actors: Mogul, Crisis Steward, CBUX Steward, Civil Engineer, Ladder Auditor (+ wildcard chain-coherence challenger) |
| Cross-rung / cross-jurisdictional exploration | Cross-Rung Orientation | `cross-rung-orientation` | Domain triad + meta-pair (expansion / constraint constitutional emissaries) + ecotone synthesis |
| Office-autonomous with temporal tension | OA-VPL-T | `office-autonomous-vpl` | Offices self-derive positions from mandate (Phase 0a/0b); T0-T5 temporal modeling |
| Hypothesis testing (coincidence / mechanism / counterfactual) | Evidence-Rebuttal (Epistemic Triangulation) | `evidence-rebuttal` | Claim advocate + evidence advocate + rebuttal/counterfactual advocate |
| External-system adoption assessment | Governed Harpoon Triangulation | `governed-harpoon-triangulation` | PASS / NO / CATALYZE advocates |
| Tournament across 4-7 opposing positions | Tournament Lattice | `tournament-lattice` | Bracket-isolated advocates with wildcard chain-coherence challenger |

### Role / office-driven advocacy

Prefer constitutional actors over generic labels whenever a question has jurisdictional stake. An actor's mandate IS its value centroid; its operational data IS its evidence base. Authenticity compounds: an actor reasoning from genuine stake produces convergence when convergence is warranted and stalemate when stalemate is warranted — not both collapsed into compliance theater.

For Governed Triangulation and Tournament Lattice, actors may be offices, domain experts, or generic advocates — but if a constitutional actor has stake, prefer that actor.

For VPL and OA-VPL-T, constitutional-actor framing is load-bearing. Do not substitute generic labels.

### Position count is downstream

Position count follows from geometry + actor selection, not the reverse. Do not pre-commit to a geometry by counting positions. Classify the question first, identify actors with jurisdictional stake, then select the geometry that fits that class. If the result yields 8+ positions, reconsider whether bracket isolation (VPL, Tournament Lattice) handles the spread.

### Right-sizing — avoid default-to-max

Do not default to 7-wide or 11-wide tournaments. Large-scale geometry is correct for federation-shape questions with genuinely wide opposing-constitutional-actor fields; it is not correct for design review, pattern discrepancy, ambiguity resolution, or focused problem solving. A **lean arena** (e.g., 2 actors + wildcard, or governed-triangulation with 3 actors) is often the right geometry — fast, focused, honestly adversarial, and cheap to run.

Use lean arenas for:
- targeted design or implementation decisions
- pattern discrepancy / ambiguity resolution
- /complement closure-inference challenges
- /consolidate context-scope verification
- small-scope problem solving where actors and question are clear

Use wide arenas (VPL, tournament-lattice, OA-VPL-T) only when the question genuinely requires broad constitutional surface coverage. Arena cost scales nonlinearly with advocate count — lead context accumulation (per Lead Context as Binding Constraint) is the real ceiling, not advocate capability.

### Actor-backed belief systems vs spec-crafted opposing values

Prefer **actor-backed value divergence**: when constitutional actors have jurisdictional stake, their values naturally diverge from their mandates and evidence bases. The disagreement is organic, not framed.

**Spec-crafted opposing-values geometry** (where the show spec assigns values like "completeness vs coherence vs efficiency" to generic advocates) is a fallback pattern for cases where no naturally-diverging actors are available. It works, but is susceptible to framing bias — whoever authored the spec chose which values oppose which, and that framing silently shapes advocacy.

When both are available (an actor-backed geometry and a spec-crafted one), prefer the actor-backed. Reserve spec-crafted opposing-values for cases where actor stakes don't naturally pull apart on the question.

## Execution Steps

### Step 1: Classify Question and Identify Actors

**Interactive mode** (no `--decision`):
1. Ask: "What are you deciding? Describe the decision space."
2. Classify the question type (operational / constitutional / cross-rung / office-temporal / hypothesis / harpoon / tournament).
3. Identify jurisdictionally-relevant constitutional actors (Mogul, Crisis Steward, CBUX Steward, Civil Engineer, Ladder Auditor) when the question has federation-level stake. Prefer constitutional actors over generic labels.
4. Confirm the geometry selection with the user. Positions will materialize from actors' mandates and evidence bases; do not pre-assign stance labels.

**Direct mode** (`--decision`):
1. Parse decision statement.
2. Classify the question type from the statement.
3. Propose actors (constitutional preference when jurisdictional stake applies) and the matching geometry.
4. Confirm with user unless `--template` is explicit.

### Step 2: Resolve Template

1. Select the template directory name from the Geometry Selection table in §Arena Geometry Selection. Template names on disk:
   - `governed-triangulation`
   - `tournament-lattice`
   - `cross-rung-orientation` (CRX)
   - `value-lattice` (VPL)
   - `office-autonomous-vpl` (OA-VPL-T)
   - `evidence-rebuttal`
   - `governed-harpoon-triangulation`
2. Locate template directory:
   - Search `$CGG_PLUGIN_ROOT/stage/templates/arenas/<template>/`
   - Fallback: `$ZONE_ROOT/stage/templates/arenas/<template>/`
   - Fallback: `$ZONE_ROOT/canonical_developer/context-grapple-gun/stage/templates/arenas/<template>/`
3. Read `spec.md`, `tasks.yaml`, `scoring.yaml` from template.
4. If template not found, report error.

### Step 3: Generate Show Spec

Create a show specification YAML:

```yaml
id: "<YYYY-MM-DD>_<slugified-decision>"
title: "<decision statement>"
arena: governed-triangulation | tournament-lattice
arena_mode: operational | experimental
status: staged
template_ref: "<template path>"
created_at: "<ISO-8601>"
created_tic: <current tic number>
agents:
  - name: ADVOCATE-A
    position: "<Position A description>"
  - name: ADVOCATE-B
    position: "<Position B description>"
  - name: ADVOCATE-C
    position: "<Position C description>"
  - name: LEAD
    position: orchestrator (does not advocate)
capture_policy:
  allow_subject_lessons: true
  route_subject_lessons_to_governance: true  # false if experimental
  allow_signals: true  # false if experimental
  allow_governance_mutation: false  # always — human-gated via /review
pressure_report_path: "audit-logs/arenas/pressure-reports/<id>.json"
outcome: {}
```

Save to `stage/specs/<id>.yaml`.

If `--dry-run`: report the generated spec and exit.

### Step 4: Validate

Before spawning:
1. Verify all task dependencies form a valid DAG (no cycles).
2. Verify all phases present: context → defense → rebuttal → synthesis → pressure_extraction.
3. Verify agent count matches template requirements.
4. Verify `stage/shows/` directory exists (create if needed).

### Step 5: Spawn Team

Create an agent team using the template's task structure:

1. Spawn each ADVOCATE agent with:
   - Its position assignment
   - The full arena spec (rules from `spec.md`)
   - Task blockers from `tasks.yaml`
2. The LEAD role is played by the orchestrator (you). Do NOT advocate any position.
3. Update show spec `status: "staged" → "live"`.

**Phase enforcement**: Tasks must respect their `blocked_by` lists. Do not advance any agent to the next phase until ALL prerequisite tasks complete.

**Phase sequence** (non-negotiable):
```
context [parallel] → defense [parallel] → rebuttal [parallel] → synthesis [serial] → pressure extraction [serial]
```

### Step 6: Monitor Phases

For each phase:
1. Wait for all tasks in the phase to complete.
2. Verify outputs meet scoring criteria from `scoring.yaml`.
3. Log phase completion: `[phase: context] complete — 3/3 tasks`.
4. Advance to next phase only when ALL tasks in current phase complete.

**Lead neutrality invariant**: During synthesis and all prior phases, you must not advocate for any position. Your job is to extract surviving structure, not to pick a winner.

### Step 7: Synthesis

After all rebuttals complete:
1. Read all advocate outputs (context reports, defenses, rebuttals).
2. Extract surviving structure — what survived challenge from all directions.
3. Identify dependency graph among surviving elements.
4. Propose implementation order if applicable.
5. Write synthesis to `stage/shows/<id>/synthesis.md`.

### Step 8: Pressure Extraction

After synthesis:
1. Classify all findings along two axes:

| Lesson Type | Description |
|------------|-------------|
| subject | About the decision topic itself |
| process | About how the arena ran / could run better |
| meta | About governance, learning, or the system |

| Confidence Tier | Criteria |
|----------------|---------|
| convergent | Independently discovered by 2+ opposed agents |
| reinforced | Supported by evidence from multiple phases |
| tentative | Single-source or speculative |

2. Route by mode and confidence:

| Finding | Operational Mode | Experimental Mode |
|---------|-----------------|-------------------|
| convergent subject | → BEACON candidate | BLOCKED |
| reinforced subject | → CogPR candidate | BLOCKED |
| tentative subject | → notes only | BLOCKED |
| convergent process/meta | → BEACON candidate | → BEACON candidate |
| reinforced process/meta | → CogPR candidate | → CogPR candidate |
| surviving contradictions | → TENSION candidate | → TENSION candidate |

3. Write pressure report to `audit-logs/arenas/pressure-reports/<id>.json`:

```json
{
  "arena_id": "<id>",
  "arena_mode": "operational|experimental",
  "template": "governed-triangulation|tournament-lattice",
  "created_at": "<ISO-8601>",
  "source_tic": <tic>,
  "convergent_discoveries": [],
  "unresolved_tensions": [],
  "candidate_signals": [],
  "candidate_cogprs": [],
  "process_lessons": [],
  "meta_lessons": [],
  "false_convergence_risks": []
}
```

### Step 9: Governance Routing

After pressure extraction:

1. For each `candidate_signal`: emit to `audit-logs/signals/YYYY-MM-DD.jsonl` using standard signal format with `"source": "arena:<id>"`.
2. For each `candidate_cogpr`: append to `audit-logs/cprs/queue.jsonl` with birth context including `arena_id`.
3. Enforce mode: if `experimental`, skip ALL subject-type candidates (do not emit them).
4. Log all routing decisions to microscan staging.

### Step 10: Report

```
/stage complete

Arena:      <id>
Template:   governed-triangulation | tournament-lattice
Mode:       operational | experimental
Positions:  N agents
Phases:     5/5 complete

Synthesis:  stage/shows/<id>/synthesis.md
Pressure:   audit-logs/arenas/pressure-reports/<id>.json

Governance routing:
  Signals emitted: N (M convergent, K tensions)
  CogPRs queued:   N
  Blocked (mode):  N subject candidates (experimental mode)

Next: /review to evaluate arena-generated candidates
```

Update show spec `status: "live" → "completed"`.

## Arena Registry

Append completed arena to `audit-logs/arenas/registry.jsonl`:

```json
{
  "type": "arena_run",
  "arena_id": "<id>",
  "template": "governed-triangulation",
  "mode": "operational",
  "participants": 4,
  "start_tic": <N>,
  "end_tic": <N>,
  "pressure_report_path": "audit-logs/arenas/pressure-reports/<id>.json",
  "signals_emitted": <N>,
  "cogprs_queued": <N>,
  "status": "completed",
  "completed_at": "<ISO-8601>"
}
```

## Post-Processing: Arena Report Pipeline

After Step 10 (Report), optionally generate an archivist-envelope HTML report:

1. Run `arena-report-generator.py --zone-root $ZONE_ROOT --arena-id $ARENA_ID`
   (or `--tic N` for multi-arena sessions)
2. This produces a `report-manifest.json` in the show directory
3. Dispatch `arena-report-agent` (spec: `cgg-runtime/agents/arena-report-agent.md`)
   with the manifest path to generate the HTML report
4. The HTML report embeds JSON-LD archivist envelope metadata for governance retrieval

For multi-arena sessions (e.g., /cadence close with 2+ arenas), use `--tic N` to
capture all arenas sharing a source tic in a single unified report.

The report pipeline is archivist-envelope-compliant:
- Capability: `knowledge.extract`
- Envelope type: `knowledge.summary`
- Callback mode: `artifact`

## Critical Invariants

1. **Role/office-driven, not position-assigned** — positions materialize from actors' jurisdictional mandates, values, priorities, and evidence bases. Generic label-assigned positions produce theater (checklist-optimization against assigned criteria); role-driven positions produce authentic, resilient, honestly adversarial pressure. Constitutional actors (Mogul, Crisis Steward, CBUX Steward, Civil Engineer, Ladder Auditor) have natural value centroids from their mandates and natural evidence bases from operational data — prefer them whenever jurisdictional stake applies.
2. **Actor-backed belief systems over spec-crafted opposing values** — prefer naturally-diverging actor values over spec-assigned opposing-value labels. Spec-crafted opposing-values geometry works but carries framing bias from the spec author. Use it only when no naturally-diverging actors are available for the question.
3. **Question-type-driven geometry selection** — classify the question first (operational / constitutional / cross-rung / office-temporal / hypothesis / harpoon / tournament), then pick the geometry that fits. Position count is downstream of geometry + actor selection, never the primary axis.
4. **Right-sized arenas — avoid default-to-max** — do not default to 7-wide or 11-wide tournaments. Lean arenas (2 + wildcard, governed-triangulation with 3) are often the right geometry for design review, pattern discrepancy, ambiguity resolution, and focused problem solving. Reserve wide geometries for genuinely federation-surface-wide questions. Lead context is the binding constraint, not advocate capability.
5. **No skipping phases** — enforced at agent spawn via task blockers
6. **Lead stays neutral** — orchestrator, not advocate
7. **Synthesis waits for all rebuttals** — dependency gating
8. **Pressure extraction is mandatory** — arena incomplete without it
9. **Governance mutation is human-gated** — all routing to `/review`, no auto-update to CLAUDE.md
10. **Convergent discoveries are high-confidence signal** — independently discovered by opposed agents
11. **Experimental mode blocks subject lessons** — only process/meta lessons route to governance
12. **Arena registry is append-only** — audit trail
13. **Post-hoc invariant conformation** — do not score advocate positions against invariants during their turns; score after advocacy completes. In-arena scoring collapses advocacy into checklist-optimization.

## Directory Structure

```
stage/
  templates/arenas/
    governed-triangulation/     # 3-position template
    tournament-lattice/         # 4-7 position template
  specs/                        # Generated show specifications (versioned)
  shows/                        # Per-run artifacts (disposable, gitignored)

audit-logs/arenas/
  pressure-reports/             # Structured pressure extraction outputs
  registry.jsonl                # Completed arena run metadata
```

## Ownership

This skill owns:
- `stage/specs/*.yaml` (create)
- `stage/shows/<id>/` (create, write synthesis)
- `audit-logs/arenas/pressure-reports/<id>.json` (create)
- `audit-logs/arenas/registry.jsonl` (append)

This skill emits to (does not own):
- `audit-logs/signals/*.jsonl` (standard signal format)
- `audit-logs/cprs/queue.jsonl` (standard CogPR format)

This skill never modifies:
- CLAUDE.md (promotion is human-gated via `/review`)
- MEMORY.md (lessons route through CogPR pipeline)
- `.ticzone` (zone config is admin-only)
