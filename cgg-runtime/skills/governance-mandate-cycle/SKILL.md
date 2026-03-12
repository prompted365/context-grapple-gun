---
name: governance-mandate-cycle
description: "Execute pending Mogul governance mandate using the mandate-pattern-triangulation team. Spawns Mogul as background agent to consume mandate cycles."
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
