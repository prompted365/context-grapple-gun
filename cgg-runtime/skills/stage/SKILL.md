---
name: stage
description: "Orchestrate governed reasoning arenas. Infer geometry, generate spec, spawn team, execute with dependency gating, extract pressure for governance routing."
user-invocable: true
---

# /stage — Governed Reasoning Arena Launcher

Orchestrate adversarial reasoning through governed arenas. Arenas produce high-confidence governance inputs (signals, lessons, CogPRs) through structured opposition.

## Invocation

- **`/stage`** — interactive mode. Ask what the user is deciding, infer arena geometry.
- **`/stage --decision "<statement>"`** — direct mode. Skip interactive prompt.
- **`/stage --spec <path>`** — resume or inspect an existing show spec.
- **`/stage --template tri|lattice`** — override geometry inference.
- **`/stage --mode operational|experimental`** — set arena mode (default: operational).
- **`/stage --dry-run`** — generate spec without spawning team.

## Arena Geometry Inference

Count distinct positions in the decision space:

| Positions | Arena | Template |
|-----------|-------|----------|
| 2 | Dyadic (head-to-head) | `governed-triangulation` with 2 agents |
| 3 | Governed Triangulation | `governed-triangulation` |
| 4–5 | Tournament Lattice (5-agent) | `tournament-lattice` |
| 6 | Tournament Lattice (6-agent) | `tournament-lattice` (two full triangles) |
| 7 | Tournament Lattice (7-agent) | `tournament-lattice` (two triangles + wildcard auditor) |
| 8+ | Error | Ask user to cluster into ≤7 positions |

If the user provides fewer than 2 or more than 7 positions, ask them to adjust.

## Execution Steps

### Step 1: Gather Context

**Interactive mode** (no `--decision`):
1. Ask: "What are you deciding? Describe the decision space."
2. Ask: "What are the distinct positions or approaches being considered?"
3. Count positions. If ambiguous, confirm with user.

**Direct mode** (`--decision`):
1. Parse decision statement.
2. Infer positions from the statement.
3. Confirm position count with user unless `--positions N` is explicit.

### Step 2: Resolve Template

1. Determine arena size from position count (see table above).
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

## Critical Invariants

1. **No skipping phases** — enforced at agent spawn via task blockers
2. **Lead stays neutral** — orchestrator, not advocate
3. **Synthesis waits for all rebuttals** — dependency gating
4. **Pressure extraction is mandatory** — arena incomplete without it
5. **Governance mutation is human-gated** — all routing to `/review`, no auto-update to CLAUDE.md
6. **Convergent discoveries are high-confidence signal** — independently discovered by opposed agents
7. **Experimental mode blocks subject lessons** — only process/meta lessons route to governance
8. **Arena registry is append-only** — audit trail

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
