---
name: governance-mandate-cycle
description: |
  Execute pending Mogul governance mandate using the mandate-pattern-triangulation team. Spawns Mogul as background agent to consume mandate cycles.

  CENTROID:
  Mogul mandate execution interface

  IS:
  - foreground mandate dispatch (wraps Mogul spawning with mandate context)
  - status-check surface for current mandate
  - explicit-deferral surface (skip with reason)
  - blocking/non-blocking execution control

  IS NOT:
    collapse_zones:
      - mandate author (cadence writes mandates; this skill consumes them)
      - governance judgment (Mogul produces disposition; /review promotes pattern candidates)
      - autonomous mandate runner (activation fabric runs at SessionStart; this skill is the manual trigger)
      - doctrine modifier (Mogul is read-only on CLAUDE.md/MEMORY.md by design)
      - team-topology authority (mandate-pattern-triangulation is referenced here but owned by Mogul)
    sibling_overlaps:
      - /cadence (mandate authoring side)
      - /review (constitutional judgment)
      - Mogul agent (the thing this skill dispatches)

  WHEN:
  - when a pending mandate exists and was not auto-consumed at SessionStart
  - when a blocking (synchronous) mandate run is operationally required
  - when status inspection without execution is needed
  - when the Architect explicitly defers the current mandate with rationale
  - on explicit Architect invocation

  NOT WHEN:
  - when the mandate is already `started` or `completed`
  - when no pending mandate exists
  - during /cadence (cadence writes the mandate; this skill consumes — same boundary cannot do both)
  - when the activation fabric has already dispatched in background (check status first)

  RELATES TO:
  - /cadence (mandate authoring — cadence writes; this skill consumes; distinct boundaries)
  - /review (constitutional judgment — Mogul produces disposition; review inscribes pattern candidates)
  - Mogul agent (execution vehicle — this skill is the dispatcher; Mogul is the worker)

  ARGS:
    stance: dispatch
    off_envelope: ask
    # off_envelope rationale: /governance-mandate-cycle routes to dispatch,
    # status-check, or defer — three distinct operations. Undeclared-arg may
    # indicate caller confused between this skill and /cadence (which writes
    # mandates, not consumes them) — ask prevents silent misroutes.
    core_dispatch_rays:
      - ""            → execute current mandate (background, non-blocking)
      - "--blocking"  → execute and wait for completion
      - "--status"    → report current mandate state without executing
      - "--skip"      → explicitly defer with reason
    secondary_modulation_axes:
      - team_topology: mandate-pattern-triangulation | <other>
      - depth_profile: verification | active | hazard | post-review
      - output_location: default | <path>
user-invocable: true
---

# /governance-mandate-cycle — Mogul Mandate Execution

Spawn Mogul to execute the current governance mandate. This is the manual trigger for mandate consumption — the same work that the SessionStart hook prompts for automatically.

## Invocation

- **`/governance-mandate-cycle`** — execute current mandate (default: background, non-blocking)
- **`/governance-mandate-cycle --blocking`** — execute and wait for results before continuing
- **`/governance-mandate-cycle --status`** — check mandate status without executing
- **`/governance-mandate-cycle --skip`** — explicitly defer the current mandate with reason

## Preconditions

1. A mandate must exist at `audit-logs/mogul/mandates/current.json` with `status: "pending"`
2. If no pending mandate exists, report "No pending mandate" and exit
3. If mandate is already `started` or `completed`, report status and exit

## Execution

### Status check (`--status`)

Read `audit-logs/mogul/mandates/current.json` and report:
- Mandate ID, status, trigger source
- Cycles requested (`cycle_request.run_now`)
- Tic context (current, due dates)
- Whether runtime truth has been verified

### Skip (`--skip`)

Update `audit-logs/mogul/mandates/current.json`:
- Set `status: "deferred"`
- Set `completed_at` to current ISO timestamp
- Append to `audit-logs/mogul/mandates/history/YYYY-MM-DD.jsonl`
- Log reason (prompt user for reason if not provided)

### Execute (default)

1. Read the current mandate
2. Validate it is `pending`
3. Spawn Mogul agent:

```
Agent(
  subagent_type: "mogul",
  run_in_background: true,  # unless --blocking
  prompt: "Execute mandate {mandate_id}. Mandate at: audit-logs/mogul/mandates/current.json.
           Cycles: {cycle_request.run_now}.
           Use the mandate-pattern-triangulation team topology for pattern_mining + ladder_audit + runtime_drift_check cycles.
           Prepare compact anti-dup signatures before team creation.
           Synthesize all findings into a disposition packet at audit-logs/mogul/runs/{mandate_id}-run.json."
)
```

4. If blocking: wait for Mogul to complete, then report summary
5. If non-blocking: report "Mogul mandate dispatched in background" and continue

## Team Topology Reference

When the mandate includes `pattern_mining`, `ladder_audit`, or `runtime_drift_check`, Mogul creates:

```
Team: mandate-pattern-triangulation
Lead: Mogul
Teammate 1: ladder-auditor       (T1: audit, T9: commentary)
Teammate 2: ripple-assessor      (T2: drift, T10: commentary)
Teammate 3: pattern-curator-meta  (T3: blind discovery, T5: submit, T7: eliminate)
Teammate 4: pattern-curator-direct (T4: blind discovery, T6: submit, T8: eliminate)
```

Task graph: T1-T4 parallel → T5-T6 → T7-T8 → T9-T10 → T11-T12 (Mogul synthesis + disposition).

## Output

Mogul produces:
- Run artifact: `audit-logs/mogul/runs/{mandate_id}-run.json`
- Updated mandate: `audit-logs/mogul/mandates/current.json` (status → completed)
- History append: `audit-logs/mogul/mandates/history/YYYY-MM-DD.jsonl`
- Pattern findings, ladder audit, drift findings (embedded in run artifact)

## Safety

- Mogul is read-only on governance surfaces (CLAUDE.md, MEMORY.md)
- Mogul writes only to execution surfaces (audit-logs/)
- All pattern candidates require `/review` human gate before promotion
- One team per session — if a team is already active, report conflict and exit
